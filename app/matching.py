"""Normalize retailer titles and match them to a canonical perfume.

Size lives on the offer. The canonical is brand + name + concentration.
A flanker (an extra token that is not the brand and not noise) never
auto-matches.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

AUTO_MATCH = 92
REVIEW = 85

_CONCENTRATIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\beau de parfum\b|\bedp\b"), "edp"),
    (re.compile(r"\beau de toilette\b|\bedt\b"), "edt"),
    (re.compile(r"\beau de cologne\b|\bedc\b"), "edc"),
    (re.compile(r"\bextrait de parfum\b|\bextrait\b"), "extrait"),
    (re.compile(r"\bparfum\b"), "parfum"),
)

_ML = re.compile(r"\b(\d{1,4})\s*ml\b")

# Words that show up in Chilean listings and are not a different fragrance.
_NOISE = {
    "hombre",
    "mujer",
    "men",
    "man",
    "woman",
    "women",
    "pour",
    "homme",
    "femme",
    "caballero",
    "dama",
    "tester",
    "original",
    "nuevo",
    "new",
    "sellado",
    "envase",
    "spray",
    "vaporizador",
    "perfume",
    "fragancia",
    "colonia",
}


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize_text(value: str) -> str:
    text = strip_accents(value).lower().replace("'", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class ParsedTitle:
    raw: str
    nombre_normalizado: str
    concentracion: str | None
    ml: int | None

    @property
    def tokens(self) -> list[str]:
        return self.nombre_normalizado.split() if self.nombre_normalizado else []


@dataclass(frozen=True)
class Canonical:
    marca: str
    nombre_base: str
    concentracion: str

    @property
    def key(self) -> str:
        return normalize_text(f"{self.marca} {self.nombre_base}")

    @property
    def nombre_normalizado(self) -> str:
        return normalize_text(f"{self.marca} {self.nombre_base} {self.concentracion}")


@dataclass(frozen=True)
class Match:
    status: str  # matched | review | unmatched
    score: float
    canonical: Canonical | None
    parsed: ParsedTitle


def parse_title(title: str) -> ParsedTitle:
    text = normalize_text(title)
    ml: int | None = None
    ml_match = _ML.search(text)
    if ml_match:
        ml = int(ml_match.group(1))
        text = _ML.sub(" ", text)

    concentracion: str | None = None
    for pattern, code in _CONCENTRATIONS:
        if pattern.search(text):
            concentracion = code
            text = pattern.sub(" ", text)
            break

    text = re.sub(r"\s+", " ", text).strip()
    return ParsedTitle(
        raw=title,
        nombre_normalizado=text,
        concentracion=concentracion,
        ml=ml,
    )


def precio_por_ml(precio_clp: int, ml: int | None) -> int | None:
    if ml is None or ml <= 0:
        return None
    return round(precio_clp / ml)


def _score(parsed: ParsedTitle, canonical: Canonical) -> float:
    if parsed.concentracion and parsed.concentracion != canonical.concentracion:
        return 0.0

    offer = set(parsed.tokens)
    key = set(canonical.key.split())
    name = set(normalize_text(canonical.nombre_base).split())
    if not offer or not name:
        return 0.0

    missing_name = name - offer
    extra = offer - key - _NOISE

    if not missing_name and not extra:
        return 100.0

    # Flanker or a different juice: never an automatic match.
    fuzzy = float(fuzz.token_sort_ratio(parsed.nombre_normalizado, canonical.key))
    if extra or missing_name:
        return min(fuzzy, AUTO_MATCH - 1)
    return fuzzy


def match_title(title: str, catalog: list[Canonical]) -> Match:
    parsed = parse_title(title)
    if not catalog:
        return Match("unmatched", 0.0, None, parsed)

    ranked = sorted(
        ((_score(parsed, canonical), canonical) for canonical in catalog),
        key=lambda item: item[0],
        reverse=True,
    )
    score, canonical = ranked[0]
    if score >= AUTO_MATCH:
        return Match("matched", score, canonical, parsed)
    if score >= REVIEW:
        return Match("review", score, canonical, parsed)
    return Match("unmatched", score, None, parsed)

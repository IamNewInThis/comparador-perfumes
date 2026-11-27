"""Run from cron or manually; never from a user-facing HTTP request."""

from __future__ import annotations

import argparse
import logging
import os
import time

import httpx
from psycopg.types.json import Jsonb

from app.db import connection
from app.matching import Canonical, match_title, precio_por_ml
from app.retailers.shopify import STORES, RawOffer

LOG = logging.getLogger(__name__)


def catalog(conn) -> list[tuple[int, Canonical]]:
    rows = conn.execute("SELECT id, marca, nombre_base, concentracion FROM perfumes ORDER BY id").fetchall()
    return [(row["id"], Canonical(row["marca"], row["nombre_base"], row["concentracion"])) for row in rows]


def save_offer(conn, raw: RawOffer, entries: list[tuple[int, Canonical]]) -> str:
    match = match_title(raw.title, [canonical for _, canonical in entries])
    status = match.status
    # Concentration is part of the canonical identity. Never infer it.
    if match.parsed.concentracion is None and status == "matched":
        status = "review"
    perfume_id = next((id for id, c in entries if c == match.canonical), None) if status == "matched" else None
    old = conn.execute("SELECT id, precio_clp, match_status FROM ofertas WHERE url = %s", (raw.url,)).fetchone()
    row = conn.execute(
        """
        INSERT INTO ofertas
            (perfume_id, retailer, url, titulo_raw, ml, precio_clp, precio_por_ml,
             stock, match_score, match_status, imagen_url, visto_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (url) DO UPDATE SET
            perfume_id = CASE WHEN EXISTS (
                SELECT 1 FROM match_reviews r
                WHERE r.oferta_id = ofertas.id AND r.estado = 'resuelto'
            ) THEN ofertas.perfume_id ELSE EXCLUDED.perfume_id END,
            retailer = EXCLUDED.retailer,
            titulo_raw = EXCLUDED.titulo_raw,
            ml = EXCLUDED.ml,
            precio_clp = EXCLUDED.precio_clp,
            precio_por_ml = EXCLUDED.precio_por_ml,
            stock = EXCLUDED.stock,
            match_score = EXCLUDED.match_score,
            imagen_url = EXCLUDED.imagen_url,
            match_status = CASE WHEN EXISTS (
                SELECT 1 FROM match_reviews r
                WHERE r.oferta_id = ofertas.id AND r.estado = 'resuelto'
            ) THEN ofertas.match_status ELSE EXCLUDED.match_status END,
            visto_at = now()
        RETURNING id, match_status
        """,
        (perfume_id, raw.retailer, raw.url, raw.title, match.parsed.ml,
         raw.price_clp, precio_por_ml(raw.price_clp, match.parsed.ml),
         raw.available, match.score, status, raw.image_url),
    ).fetchone()
    if old is None or old["precio_clp"] != raw.price_clp:
        conn.execute(
            "INSERT INTO historial_precios (oferta_id, precio_clp) VALUES (%s, %s)",
            (row["id"], raw.price_clp),
        )
    if row["match_status"] == "review" and not conn.execute(
        "SELECT 1 FROM match_reviews WHERE oferta_id = %s AND estado = 'abierto'", (row["id"],)
    ).fetchone():
        conn.execute(
            "INSERT INTO match_reviews (oferta_id, candidatos) VALUES (%s, %s)",
            (row["id"], Jsonb([{"nombre": match.canonical.nombre_normalizado, "score": match.score}] if match.canonical else [])),
        )
    return row["match_status"]


def run() -> dict[str, int]:
    counts = {"matched": 0, "review": 0, "unmatched": 0}
    with connection() as conn:
        entries = catalog(conn)
    if not entries:
        raise RuntimeError("No hay perfumes semilla en la base")
    # The store search often omits products when the brand is included.
    # The matcher still checks brand, fragrance and concentration afterwards.
    queries = list(dict.fromkeys(c.nombre_base for _, c in entries))
    user_agent = os.getenv("SCRAPER_USER_AGENT", "ComparadorPerfumes/0.1 (+contacto local)")
    with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": user_agent}) as client:
        for store in STORES:
            for query in queries:
                try:
                    offers = store.search(query, client)
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    LOG.warning("Falló %s para %s: %s", store.name, query, exc)
                    continue
                with connection() as conn:
                    for offer in offers:
                        status = save_offer(conn, offer, entries)
                        counts[status] += 1
                time.sleep(1)
    return counts


if __name__ == "__main__":
    argparse.ArgumentParser(description="Actualiza ofertas desde tiendas públicas").parse_args()
    logging.basicConfig(level=logging.INFO)
    print(run())

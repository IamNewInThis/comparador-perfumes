"""Public search adapters for major Chilean department stores (Falabella, Paris, Ripley)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.retailers.shopify import RawOffer

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9",
}

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_NEXT_F_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.S)
_ITEM_LIST_RE = re.compile(r'\{"@context":"https://schema\.org","@type":"ItemList"')


def _parse_clp(value: object) -> int | None:
    if isinstance(value, (int, float)):
        amount = int(value)
        return amount if amount > 0 else None
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        if digits:
            amount = int(digits)
            return amount if amount > 0 else None
    return None


def _with_brand(brand: str | None, title: str) -> str:
    clean_title = title.strip()
    clean_brand = (brand or "").strip()
    if clean_brand and clean_brand.lower() not in clean_title.lower():
        return f"{clean_brand} {clean_title}"
    return clean_title


def _extract_next_data(html: str) -> dict:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return {}
    return json.loads(match.group(1))


@dataclass(frozen=True)
class FalabellaStore:
    name: str = "Falabella"

    def search(self, query: str, client: httpx.Client) -> list[RawOffer]:
        response = client.get(
            "https://www.falabella.com/falabella-cl/search",
            params={"Ntt": query},
            headers=_BROWSER_HEADERS,
        )
        response.raise_for_status()
        data = _extract_next_data(response.text)
        results = data.get("props", {}).get("pageProps", {}).get("results", [])
        offers: list[RawOffer] = []
        for item in results:
            url = item.get("url")
            title = item.get("displayName")
            if not isinstance(url, str) or not isinstance(title, str):
                continue
            price = self._best_price(item.get("prices"))
            if price is None:
                continue
            media = item.get("mediaUrls") or []
            image_url = media[0] if isinstance(media, list) and media and isinstance(media[0], str) else None
            offers.append(
                RawOffer(
                    retailer=self.name,
                    title=_with_brand(item.get("brand"), title),
                    url=url,
                    price_clp=price,
                    available=True,
                    image_url=image_url,
                )
            )
        return offers

    @staticmethod
    def _best_price(prices: object) -> int | None:
        if not isinstance(prices, list):
            return None
        candidates: list[int] = []
        for entry in prices:
            if not isinstance(entry, dict) or entry.get("crossed"):
                continue
            raw_list = entry.get("price")
            if isinstance(raw_list, list) and raw_list:
                parsed = _parse_clp(raw_list[0])
                if parsed:
                    candidates.append(parsed)
        return min(candidates) if candidates else None


@dataclass(frozen=True)
class ParisStore:
    name: str = "Paris"

    def search(self, query: str, client: httpx.Client) -> list[RawOffer]:
        response = client.get(
            "https://www.paris.cl/search",
            params={"q": query},
            headers=_BROWSER_HEADERS,
        )
        response.raise_for_status()
        items = self._extract_item_list(response.text)
        offers: list[RawOffer] = []
        for entry in items:
            product = entry.get("item") if isinstance(entry, dict) else None
            if not isinstance(product, dict):
                continue
            url = product.get("url")
            title = product.get("name")
            offer_data = product.get("offers")
            if not isinstance(url, str) or not isinstance(title, str) or not isinstance(offer_data, dict):
                continue
            price = _parse_clp(offer_data.get("price"))
            if price is None:
                continue
            availability = str(offer_data.get("availability") or "")
            available = "outofstock" not in availability.lower()
            brand_obj = product.get("brand")
            brand = brand_obj.get("name") if isinstance(brand_obj, dict) else None
            image = product.get("image")
            image_url = image if isinstance(image, str) and image.startswith("https://") else None
            offers.append(
                RawOffer(
                    retailer=self.name,
                    title=_with_brand(brand, title),
                    url=url,
                    price_clp=price,
                    available=available,
                    image_url=image_url,
                )
            )
        return offers

    @staticmethod
    def _extract_item_list(html: str) -> list[dict]:
        decoder = json.JSONDecoder()
        for chunk in _NEXT_F_RE.findall(html):
            if "itemListElement" not in chunk:
                continue
            try:
                unescaped = json.loads('"' + chunk + '"')
            except ValueError:
                continue
            match = _ITEM_LIST_RE.search(unescaped)
            if not match:
                continue
            try:
                obj, _ = decoder.raw_decode(unescaped[match.start():])
            except ValueError:
                continue
            items = obj.get("itemListElement")
            if isinstance(items, list):
                return items
        return []


@dataclass(frozen=True)
class RipleyStore:
    name: str = "Ripley"

    def search(self, query: str, client: httpx.Client) -> list[RawOffer]:
        response = client.get(
            f"https://simple.ripley.cl/search/{quote(query)}",
            headers=_BROWSER_HEADERS,
        )
        response.raise_for_status()
        data = _extract_next_data(response.text)
        findability = data.get("props", {}).get("pageProps", {}).get("findabilityProps", {}).get("data", {})
        products = findability.get("products") or []
        url_by_position = self._urls_by_position(findability.get("structuredData"))
        offers: list[RawOffer] = []
        for idx, item in enumerate(products, start=1):
            if not isinstance(item, dict):
                continue
            title = item.get("name")
            sku = item.get("sku")
            price = _parse_clp(item.get("priceNumber") or item.get("price"))
            if not isinstance(title, str) or price is None:
                continue
            pos = item.get("position") or idx
            url = url_by_position.get(pos) or (f"https://simple.ripley.cl/p/{sku}" if sku else None)
            if not url:
                continue
            images = item.get("images") or []
            image_url = item.get("primaryImage") or (images[0] if isinstance(images, list) and images else None)
            if not isinstance(image_url, str) or not image_url.startswith("https://"):
                image_url = None
            offers.append(
                RawOffer(
                    retailer=self.name,
                    title=_with_brand(item.get("brand"), title),
                    url=url,
                    price_clp=price,
                    available=bool(item.get("inStock", False)),
                    image_url=image_url,
                )
            )
        return offers

    @staticmethod
    def _urls_by_position(structured_data: object) -> dict[int, str]:
        if not isinstance(structured_data, dict):
            return {}
        urls: dict[int, str] = {}
        for node in structured_data.get("@graph") or []:
            if not isinstance(node, dict) or node.get("@type") != "CollectionPage":
                continue
            elements = node.get("mainEntity", {}).get("itemListElement") or []
            for entry in elements:
                if not isinstance(entry, dict):
                    continue
                pos = entry.get("position")
                url = entry.get("url")
                if isinstance(pos, int) and isinstance(url, str) and url.startswith("https://"):
                    urls[pos] = url
        return urls


CHILE_STORES = (
    FalabellaStore(),
    ParisStore(),
    RipleyStore(),
)

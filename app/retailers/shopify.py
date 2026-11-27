"""Low-volume search against the public Shopify predictive-search endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

import httpx


@dataclass(frozen=True)
class RawOffer:
    retailer: str
    title: str
    url: str
    price_clp: int
    available: bool
    image_url: str | None = None


def product_image_url(value: object, origin: str) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "cdn.shopify.com":
        return None
    filename = unquote(parsed.path.rsplit("/", 1)[-1])
    if filename in ("", ".", ".."):
        return None
    version = parse_qs(parsed.query).get("v", [None])[0]
    query = urlencode({"v": version}) if version and version.isdigit() else ""
    return origin + "/cdn/shop/files/" + quote(filename, safe="._-") + ("?" + query if query else "")


@dataclass(frozen=True)
class ShopifyStore:
    name: str
    origin: str

    def search(self, query: str, client: httpx.Client) -> list[RawOffer]:
        response = client.get(
            self.origin + "/search/suggest.json",
            params={"q": query, "resources[type]": "product", "resources[limit]": 10},
        )
        response.raise_for_status()
        products = response.json()["resources"]["results"]["products"]
        offers = []
        for product in products:
            path = urlparse(product.get("url", "")).path
            if not path.startswith("/products/"):
                continue
            try:
                price = int(product["price"])
            except (KeyError, TypeError, ValueError):
                continue
            if price <= 0:
                continue
            offers.append(
                RawOffer(
                    retailer=self.name,
                    title=product["title"],
                    url=self.origin + path,
                    price_clp=price,
                    available=bool(product.get("available", False)),
                    image_url=product_image_url(product.get("image"), self.origin),
                )
            )
        return offers


STORES = (
    ShopifyStore("Silk Perfumes", "https://silkperfumes.cl"),
    ShopifyStore("Perfuma", "https://perfuma.cl"),
)

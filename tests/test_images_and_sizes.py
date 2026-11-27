import httpx

from app.catalog import _serialize
from app.retailers.shopify import ShopifyStore


def test_shopify_offer_keeps_only_trusted_image_urls():
    payload = {
        "resources": {"results": {"products": [
            {"title": "Acqua di Gio EDT 100 ml", "url": "/products/one?tracking=1", "price": "79990", "available": True,
             "image": "https://cdn.shopify.com/s/files/one.jpg?v=1"},
            {"title": "Acqua di Gio EDT 50 ml", "url": "/products/two", "price": "59990", "available": True,
             "image": "https://example.invalid/image.jpg"},
        ]}}
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    with httpx.Client(transport=transport) as client:
        offers = ShopifyStore("Tienda", "https://store.example").search("Acqua di Gio", client)
    assert offers[0].image_url == "https://store.example/cdn/shop/files/one.jpg?v=1"
    assert offers[0].url == "https://store.example/products/one"
    assert offers[1].image_url is None


def test_presentations_do_not_mix_prices_between_sizes():
    row = {"id": 1, "marca": "Giorgio Armani", "nombre_base": "Acqua di Gio", "concentracion": "edp"}
    offers = [
        {"id": 1, "ml": 100, "titulo_raw": "Acqua di Gio EDP 100 ml", "imagen_url": "https://cdn.shopify.com/100.jpg", "retailer": "A"},
        {"id": 2, "ml": 50, "titulo_raw": "Acqua di Gio EDP 50 ml", "imagen_url": "https://cdn.shopify.com/50.jpg", "retailer": "A"},
        {"id": 3, "ml": 100, "titulo_raw": "Acqua di Gio EDP 100 ml", "imagen_url": None, "retailer": "B"},
    ]
    result = _serialize(row, offers)
    assert [item["ml"] for item in result["presentaciones"]] == [50, 100]
    assert [len(item["ofertas"]) for item in result["presentaciones"]] == [1, 2]
    assert result["imagen_url"] == "https://cdn.shopify.com/100.jpg"

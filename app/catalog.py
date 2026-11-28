"""Read-only catalog queries. Scraping never happens in a web request."""

from __future__ import annotations

from app.db import connection
from app.matching import parse_title


def _offers(conn, perfume_id: int, sort: str) -> list[dict]:
    order = (
        "o.precio_clp ASC, o.precio_por_ml ASC NULLS LAST"
        if sort == "precio"
        else "o.precio_por_ml ASC NULLS LAST, o.precio_clp ASC"
    )
    rows = conn.execute(
        f"""
        SELECT o.id, o.retailer, o.titulo_raw, o.ml, o.precio_clp,
               o.precio_por_ml, o.url, o.imagen_url, o.visto_at
        FROM ofertas o
        WHERE o.perfume_id = %s AND o.match_status = 'matched'
          AND o.stock IS TRUE
          AND o.visto_at >= now() - interval '48 hours'
        ORDER BY {order}, o.id
        """,
        (perfume_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _serialize(row: dict, offers: list[dict]) -> dict:
    sizes = sorted({offer["ml"] for offer in offers if offer["ml"] is not None})
    if any(offer["ml"] is None for offer in offers):
        sizes.append(None)
    presentations = [
        {
            "ml": size,
            "ofertas": [offer for offer in offers if offer["ml"] == size],
        }
        for size in sizes
    ]
    images = [offer for offer in offers if offer.get("imagen_url")]
    images.sort(
        key=lambda offer: (
            "tester" in offer["titulo_raw"].lower(),
            abs((offer["ml"] or 100) - 100),
            offer["id"],
        )
    )
    return {
        "id": row["id"],
        "marca": row["marca"],
        "nombre_base": row["nombre_base"],
        "concentracion": row["concentracion"],
        "ofertas": offers,
        "presentaciones": presentations,
        "imagen_url": images[0]["imagen_url"] if images else None,
    }


_ACTIVE_OFFER_EXISTS = """
EXISTS (
    SELECT 1 FROM ofertas o
    WHERE o.perfume_id = p.id
      AND o.match_status = 'matched'
      AND o.stock IS TRUE
      AND o.visto_at >= now() - interval '48 hours'
)
"""


def search_perfumes_page(
    query: str = "",
    sort: str = "precio_ml",
    page: int = 1,
    per_page: int = 24,
) -> dict:
    parsed = parse_title(query)
    terms = parsed.nombre_normalizado.split()
    where_parts = [_ACTIVE_OFFER_EXISTS]
    params: list = []
    if terms:
        # Parameters and literal substring matching keep user wildcards inert.
        for term in terms:
            where_parts.append("p.nombre_normalizado LIKE %s ESCAPE '\\'")
            params.append("%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        if parsed.concentracion:
            where_parts.append("p.concentracion = %s")
            params.append(parsed.concentracion)

    where_sql = " AND ".join(where_parts)
    safe_per_page = max(1, min(per_page, 100))

    with connection() as conn:
        total = conn.execute(
            f"SELECT count(*) AS total FROM perfumes p WHERE {where_sql}",
            params,
        ).fetchone()["total"]
        total_pages = max(1, (total + safe_per_page - 1) // safe_per_page)
        safe_page = max(1, min(page, total_pages))
        offset = (safe_page - 1) * safe_per_page
        rows = conn.execute(
            f"""
            SELECT p.id, p.marca, p.nombre_base, p.concentracion
            FROM perfumes p
            WHERE {where_sql}
            ORDER BY p.marca, p.nombre_base, p.concentracion
            LIMIT %s OFFSET %s
            """,
            [*params, safe_per_page, offset],
        ).fetchall()
        items = [_serialize(row, _offers(conn, row["id"], sort)) for row in rows]

    return {
        "items": [item for item in items if item["ofertas"]],
        "total": total,
        "page": safe_page,
        "per_page": safe_per_page,
        "total_pages": total_pages,
    }


def search_perfumes(query: str = "", sort: str = "precio_ml", page: int = 1, per_page: int = 100) -> list[dict]:
    return search_perfumes_page(query=query, sort=sort, page=page, per_page=per_page)["items"]


def get_perfume(perfume_id: int, sort: str = "precio_ml") -> dict | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT id, marca, nombre_base, concentracion FROM perfumes WHERE id = %s",
            (perfume_id,),
        ).fetchone()
        return _serialize(row, _offers(conn, perfume_id, sort)) if row else None

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


def search_perfumes(query: str = "", sort: str = "precio_ml") -> list[dict]:
    parsed = parse_title(query)
    terms = parsed.nombre_normalizado.split()
    with connection() as conn:
        if terms:
            # Parameters and literal substring matching keep user wildcards inert.
            predicates = " AND ".join("nombre_normalizado LIKE %s ESCAPE '\\'" for _ in terms)
            params = ["%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%" for term in terms]
            if parsed.concentracion:
                predicates += " AND concentracion = %s"
                params.append(parsed.concentracion)
            rows = conn.execute(
                f"SELECT id, marca, nombre_base, concentracion FROM perfumes WHERE {predicates} ORDER BY marca, nombre_base LIMIT 30",
                params,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, marca, nombre_base, concentracion FROM perfumes ORDER BY marca, nombre_base LIMIT 30"
            ).fetchall()
        result = [_serialize(row, _offers(conn, row["id"], sort)) for row in rows]
    return [item for item in result if item["ofertas"]]


def get_perfume(perfume_id: int, sort: str = "precio_ml") -> dict | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT id, marca, nombre_base, concentracion FROM perfumes WHERE id = %s",
            (perfume_id,),
        ).fetchone()
        return _serialize(row, _offers(conn, perfume_id, sort)) if row else None

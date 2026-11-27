"""Public API and small server-rendered UI."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from psycopg import OperationalError

from app.catalog import get_perfume, search_perfumes
from app.db import connection

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Comparador de perfumes")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


def format_clp(value: int | None) -> str:
    return "$" + f"{value:,}".replace(",", ".") if value is not None else "—"


templates.env.filters["clp"] = format_clp


def image_width(url: str, width: int) -> str:
    parsed = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query) if key != "width"]
    query.append(("width", str(width)))
    return urlunsplit(parsed._replace(query=urlencode(query)))


templates.env.filters["image_width"] = image_width


@app.get("/health")
def health():
    try:
        with connection() as conn:
            conn.execute("SELECT 1")
    except (OperationalError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Base de datos no disponible") from exc
    return {"status": "ok"}


@app.get("/perfumes")
def perfumes(q: str = Query(default="", max_length=120), sort: str = Query(default="precio_ml", pattern="^(precio_ml|precio)$")):
    return search_perfumes(q, sort)


@app.get("/perfumes/{perfume_id}")
def perfume(perfume_id: int, sort: str = Query(default="precio_ml", pattern="^(precio_ml|precio)$")):
    result = get_perfume(perfume_id, sort)
    if result is None:
        raise HTTPException(status_code=404, detail="Perfume no encontrado")
    return result


@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: str = Query(default="", max_length=120)):
    products = search_perfumes(q)
    return templates.TemplateResponse(request, "home.html", {"q": q, "products": products})


@app.get("/p/{perfume_id}", response_class=HTMLResponse)
def product_page(request: Request, perfume_id: int, sort: str = Query(default="precio_ml", pattern="^(precio_ml|precio)$")):
    product = get_perfume(perfume_id, sort)
    if product is None:
        raise HTTPException(status_code=404, detail="Perfume no encontrado")
    return templates.TemplateResponse(request, "product.html", {"product": product, "sort": sort})

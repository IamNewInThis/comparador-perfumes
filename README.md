# Comparador de perfumes

Comparador de precios de perfumes en Chile, en la línea de SoloTodo. La comparación justa es el precio por ml.

Decisiones (27 nov 2026):

- Sin Mercado Libre en el MVP.
- Tracking cada 12 horas. El historial guarda una fila solo si el precio cambió. `visto_at` se actualiza en cada corrida.
- Notas olfativas después.
- Monetización: solo publicidad.
- Deploy en la VPS.
- Matching: normalizar, exacto, y fuzzy. Automático desde 92. Cola de revisión de 85 a 91. Un flanker (token extra que no es marca ni ruido) no se une solo.

El canónico es marca + nombre + concentración. 50 ml y 100 ml son ofertas del mismo perfume.

## Probar en local

```bash
docker compose up -d --build
```

Abre <http://127.0.0.1:8000>. El contenedor `scheduler` consulta Silk Perfumes y Perfuma al arrancar y luego cada 12 horas. El primer llenado demora unos segundos. Para correrlo manualmente:

```bash
docker compose --profile tools run --rm ingest
```

La API expone `GET /health`, `GET /perfumes?q=polo+blue` y `GET /perfumes/{id}`. Por defecto ordena las ofertas por precio por ml; `sort=precio` usa el precio de la botella. Solo muestra ofertas disponibles, vinculadas con confianza y vistas en las últimas 48 horas. Los precios son observaciones, no una garantía de compra.

La búsqueda y la ficha muestran fotos entregadas por las tiendas cuando existen. La ficha separa las ofertas por tamaño (por ejemplo, 50 ml y 100 ml) y compara precios entre tiendas dentro de cada presentación. Las imágenes se cargan desde el CDN del dominio de cada tienda en una resolución adecuada para cada vista; no se descargan al servidor.

El `compose.yaml` es **solo para desarrollo local**: publica la web en `127.0.0.1` y usa una contraseña de Postgres de ejemplo. Para la VPS hay que definir credenciales fuera del repo, proxy/TLS y respaldo antes del deploy.

## Matching

```bash
python -m pip install -r requirements.txt
python -m pytest
```

`match_title(titulo, catalogo)` devuelve `matched`, `review` o `unmatched`, más ml y concentración parseados. No crea canónicos solo.

## Esquema

`db/001_schema.sql`, `db/002_offer_images.sql` y `db/seed.sql` se aplican automáticamente al crear un volumen Postgres nuevo. El seed contiene canónicos, sin precios ficticios. El request del usuario lee la base; `scheduler` escribe fuera del request. `historial_precios` guarda la primera observación y cada cambio de precio; `visto_at` se actualiza en cada ingesta. Si agregas canónicos al seed con el volumen ya creado, aplícalo manualmente con `docker compose exec -T db psql -U perfumes -d perfumes < db/seed.sql`.

Si ya tenías un volumen creado antes de las fotos, aplica `docker compose exec -T db psql -U perfumes -d perfumes < db/002_offer_images.sql` y luego `docker compose --profile tools run --rm --build ingest` para completar las URLs de imagen existentes.

Los adapters usan una búsqueda pública de bajo volumen, sin cuenta de cliente. Si una tienda deja de responder, la otra sigue procesándose. Los productos sin match seguro quedan fuera del catálogo público; los dudosos se guardan en `match_reviews` para revisión futura.

Proyecto: Linear, equipo SimpleDigital, Comparador de Perfumes.

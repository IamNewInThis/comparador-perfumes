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

## Matching

```bash
python -m pip install -r requirements.txt
python -m pytest
```

`match_title(titulo, catalogo)` devuelve `matched`, `review` o `unmatched`, más ml y concentración parseados. No crea canónicos solo.

## Esquema

`db/001_schema.sql` y `db/seed.sql` van sobre Postgres. El request del usuario lee la base. El scraper escribe, cada 12 horas, fuera del request.

Proyecto: Linear, equipo SimpleDigital, Comparador de Perfumes.

-- Canonical perfume. 50 ml and 100 ml are offers, not two perfumes.
CREATE TABLE perfumes (
    id            BIGSERIAL PRIMARY KEY,
    marca         TEXT NOT NULL,
    nombre_base   TEXT NOT NULL,
    concentracion TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ofertas (
    id             BIGSERIAL PRIMARY KEY,
    perfume_id     BIGINT REFERENCES perfumes (id),
    retailer       TEXT NOT NULL,
    url            TEXT NOT NULL UNIQUE,
    titulo_raw     TEXT NOT NULL,
    ml             INTEGER,
    precio_clp     INTEGER NOT NULL,
    precio_por_ml  INTEGER,
    stock          BOOLEAN,
    match_score    NUMERIC(5, 2),
    match_status   TEXT NOT NULL CHECK (match_status IN ('matched', 'review', 'unmatched')),
    visto_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ofertas_perfume_id_idx ON ofertas (perfume_id);
CREATE INDEX ofertas_status_idx ON ofertas (match_status);

-- A row is written only when the price changes. visto_at on the offer
-- still moves on every 12 h run.
CREATE TABLE historial_precios (
    id          BIGSERIAL PRIMARY KEY,
    oferta_id   BIGINT NOT NULL REFERENCES ofertas (id),
    precio_clp  INTEGER NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX historial_oferta_idx ON historial_precios (oferta_id, captured_at);

CREATE TABLE match_reviews (
    id         BIGSERIAL PRIMARY KEY,
    oferta_id  BIGINT NOT NULL REFERENCES ofertas (id),
    candidatos JSONB NOT NULL,
    estado     TEXT NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto', 'resuelto')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

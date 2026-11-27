INSERT INTO perfumes (marca, nombre_base, concentracion, nombre_normalizado)
VALUES
    ('Giorgio Armani', 'Acqua di Gio', 'edt', 'giorgio armani acqua di gio edt'),
    ('Dior', 'Sauvage', 'edp', 'dior sauvage edp')
ON CONFLICT (nombre_normalizado) DO NOTHING;

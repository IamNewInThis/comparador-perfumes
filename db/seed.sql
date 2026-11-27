INSERT INTO perfumes (marca, nombre_base, concentracion, nombre_normalizado)
VALUES
    ('Giorgio Armani', 'Acqua di Gio', 'edt', 'giorgio armani acqua di gio edt'),
    ('Giorgio Armani', 'Acqua di Gio', 'edp', 'giorgio armani acqua di gio edp'),
    ('Dior', 'Sauvage', 'edp', 'dior sauvage edp'),
    ('Dior', 'Sauvage', 'edt', 'dior sauvage edt'),
    ('Ralph Lauren', 'Polo Blue', 'edt', 'ralph lauren polo blue edt')
ON CONFLICT (nombre_normalizado) DO NOTHING;

-- =============================================================
-- 002_seed_productos.sql — Tacos Las Cazuelitas
-- Migración 002: seed completo del catálogo de productos.
-- Idempotente: usa ON CONFLICT DO NOTHING para re-ejecuciones.
-- Ejecutar después de 001_schema_inicial.sql
-- =============================================================

-- ── Guisados del menú ($20.00 MXN c/u) ──────────────────────
INSERT INTO productos (nombre, categoria, precio_unitario, activo) VALUES
    ('Pepena',                        'guisado', 20.00, TRUE),
    ('Carne de puerco con calabacita','guisado', 20.00, TRUE),
    ('Chicharrón',                    'guisado', 20.00, TRUE),
    ('Machaca',                       'guisado', 20.00, TRUE),
    ('Carne de res a la mexicana',    'guisado', 20.00, TRUE),
    ('Rajas con crema y elote',       'guisado', 20.00, TRUE),
    ('Frijoles',                      'guisado', 20.00, TRUE),
    ('Huevo con jamón',               'guisado', 20.00, TRUE)
ON CONFLICT (nombre) DO NOTHING;

-- ── Bebidas del menú ($25.00 MXN c/u) ───────────────────────
INSERT INTO productos (nombre, categoria, precio_unitario, activo) VALUES
    ('Agua fresca del día', 'bebida', 25.00, TRUE),
    ('Coca-Cola',           'bebida', 25.00, TRUE),
    ('Coca-Cola Light',     'bebida', 25.00, TRUE),
    ('Squirt',              'bebida', 25.00, TRUE),
    ('Fanta de Naranja',    'bebida', 25.00, TRUE),
    ('Manzanita Sidral',    'bebida', 25.00, TRUE)
ON CONFLICT (nombre) DO NOTHING;

-- Verificación rápida (opcional, útil en scripts de CI)
-- SELECT categoria, COUNT(*) AS total, AVG(precio_unitario) AS precio_prom
-- FROM productos GROUP BY categoria ORDER BY categoria;

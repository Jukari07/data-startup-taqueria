-- =============================================================
-- 001_schema_inicial.sql — Tacos Las Cazuelitas
-- Migración 001: definición completa del esquema relacional.
-- Motor: PostgreSQL 16
-- Ejecutar: psql -U taqueria_user -d taqueria -f 001_schema_inicial.sql
-- =============================================================

-- Habilita la extensión uuid-ossp para generar UUIDs en el servidor
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================
-- TABLA: usuarios
-- Almacena tanto clientes como empleados (cajeros, cocineros).
-- El campo `rol` permite control de acceso basado en roles (RBAC).
-- =============================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre        VARCHAR(120)  NOT NULL,
    email         VARCHAR(254)  NOT NULL UNIQUE,
    password_hash VARCHAR(255)  NOT NULL,
    rol           VARCHAR(30)   NOT NULL DEFAULT 'cliente'
                      CHECK (rol IN ('cliente','cajero','cocinero','admin')),
    creado_en     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  usuarios              IS 'Usuarios del sistema: clientes, cajeros, cocineros y administradores.';
COMMENT ON COLUMN usuarios.id           IS 'Identificador único UUID generado automáticamente.';
COMMENT ON COLUMN usuarios.email        IS 'Correo único, usado como nombre de usuario para autenticación.';
COMMENT ON COLUMN usuarios.password_hash IS 'Hash bcrypt de la contraseña; nunca se guarda en texto plano.';
COMMENT ON COLUMN usuarios.rol          IS 'Rol de acceso: cliente | cajero | cocinero | admin.';

-- =============================================================
-- TABLA: productos
-- Catálogo de guisados y bebidas del menú de la taquería.
-- =============================================================
CREATE TABLE IF NOT EXISTS productos (
    id               SERIAL PRIMARY KEY,
    nombre           VARCHAR(100) NOT NULL UNIQUE,
    categoria        VARCHAR(50)  NOT NULL
                         CHECK (categoria IN ('guisado','bebida','extra')),
    precio_unitario  NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    activo           BOOLEAN      NOT NULL DEFAULT TRUE,
    creado_en        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  productos                 IS 'Catálogo de productos disponibles en el menú de la taquería.';
COMMENT ON COLUMN productos.categoria       IS 'Clasificación del producto: guisado, bebida o extra.';
COMMENT ON COLUMN productos.precio_unitario IS 'Precio en pesos mexicanos (MXN) sin impuesto adicional.';
COMMENT ON COLUMN productos.activo          IS 'FALSE cuando el producto está temporalmente fuera de menú.';

-- =============================================================
-- TABLA: pedidos
-- Encabezado de cada orden realizada por un cliente.
-- =============================================================
CREATE TABLE IF NOT EXISTS pedidos (
    pedido_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cliente_id         UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    fecha_hora         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    tipo_entrega       VARCHAR(20)  NOT NULL
                           CHECK (tipo_entrega IN ('llevar','aqui','domicilio')),
    estado             VARCHAR(20)  NOT NULL DEFAULT 'pendiente'
                           CHECK (estado IN ('pendiente','en_preparacion','listo','entregado','cancelado')),
    direccion_domicilio TEXT,
    notas              TEXT,
    total              NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    creado_en          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  pedidos                     IS 'Encabezado de cada pedido; referencia al cliente y estado del flujo de cocina.';
COMMENT ON COLUMN pedidos.tipo_entrega        IS 'Modalidad: llevar (para llevar), aqui (en mesa), domicilio (delivery).';
COMMENT ON COLUMN pedidos.estado              IS 'Flujo: pendiente → en_preparacion → listo → entregado / cancelado.';
COMMENT ON COLUMN pedidos.direccion_domicilio IS 'Dirección de entrega; obligatoria solo cuando tipo_entrega=domicilio.';
COMMENT ON COLUMN pedidos.total               IS 'Suma de subtotales de detalle_pedido; actualizada por trigger o aplicación.';

-- Índices para acelerar consultas frecuentes en el tablero
CREATE INDEX IF NOT EXISTS idx_pedidos_fecha_hora  ON pedidos (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_pedidos_cliente_id  ON pedidos (cliente_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado      ON pedidos (estado);

-- =============================================================
-- TABLA: detalle_pedido
-- Líneas de detalle (ítems) de cada pedido.
-- =============================================================
CREATE TABLE IF NOT EXISTS detalle_pedido (
    id              SERIAL PRIMARY KEY,
    pedido_id       UUID          NOT NULL REFERENCES pedidos(pedido_id) ON DELETE CASCADE,
    producto_id     INT           NOT NULL REFERENCES productos(id),
    salsa           VARCHAR(10)   NOT NULL DEFAULT 'verde'
                        CHECK (salsa IN ('verde','roja','sin_salsa')),
    cantidad        INT           NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    subtotal        NUMERIC(10,2) NOT NULL CHECK (subtotal >= 0),
    creado_en       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  detalle_pedido                IS 'Líneas de detalle de cada pedido; un registro por producto/salsa seleccionado.';
COMMENT ON COLUMN detalle_pedido.salsa          IS 'Preferencia de salsa del cliente: verde, roja o sin_salsa.';
COMMENT ON COLUMN detalle_pedido.precio_unitario IS 'Precio del producto al momento de crear el pedido (precio histórico).';
COMMENT ON COLUMN detalle_pedido.subtotal        IS 'cantidad × precio_unitario; calculado en la aplicación antes del INSERT.';

-- =============================================================
-- DATOS INICIALES: productos del menú
-- (El seed completo está en 002_seed_productos.sql)
-- Este bloque usa INSERT ... ON CONFLICT DO NOTHING para que
-- sea idempotente al re-ejecutar la migración.
-- =============================================================

INSERT INTO productos (nombre, categoria, precio_unitario) VALUES
-- Guisados ($20 MXN)
('Pepena',                      'guisado', 20.00),
('Carne de puerco con calabacita','guisado', 20.00),
('Chicharrón',                  'guisado', 20.00),
('Machaca',                     'guisado', 20.00),
('Carne de res a la mexicana',  'guisado', 20.00),
('Rajas con crema y elote',     'guisado', 20.00),
('Frijoles',                    'guisado', 20.00),
('Huevo con jamón',             'guisado', 20.00),
-- Bebidas ($25 MXN)
('Agua fresca del día',         'bebida',  25.00),
('Coca-Cola',                   'bebida',  25.00),
('Coca-Cola Light',             'bebida',  25.00),
('Squirt',                      'bebida',  25.00),
('Fanta de Naranja',            'bebida',  25.00),
('Manzanita Sidral',            'bebida',  25.00)
ON CONFLICT (nombre) DO NOTHING;

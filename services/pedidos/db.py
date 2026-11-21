"""
Módulo de conexión a PostgreSQL para Las Cazuelitas.
Usa psycopg2 y lee la configuración desde variables de entorno POSTGRES_*.
Proporciona un context manager para manejo seguro de conexiones.
"""

import contextlib
import glob
import os
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as Psycopg2Connection


# ---------------------------------------------------------------------------
# Parámetros de conexión leídos desde variables de entorno
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "taqueria"),
    "user": os.getenv("POSTGRES_USER", "taqueria_user"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}


def get_connection() -> Psycopg2Connection:
    """
    Abre y retorna una nueva conexión a PostgreSQL.
    La conexión NO se cierra automáticamente; úsala dentro del context
    manager `conexion()` para garantizar el cierre correcto.

    Lanza psycopg2.OperationalError si no puede conectarse.
    """
    return psycopg2.connect(**DB_CONFIG)


@contextlib.contextmanager
def conexion():
    """
    Context manager que abre una conexión, la entrega y la cierra al salir.

    Uso:
        with conexion() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = get_connection()
    try:
        yield conn
    except Exception:
        # Si ocurre un error, revertimos la transacción en curso
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Ejecuta todos los archivos de migración SQL ubicados en db/migrations/,
    en orden alfabético. Solo ejecuta cada migración una vez, usando la tabla
    de control `_migraciones`.

    Los archivos deben seguir el patrón: NNN_descripcion.sql
    Ejemplo: 001_schema_inicial.sql, 002_datos_semilla.sql
    """
    # Ruta de las migraciones relativa al directorio raíz del proyecto
    ruta_migraciones = Path(__file__).resolve().parents[2] / "db" / "migrations"

    with conexion() as conn:
        with conn.cursor() as cur:
            # Crear tabla de control si no existe
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS _migraciones (
                    nombre   VARCHAR(255) PRIMARY KEY,
                    aplicada TIMESTAMPTZ  DEFAULT NOW()
                )
                """
            )
            conn.commit()

            # Obtener migraciones ya aplicadas
            cur.execute("SELECT nombre FROM _migraciones")
            aplicadas = {fila[0] for fila in cur.fetchall()}

            # Recorrer archivos SQL ordenados alfabéticamente
            archivos_sql = sorted(ruta_migraciones.glob("*.sql"))
            if not archivos_sql:
                print(f"[db] No se encontraron migraciones en {ruta_migraciones}")
                return

            for archivo in archivos_sql:
                nombre = archivo.name
                if nombre in aplicadas:
                    print(f"[db] Migración ya aplicada, omitiendo: {nombre}")
                    continue

                print(f"[db] Aplicando migración: {nombre}")
                sql = archivo.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO _migraciones (nombre) VALUES (%s)", (nombre,)
                )
                conn.commit()
                print(f"[db] Migración completada: {nombre}")

    print("[db] Todas las migraciones están al día.")

"""
ingesta_csv.py
==============
Módulo y CLI para la ingesta de archivos CSV hacia la zona raw/ del data lake
y publicación del evento en la cola de mensajería (RabbitMQ / SQS).

Uso CLI:
    python -m services.ingesta.ingesta_csv --archivo data/raw/pedidos_raw.csv
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Asegurar importación de módulos raíz
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.pedidos.cola import get_cola
from services.pedidos.storage import subir_raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingesta")

# Columnas mínimas que debe contener un lote de pedidos para ser admitido
COLUMNAS_OBLIGATORIAS = {
    "pedido_id",
    "fecha_hora",
    "cliente_id",
    "tipo_entrega",
    "producto",
    "categoria",
    "cantidad",
    "precio_unitario",
    "total",
}


def validar_csv(ruta_csv: str) -> bytes:
    """
    Valida que el archivo exista, no esté vacío y contenga las columnas requeridas.
    Retorna el contenido en bytes listo para transferir a S3/MinIO.
    """
    path = Path(ruta_csv)
    if not path.exists():
        raise FileNotFoundError(f"El archivo {ruta_csv} no existe.")

    contenido = path.read_bytes()
    if len(contenido) == 0:
        raise ValueError("El archivo está vacío.")

    df_test = pd.read_csv(path, nrows=5)
    columnas_presentes = set(df_test.columns)
    faltantes = COLUMNAS_OBLIGATORIAS - columnas_presentes
    if faltantes:
        raise ValueError(f"El CSV no contiene las columnas requeridas: {faltantes}")

    return contenido


def ejecutar_ingesta(ruta_csv: str) -> dict:
    """
    Ejecuta el flujo completo de ingesta:
    1. Valida el CSV.
    2. Sube a S3/MinIO (zona raw/).
    3. Publica evento en la cola.
    """
    logger.info("Iniciando validación de archivo: %s", ruta_csv)
    contenido = validar_csv(ruta_csv)
    nombre_archivo = Path(ruta_csv).name

    logger.info("Subiendo archivo a zona raw/ en almacenamiento de objetos...")
    ruta_s3 = subir_raw(contenido, nombre_archivo)
    logger.info("Archivo almacenado en: %s", ruta_s3)

    logger.info("Publicando mensaje en cola de mensajería...")
    cola = get_cola()
    mensaje = {
        "tipo_evento": "archivo_ingestado",
        "ruta_raw": ruta_s3,
        "nombre_archivo": nombre_archivo,
    }
    cola.publicar(mensaje)
    cola.cerrar()
    logger.info("Mensaje publicado con éxito en la cola.")

    return {
        "status": "ingestado",
        "ruta_raw": ruta_s3,
        "tamano_bytes": len(contenido),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta masiva de CSV a raw/ y notificación a cola.")
    parser.add_argument("--archivo", required=True, help="Ruta local al archivo CSV a ingestar.")
    args = parser.parse_args()

    try:
        resultado = ejecutar_ingesta(args.archivo)
        print("\n=== INGESTA COMPLETADA EXITOSAMENTE ===")
        for k, v in resultado.items():
            print(f"  {k}: {v}")
    except Exception as e:
        logger.error("Error durante la ingesta: %s", e)
        sys.exit(1)

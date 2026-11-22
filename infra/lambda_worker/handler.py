"""
handler.py
==========
Función Serverless AWS Lambda (Python 3.11) para procesamiento de eventos de pedidos.
Puede activarse mediante:
  a) Disparador de eventos SQS (lote de mensajes)
  b) Notificación S3 ObjectCreated en bucket taqueria-raw

Flujo:
  1. Extrae la ruta del archivo raw del evento.
  2. Descarga el CSV desde S3.
  3. Ejecuta la función reproducible de limpieza de datos.
  4. Sube el dataset limpio a la zona clean/ de S3.
  5. Maneja fallos parciales por registro para evitar reprocesamiento innecesario (batch item failure).
"""

import io
import json
import logging
import os
import boto3
import pandas as pd

# Módulo de limpieza empaquetado en el runtime de la Lambda
from services.worker.limpieza import limpiar_pedidos

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")

BUCKET_RAW = os.getenv("BUCKET_RAW", "taqueria-raw-prod")
BUCKET_CLEAN = os.getenv("BUCKET_CLEAN", "taqueria-clean-prod")


def lambda_handler(event, context):
    """
    Punto de entrada principal de la Lambda de AWS.
    Procesa lotes de eventos SQS devolviendo los identificadores de mensajes que fallaron.
    """
    logger.info("Evento recibido en Lambda Worker: %s", json.dumps(event))

    batch_item_failures = []
    registros = event.get("Records", [])

    for record in registros:
        mensaje_id = record.get("messageId", "desconocido")
        try:
            # 1. Parsear cuerpo del mensaje (origen SQS o S3 directo)
            cuerpo = record.get("body", "{}")
            if isinstance(cuerpo, str):
                try:
                    datos = json.loads(cuerpo)
                except json.JSONDecodeError:
                    datos = {"ruta_raw": cuerpo}
            else:
                datos = cuerpo

            ruta_raw = datos.get("ruta_raw") or datos.get("path")
            if not ruta_raw:
                # Si vino directamente de notificación S3 en SQS
                s3_info = datos.get("Records", [{}])[0].get("s3", {})
                ruta_raw = s3_info.get("object", {}).get("key")

            if not ruta_raw:
                raise ValueError(f"No se encontró la ruta del archivo raw en el mensaje {mensaje_id}")

            logger.info("Procesando archivo: s3://%s/%s", BUCKET_RAW, ruta_raw)

            # 2. Descargar CSV crudo desde S3
            obj = s3_client.get_object(Bucket=BUCKET_RAW, Key=ruta_raw)
            contenido_csv = obj["Body"].read()

            # 3. Aplicar limpieza en memoria usando un buffer temporal
            import tempfile
            with tempfile.NamedTemporaryFile(suffix="_raw.csv", delete=False) as f_raw, \
                 tempfile.NamedTemporaryFile(suffix="_clean.csv", delete=False) as f_clean, \
                 tempfile.NamedTemporaryFile(suffix="_rep.json", delete=False) as f_rep:
                
                f_raw.write(contenido_csv)
                f_raw.flush()

                df_clean, reporte = limpiar_pedidos(f_raw.name, f_clean.name, f_rep.name)
                contenido_clean = open(f_clean.name, "rb").read()
                contenido_rep = open(f_rep.name, "rb").read()

            # 4. Construir clave de salida en zona clean/
            nombre_base = os.path.basename(ruta_raw).replace("pedidos_", "pedidos_clean_")
            ruta_clean = ruta_raw.replace("raw/", "clean/").replace(os.path.basename(ruta_raw), nombre_base)

            # 5. Subir resultado a S3 zona clean
            s3_client.put_object(
                Bucket=BUCKET_CLEAN,
                Key=ruta_clean,
                Body=contenido_clean,
                ContentType="text/csv",
            )

            # Subir reporte de calidad asociado
            ruta_rep = ruta_clean.replace(".csv", "_reporte.json")
            s3_client.put_object(
                Bucket=BUCKET_CLEAN,
                Key=ruta_rep,
                Body=contenido_rep,
                ContentType="application/json",
            )

            logger.info("Archivo limpio guardado con éxito en s3://%s/%s", BUCKET_CLEAN, ruta_clean)

        except Exception as e:
            logger.error("Error procesando mensaje %s: %s", mensaje_id, e, exc_info=True)
            # Notificar fallo parcial a SQS para que solo este mensaje reintente
            batch_item_failures.append({"itemIdentifier": mensaje_id})

    return {
        "statusCode": 200,
        "batchItemFailures": batch_item_failures,
    }

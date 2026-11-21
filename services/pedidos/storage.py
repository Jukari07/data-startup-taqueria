"""
Módulo de almacenamiento S3/MinIO para Las Cazuelitas.
Usa boto3 con la misma API S3 tanto para MinIO (local) como para AWS S3 (producción).
La variable de entorno MINIO_ENDPOINT determina si se usa MinIO o S3 real.
"""

import os
import uuid
from datetime import datetime

import boto3
from botocore.client import Config


# ---------------------------------------------------------------------------
# Configuración de buckets
# ---------------------------------------------------------------------------
BUCKET_RAW = os.getenv("MINIO_BUCKET_RAW", "taqueria-raw")
BUCKET_CLEAN = os.getenv("MINIO_BUCKET_CLEAN", "taqueria-clean")

# Endpoint de MinIO (solo se define en entorno local/dev)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def get_s3_client():
    """
    Retorna un cliente boto3 configurado para S3 o MinIO según el entorno.

    - Si MINIO_ENDPOINT está definido → usa MinIO (entorno local/dev).
    - Si no está definido → usa AWS S3 con credenciales del entorno/rol IAM.
    """
    if MINIO_ENDPOINT:
        # Configuración para MinIO (compatible con API S3)
        cliente = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",  # MinIO acepta cualquier región
        )
        # Crear buckets si no existen (útil en desarrollo)
        _asegurar_buckets(cliente)
    else:
        # AWS S3: las credenciales vienen del perfil de instancia EC2/ECS o env vars
        cliente = boto3.client("s3", region_name=AWS_REGION)
    return cliente


def _asegurar_buckets(cliente) -> None:
    """
    Crea los buckets raw y clean en MinIO si aún no existen.
    Se omite en AWS S3 (los buckets se crean via Terraform).
    """
    buckets_existentes = {b["Name"] for b in cliente.list_buckets().get("Buckets", [])}
    for bucket in [BUCKET_RAW, BUCKET_CLEAN]:
        if bucket not in buckets_existentes:
            cliente.create_bucket(Bucket=bucket)
            print(f"[storage] Bucket creado en MinIO: {bucket}")


def _generar_path_raw(nombre_archivo: str) -> str:
    """
    Genera la ruta de destino en la zona raw/ con convención de fecha.
    Formato: raw/YYYY/MM/DD/pedidos_<uuid>.csv
    """
    hoy = datetime.utcnow()
    # Si el nombre no tiene UUID, generamos uno
    nombre_base = nombre_archivo.rsplit(".", 1)[0]
    extension = nombre_archivo.rsplit(".", 1)[-1] if "." in nombre_archivo else "csv"
    return f"raw/{hoy.year}/{hoy.month:02d}/{hoy.day:02d}/{nombre_base}_{uuid.uuid4()}.{extension}"


def _generar_path_clean(nombre_archivo: str) -> str:
    """
    Genera la ruta de destino en la zona clean/ con convención de fecha.
    Formato: clean/YYYY/MM/DD/pedidos_clean_<uuid>.csv
    """
    hoy = datetime.utcnow()
    nombre_base = nombre_archivo.rsplit(".", 1)[0]
    extension = nombre_archivo.rsplit(".", 1)[-1] if "." in nombre_archivo else "csv"
    return f"clean/{hoy.year}/{hoy.month:02d}/{hoy.day:02d}/{nombre_base}_clean_{uuid.uuid4()}.{extension}"


# ---------------------------------------------------------------------------
# Funciones públicas de almacenamiento
# ---------------------------------------------------------------------------

def subir_raw(contenido_csv: bytes, nombre_archivo: str) -> str:
    """
    Sube un CSV al bucket raw/.
    Retorna el path completo dentro del bucket (ej: raw/2025/01/15/pedidos_<uuid>.csv).
    """
    cliente = get_s3_client()
    path = _generar_path_raw(nombre_archivo)
    cliente.put_object(
        Bucket=BUCKET_RAW,
        Key=path,
        Body=contenido_csv,
        ContentType="text/csv",
    )
    print(f"[storage] CSV subido a raw: s3://{BUCKET_RAW}/{path}")
    return path


def descargar_raw(path: str) -> bytes:
    """
    Descarga un archivo del bucket raw/ dado su path.
    Retorna el contenido como bytes.
    """
    cliente = get_s3_client()
    respuesta = cliente.get_object(Bucket=BUCKET_RAW, Key=path)
    contenido = respuesta["Body"].read()
    print(f"[storage] CSV descargado de raw: {path} ({len(contenido)} bytes)")
    return contenido


def subir_clean(contenido_csv: bytes, nombre_archivo: str) -> str:
    """
    Sube un CSV limpio al bucket clean/.
    Retorna el path completo dentro del bucket.
    """
    cliente = get_s3_client()
    path = _generar_path_clean(nombre_archivo)
    cliente.put_object(
        Bucket=BUCKET_CLEAN,
        Key=path,
        Body=contenido_csv,
        ContentType="text/csv",
    )
    print(f"[storage] CSV limpio subido a clean: s3://{BUCKET_CLEAN}/{path}")
    return path


def descargar_clean(path: str) -> bytes:
    """
    Descarga un archivo del bucket clean/ dado su path.
    Retorna el contenido como bytes.
    """
    cliente = get_s3_client()
    respuesta = cliente.get_object(Bucket=BUCKET_CLEAN, Key=path)
    contenido = respuesta["Body"].read()
    print(f"[storage] CSV descargado de clean: {path} ({len(contenido)} bytes)")
    return contenido

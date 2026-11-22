"""
preparar_datos.py
=================
Script de preparación de datos para el contenedor del tablero.
Genera los pedidos simulados y aplica la limpieza con semilla fija si
el CSV limpio no existe localmente. Luego sube el archivo limpio a MinIO
(zona clean/) para que el tablero y el worker lo encuentren.

Se ejecuta automáticamente al arrancar el contenedor del tablero
si falta data/clean/pedidos_clean.csv.

Uso:
    python scripts/preparar_datos.py
"""

import io
import os
import sys
from pathlib import Path

# ── Raíz del proyecto ─────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

RAW_PATH   = ROOT_DIR / "data" / "raw"   / "pedidos_raw.csv"
CLEAN_PATH = ROOT_DIR / "data" / "clean" / "pedidos_clean.csv"
CLEAN_KEY  = "clean/pedidos_clean.csv"


def _necesita_generar() -> bool:
    """Devuelve True si falta el CSV limpio local."""
    return not CLEAN_PATH.exists()


def generar_y_limpiar() -> None:
    """
    Genera pedidos_raw.csv con la semilla fija del simulador (SEED=42)
    y aplica los 5 pilares de limpieza para producir pedidos_clean.csv.
    """
    print("[preparar_datos] Generando pedidos sintéticos con SEED=42…")
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Importar el simulador y ejecutar las funciones principales
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generar_pedidos",
        ROOT_DIR / "data" / "raw" / "generar_pedidos.py",
    )
    gen_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen_mod)

    # Generar datos y guardar como en __main__ del simulador
    df_base = gen_mod.generar_pedidos()
    df_con_errores, _ = gen_mod.sembrar_errores(df_base)
    df_con_errores.to_csv(str(RAW_PATH), index=False, encoding="utf-8")

    if not RAW_PATH.exists():
        raise FileNotFoundError(f"El simulador no generó {RAW_PATH}")

    print(f"[preparar_datos] pedidos_raw.csv generado ({RAW_PATH.stat().st_size:,} bytes)")

    # Aplicar limpieza
    print("[preparar_datos] Aplicando 5 pilares de limpieza…")
    from services.worker.limpieza import limpiar_pedidos
    df_clean, reporte = limpiar_pedidos(str(RAW_PATH), str(CLEAN_PATH))
    print(
        f"[preparar_datos] Limpieza completa → "
        f"{reporte.get('n_registros_clean', '?')} filas limpias, "
        f"{reporte.get('n_pedidos_unicos_clean', '?')} pedidos únicos en {CLEAN_PATH}"
    )


def subir_a_minio(ruta_local: Path) -> None:
    """
    Sube pedidos_clean.csv al bucket de MinIO (zona clean/).
    Si MinIO no está disponible, solo avisa y continúa.
    """
    endpoint   = os.getenv("MINIO_ENDPOINT", "")
    access_key = os.getenv("MINIO_ACCESS_KEY", "")
    secret_key = os.getenv("MINIO_SECRET_KEY", "")
    bucket     = os.getenv("MINIO_BUCKET_CLEAN", "taqueria-clean")

    if not (endpoint and access_key and secret_key):
        print("[preparar_datos] MINIO_ENDPOINT no definido; se omite subida a MinIO.")
        return

    try:
        import boto3
        from botocore.client import Config
        from services.pedidos.storage import asegurar_buckets

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        # Crear buckets si no existen
        asegurar_buckets(s3)

        with open(ruta_local, "rb") as f:
            contenido = f.read()

        s3.put_object(
            Bucket=bucket,
            Key=CLEAN_KEY,
            Body=contenido,
            ContentType="text/csv",
        )
        print(f"[preparar_datos] Subido a MinIO: s3://{bucket}/{CLEAN_KEY} ({len(contenido):,} bytes)")
    except Exception as exc:
        print(f"[preparar_datos] Aviso: no se pudo subir a MinIO ({exc}). Se usará el archivo local.")


def main() -> None:
    if _necesita_generar():
        generar_y_limpiar()
    else:
        print(f"[preparar_datos] {CLEAN_PATH} ya existe; se omite regeneración.")

    # Siempre intentar subir a MinIO (para que el tablero en otros contenedores lo encuentre)
    if CLEAN_PATH.exists():
        subir_a_minio(CLEAN_PATH)
    else:
        print("[preparar_datos] ⚠ CLEAN_PATH no existe tras la preparación; algo falló.")
        sys.exit(1)


if __name__ == "__main__":
    main()

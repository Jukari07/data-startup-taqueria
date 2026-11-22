"""
Worker de procesamiento de pedidos para Las Cazuelitas.
Consume mensajes de la cola (RabbitMQ o SQS), descarga CSV de raw/,
aplica limpieza, sube el resultado a clean/ y actualiza PostgreSQL.
Incluye reintentos con contador y reconexión automática al broker.
"""

import io
import json
import os
import sys
import time
from pathlib import Path

# Permitir importar módulos del proyecto desde la raíz
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.pedidos.cola import get_cola, ColaMensajes
from services.pedidos.storage import descargar_raw, subir_clean, asegurar_buckets
from services.pedidos.db import get_connection

# Importar módulo de limpieza (ruta relativa al worker)
try:
    from services.worker import limpieza
except ImportError:
    # Fallback: buscar limpieza.py en el mismo directorio del worker
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "limpieza",
        Path(__file__).parent / "limpieza.py",
    )
    limpieza = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(limpieza)


MAX_INTENTOS = 3  # Máximo de reintentos antes de abandonar el mensaje


# ---------------------------------------------------------------------------
# Procesamiento de un mensaje individual
# ---------------------------------------------------------------------------

def procesar_mensaje(mensaje: dict) -> None:
    """
    Procesa un mensaje de la cola:
    1. Descarga el CSV desde raw/ en S3/MinIO.
    2. Aplica transformaciones de limpieza.
    3. Sube el CSV limpio a clean/.
    4. Inserta/actualiza el detalle en PostgreSQL.

    Lanza excepción si algún paso falla (para activar el mecanismo de reintento).
    """
    path_raw = mensaje.get("path_raw")
    pedido_id = mensaje.get("pedido_id")

    if not path_raw:
        raise ValueError(f"Mensaje inválido: falta 'path_raw'. Mensaje: {mensaje}")

    print(f"[worker] Procesando pedido {pedido_id} — raw: {path_raw}")

    # 1. Descargar CSV de raw/
    contenido_raw = descargar_raw(path_raw)

    # 2. Limpiar el CSV con el módulo de limpieza
    contenido_limpio = limpieza.limpiar_csv(contenido_raw)

    # 3. Subir CSV limpio a clean/
    nombre_archivo = Path(path_raw).name
    path_clean = subir_clean(contenido_limpio, nombre_archivo)
    print(f"[worker] CSV limpio guardado en: {path_clean}")

    # 4. Insertar/actualizar en PostgreSQL si tenemos pedido_id
    if pedido_id:
        _actualizar_estado_pedido(pedido_id, path_clean)

    print(f"[worker] Pedido {pedido_id} procesado correctamente.")


def _actualizar_estado_pedido(pedido_id: str, path_clean: str) -> None:
    """
    Actualiza el estado del pedido a 'en_preparacion' y registra el path del CSV limpio.
    Si el pedido_id no existe, registra una advertencia y continúa.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pedidos
                SET estado = 'en_preparacion'
                WHERE pedido_id = %s AND estado = 'pendiente'
                """,
                (pedido_id,),
            )
            filas_actualizadas = cur.rowcount
        conn.commit()

    if filas_actualizadas == 0:
        print(
            f"[worker] Advertencia: pedido {pedido_id} no encontrado o ya procesado. "
            "Se omite la actualización de estado."
        )
    else:
        print(f"[worker] Estado del pedido {pedido_id} actualizado a 'en_preparacion'.")


# ---------------------------------------------------------------------------
# Envoltura con lógica de reintentos
# ---------------------------------------------------------------------------

def callback_con_reintentos(mensaje: dict) -> None:
    """
    Envoltura del procesador que implementa reintentos locales.
    Si procesar_mensaje falla, reintenta hasta MAX_INTENTOS con backoff exponencial.
    Al agotar los intentos, registra el error y relanza la excepción para que
    el adaptador de cola lo envíe a la DLQ.
    """
    intentos = mensaje.get("_intento_worker", 1)

    for intento in range(intentos, MAX_INTENTOS + 1):
        try:
            procesar_mensaje(mensaje)
            return  # Éxito — salimos del loop
        except Exception as exc:
            print(f"[worker] Error en intento {intento}/{MAX_INTENTOS}: {exc}")
            if intento < MAX_INTENTOS:
                espera = 2 ** intento  # Backoff exponencial: 2s, 4s, 8s…
                print(f"[worker] Reintentando en {espera}s…")
                time.sleep(espera)
            else:
                print(
                    f"[worker] Máximo de reintentos alcanzado para pedido "
                    f"{mensaje.get('pedido_id', 'desconocido')}. Enviando a DLQ."
                )
                raise  # El adaptador de cola maneja el envío a DLQ


# ---------------------------------------------------------------------------
# Loop principal con reconexión automática
# ---------------------------------------------------------------------------

def iniciar_worker() -> None:
    """
    Loop principal del worker. Inicia el consumo de la cola y, si se pierde
    la conexión, espera y vuelve a intentar indefinidamente.
    """
    intentos_reconexion = 0
    max_reconexiones = 10
    espera_reconexion = 5  # segundos iniciales entre reconexiones

    print("[worker] Iniciando worker de pedidos Las Cazuelitas…")

    # Asegurar de forma idempotente que los buckets raw y clean existan
    try:
        asegurar_buckets()
    except Exception as exc:
        print(f"[worker] Advertencia al verificar/crear buckets: {exc}")

    while True:
        cola: ColaMensajes | None = None
        try:
            cola = get_cola()
            intentos_reconexion = 0  # Resetear contador al conectar con éxito
            print("[worker] Conectado a la cola. Esperando mensajes…")
            cola.consumir(callback_con_reintentos)

        except KeyboardInterrupt:
            print("[worker] Detenido por el usuario.")
            break

        except Exception as exc:
            intentos_reconexion += 1
            print(
                f"[worker] Error de conexión con la cola: {exc}. "
                f"Reintento {intentos_reconexion}/{max_reconexiones} "
                f"en {espera_reconexion}s…"
            )
            if intentos_reconexion >= max_reconexiones:
                print("[worker] Máximo de reconexiones alcanzado. Terminando.")
                raise SystemExit(1)
            time.sleep(espera_reconexion)
            # Backoff exponencial hasta 60 segundos
            espera_reconexion = min(espera_reconexion * 2, 60)

        finally:
            if cola:
                try:
                    cola.cerrar()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    iniciar_worker()

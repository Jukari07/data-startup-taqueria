"""
Módulo de cola de mensajes para Las Cazuelitas.
Soporta dos backends: RabbitMQ (local/dev) y SQS (AWS/producción).
El backend se selecciona con la variable de entorno QUEUE_BACKEND.
"""

import json
import os
import time
from abc import ABC, abstractmethod
from typing import Callable

import pika
import boto3


# ---------------------------------------------------------------------------
# Clase base abstracta
# ---------------------------------------------------------------------------

class ColaMensajes(ABC):
    """
    Interfaz común para los adaptadores de cola de mensajes.
    Todos los backends deben implementar publicar, consumir y cerrar.
    """

    @abstractmethod
    def publicar(self, mensaje: dict) -> None:
        """Serializa y publica un mensaje en la cola."""
        ...

    @abstractmethod
    def consumir(self, callback: Callable[[dict], None]) -> None:
        """
        Inicia el consumo de mensajes de la cola.
        Por cada mensaje recibido invoca callback(mensaje_dict).
        Bloqueante: no retorna hasta que se llame a cerrar() o se lance excepción.
        """
        ...

    @abstractmethod
    def cerrar(self) -> None:
        """Cierra la conexión con el broker de mensajería."""
        ...


# ---------------------------------------------------------------------------
# Adaptador RabbitMQ (pika) — para desarrollo local
# ---------------------------------------------------------------------------

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
COLA_PRINCIPAL = "taqueria.pedidos"
COLA_DLQ = "taqueria.pedidos.dlq"
MAX_INTENTOS = 3  # Máximo de reintentos antes de enviar a DLQ


class ColaRabbitMQ(ColaMensajes):
    """
    Adaptador de RabbitMQ usando la librería pika.

    - Cola principal: taqueria.pedidos (durable, mensajes persistentes)
    - DLQ: taqueria.pedidos.dlq (recibe mensajes fallidos)
    - Reintentos: se rastrea en el header x-attempt; al llegar a MAX_INTENTOS
      el mensaje se publica en la DLQ y se descarta de la cola principal.
    """

    def __init__(self):
        # Parámetros de conexión con reconexión automática en bloqueos
        parametros = pika.URLParameters(RABBITMQ_URL)
        parametros.heartbeat = 60
        parametros.blocked_connection_timeout = 300

        self._conexion = pika.BlockingConnection(parametros)
        self._canal = self._conexion.channel()

        # Declarar DLQ primero (debe existir antes de referenciarla)
        self._canal.queue_declare(queue=COLA_DLQ, durable=True)

        # Declarar la cola principal con referencia a la DLQ
        self._canal.queue_declare(
            queue=COLA_PRINCIPAL,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": COLA_DLQ,
            },
        )

    def publicar(self, mensaje: dict) -> None:
        """
        Publica un mensaje JSON en la cola principal con delivery_mode=2
        (persistente: sobrevive reinicios del broker).
        """
        cuerpo = json.dumps(mensaje, ensure_ascii=False)
        self._canal.basic_publish(
            exchange="",
            routing_key=COLA_PRINCIPAL,
            body=cuerpo.encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=2,            # Mensaje persistente
                content_type="application/json",
                headers={"x-attempt": 1},  # Primer intento
            ),
        )
        print(f"[cola] Mensaje publicado en {COLA_PRINCIPAL}: {list(mensaje.keys())}")

    def _publicar_en_dlq(self, mensaje: dict, intento: int) -> None:
        """Envía un mensaje fallido a la Dead Letter Queue."""
        cuerpo = json.dumps(mensaje, ensure_ascii=False)
        self._canal.basic_publish(
            exchange="",
            routing_key=COLA_DLQ,
            body=cuerpo.encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                headers={"x-attempt": intento, "x-motivo": "maximo_reintentos"},
            ),
        )
        print(f"[cola] Mensaje enviado a DLQ tras {intento} intentos.")

    def consumir(self, callback: Callable[[dict], None]) -> None:
        """
        Escucha mensajes de la cola principal. Para cada mensaje:
        - Deserializa el JSON.
        - Invoca el callback.
        - Si el callback falla, reencola hasta MAX_INTENTOS, luego DLQ.
        """

        def _on_message(ch, method, properties, body):
            # Número de intento actual (empieza en 1)
            intento = (properties.headers or {}).get("x-attempt", 1)
            try:
                mensaje = json.loads(body.decode("utf-8"))
                callback(mensaje)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print(f"[cola] Mensaje procesado correctamente (intento {intento}).")
            except Exception as exc:
                print(f"[cola] Error al procesar mensaje (intento {intento}): {exc}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                if intento < MAX_INTENTOS:
                    # Reencolar con contador incrementado
                    mensaje_dict = json.loads(body.decode("utf-8"))
                    cuerpo_reencola = json.dumps(mensaje_dict).encode("utf-8")
                    ch.basic_publish(
                        exchange="",
                        routing_key=COLA_PRINCIPAL,
                        body=cuerpo_reencola,
                        properties=pika.BasicProperties(
                            delivery_mode=2,
                            content_type="application/json",
                            headers={"x-attempt": intento + 1},
                        ),
                    )
                    print(f"[cola] Reencolado para intento {intento + 1}.")
                else:
                    # Máximo de reintentos alcanzado → DLQ
                    self._publicar_en_dlq(json.loads(body.decode("utf-8")), intento)

        # Procesar de uno en uno (fair dispatch)
        self._canal.basic_qos(prefetch_count=1)
        self._canal.basic_consume(queue=COLA_PRINCIPAL, on_message_callback=_on_message)
        print(f"[cola] Escuchando mensajes en {COLA_PRINCIPAL}...")
        self._canal.start_consuming()

    def cerrar(self) -> None:
        """Cierra el canal y la conexión con RabbitMQ."""
        try:
            if self._canal.is_open:
                self._canal.close()
            if self._conexion.is_open:
                self._conexion.close()
        except Exception as exc:
            print(f"[cola] Error al cerrar conexión RabbitMQ: {exc}")


# ---------------------------------------------------------------------------
# Adaptador SQS (boto3) — para producción en AWS
# ---------------------------------------------------------------------------

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")
SQS_DLQ_URL = os.getenv("SQS_DLQ_URL", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


class ColaSQS(ColaMensajes):
    """
    Adaptador de Amazon SQS usando boto3.

    - Long polling con WaitTimeSeconds=20 para reducir costos.
    - La política de redrive (MaxReceiveCount) se configura en Terraform;
      los mensajes fallidos van automáticamente a la DLQ de SQS.
    - Publicar con MessageBody=json.dumps(mensaje).
    """

    def __init__(self):
        self._cliente = boto3.client("sqs", region_name=AWS_REGION)
        if not SQS_QUEUE_URL:
            raise EnvironmentError(
                "Variable de entorno SQS_QUEUE_URL no definida. "
                "Revisa tu archivo .env o la configuración de ECS."
            )

    def publicar(self, mensaje: dict) -> None:
        """
        Publica un mensaje en la cola SQS.
        El cuerpo del mensaje es el JSON serializado del dict.
        """
        respuesta = self._cliente.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(mensaje, ensure_ascii=False),
        )
        print(f"[cola-sqs] Mensaje publicado. MessageId: {respuesta['MessageId']}")

    def consumir(self, callback: Callable[[dict], None]) -> None:
        """
        Polling largo de mensajes SQS (WaitTimeSeconds=20).
        Para cada mensaje invoca el callback y luego lo elimina de la cola.
        Los reintentos y la redirección a DLQ son gestionados por la
        política de redrive configurada en Terraform (MaxReceiveCount).
        """
        print(f"[cola-sqs] Iniciando consumo long-poll de {SQS_QUEUE_URL}")
        while True:
            respuesta = self._cliente.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,          # Long polling → menos llamadas vacías
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )
            mensajes = respuesta.get("Messages", [])
            if not mensajes:
                continue  # Sin mensajes, seguir esperando

            for sqs_msg in mensajes:
                receipt_handle = sqs_msg["ReceiptHandle"]
                try:
                    mensaje = json.loads(sqs_msg["Body"])
                    callback(mensaje)
                    # Eliminar de la cola solo si el callback fue exitoso
                    self._cliente.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=receipt_handle,
                    )
                    print(f"[cola-sqs] Mensaje procesado y eliminado: {sqs_msg['MessageId']}")
                except Exception as exc:
                    # No eliminamos el mensaje → SQS lo reintentará
                    # Al superar MaxReceiveCount, va a la DLQ automáticamente
                    print(
                        f"[cola-sqs] Error procesando mensaje {sqs_msg['MessageId']}: {exc}. "
                        "El mensaje será reintentado por SQS."
                    )

    def cerrar(self) -> None:
        """SQS no mantiene conexiones persistentes; noop."""
        pass


# ---------------------------------------------------------------------------
# Fábrica de cola
# ---------------------------------------------------------------------------

def get_cola() -> ColaMensajes:
    """
    Fábrica que retorna el adaptador de cola correcto según la variable
    de entorno QUEUE_BACKEND.

    - QUEUE_BACKEND=rabbitmq (default) → ColaRabbitMQ
    - QUEUE_BACKEND=sqs               → ColaSQS
    """
    backend = os.getenv("QUEUE_BACKEND", "rabbitmq").lower()
    if backend == "sqs":
        print("[cola] Usando backend: AWS SQS")
        return ColaSQS()
    print("[cola] Usando backend: RabbitMQ")
    return ColaRabbitMQ()

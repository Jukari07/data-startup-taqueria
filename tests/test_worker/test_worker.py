"""
test_worker.py
==============
Pruebas para el worker y los adaptadores de almacenamiento y cola.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

import services.pedidos.cola as cola_module
from services.pedidos.cola import get_cola, ColaRabbitMQ, ColaSQS
from services.worker.worker import MAX_INTENTOS


def test_max_reintentos_worker():
    """Valida que el worker esté configurado con exactamente 3 reintentos antes de DLQ."""
    assert MAX_INTENTOS == 3


def test_adaptador_cola_rabbitmq(monkeypatch):
    """Valida que get_cola devuelva ColaRabbitMQ por defecto con sus nombres de colas."""
    monkeypatch.setenv("QUEUE_BACKEND", "rabbitmq")
    
    with patch("pika.BlockingConnection") as mock_conn:
        mock_canal = MagicMock()
        mock_conn.return_value.channel.return_value = mock_canal
        cola = get_cola()
        assert isinstance(cola, ColaRabbitMQ)
        assert cola_module.COLA_PRINCIPAL == "taqueria.pedidos"
        assert cola_module.COLA_DLQ == "taqueria.pedidos.dlq"


def test_adaptador_cola_sqs(monkeypatch):
    """Valida que get_cola devuelva ColaSQS cuando QUEUE_BACKEND=sqs."""
    monkeypatch.setenv("QUEUE_BACKEND", "sqs")
    monkeypatch.setattr(cola_module, "SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/taqueria-pedidos")
    monkeypatch.setattr(cola_module, "SQS_DLQ_URL", "https://sqs.us-east-1.amazonaws.com/123/taqueria-pedidos-dlq")
    
    with patch("boto3.client") as mock_boto:
        cola = get_cola()
        assert isinstance(cola, ColaSQS)
        assert cola_module.SQS_QUEUE_URL == "https://sqs.us-east-1.amazonaws.com/123/taqueria-pedidos"

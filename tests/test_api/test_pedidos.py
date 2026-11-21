"""
test_pedidos.py
===============
Pruebas para la API de pedidos y autenticación de Las Cazuelitas.
"""

import io
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from services.pedidos.main import (
    app,
    hashear_password,
    verificar_password,
    crear_token_jwt,
    JWT_SECRET,
    JWT_ALGORITHM,
    ItemPedido,
    CrearPedido,
)

client = TestClient(app)


def test_health_check():
    """Valida que el endpoint /health responda status 200 y status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_hashear_y_verificar_password():
    """Valida el hashing seguro con bcrypt y su verificación."""
    password = "TacosDeliciosos123!"
    hashed = hashear_password(password)

    assert hashed != password
    assert verificar_password(password, hashed) is True
    assert verificar_password("PasswordErroneo", hashed) is False


def test_crear_y_decodificar_jwt():
    """Valida la generación de tokens JWT con expiración."""
    payload = {"sub": "user-12345", "email": "rocio@cazuelitas.mx", "rol": "admin"}
    token = crear_token_jwt(payload)

    assert isinstance(token, str)
    decodificado = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert decodificado["sub"] == "user-12345"
    assert decodificado["email"] == "rocio@cazuelitas.mx"
    assert "exp" in decodificado


def test_modelos_pydantic_validos():
    """Valida la estructura de los modelos Pydantic de pedidos."""
    item = ItemPedido(producto_id=1, cantidad=3, salsa="verde")
    assert item.producto_id == 1
    assert item.cantidad == 3
    assert item.salsa == "verde"

    pedido = CrearPedido(
        tipo_entrega="domicilio",
        notas="Poner bastante limón y salsa verde",
        items=[item]
    )
    assert pedido.tipo_entrega == "domicilio"
    assert len(pedido.items) == 1


def test_crear_pedido_sin_auth_falla():
    """Valida que el endpoint protegido /pedidos rechace solicitudes sin token Bearer."""
    payload = {
        "tipo_entrega": "llevar",
        "items": [{"producto_id": 1, "cantidad": 2, "salsa": "roja"}]
    }
    response = client.post("/pedidos", json=payload)
    assert response.status_code in {401, 403}


def test_ingesta_csv_sin_token_falla():
    """Valida que /ingesta/csv rechace solicitudes con token inválido o sin cabecera X-API-Token."""
    archivo_csv = io.BytesIO(b"folio,fecha,total\n1,2024-01-01,100")
    response = client.post(
        "/ingesta/csv",
        files={"archivo": ("pedidos.csv", archivo_csv, "text/csv")},
        headers={"X-API-Token": "token_invalido"}
    )
    assert response.status_code == 401

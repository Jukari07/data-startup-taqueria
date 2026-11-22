"""
locustfile.py
=============
Script de prueba de carga con Locust para la API de Tacos Las Cazuelitas.
Simula el comportamiento de 50 comensales concurrentes realizando pedidos
en línea en horas pico de atención (7:00 a 10:00 a.m.).

Métricas objetivo:
  - Latencia percentil 95 (p95) < 500 ms
  - Tasa de errores < 1 %
  - Throughput sostenido > 25 req/s
"""

import json
import random
from locust import HttpUser, task, between


class ComensalLasCazuelitas(HttpUser):
    """
    Simula un cliente que consulta el menú, inicia sesión y realiza pedidos
    en la plataforma de Tacos Las Cazuelitas.
    """
    wait_time = between(1, 3)  # Tiempo de espera realista entre acciones del usuario

    def on_start(self):
        """Inicializa sesión simulada y obtiene token de autenticación."""
        self.email = f"cliente_{random.randint(1000, 9999)}@correo.com"
        self.password = "PasswordCliente123!"
        self.token = None

        # Intentar registro o login simulado
        res_registro = self.client.post("/auth/registro", json={
            "nombre": f"Cliente {random.randint(10, 99)}",
            "email": self.email,
            "password": self.password,
        })
        if res_registro.status_code == 201:
            self.token = res_registro.json().get("token")
        else:
            # Si ya existía, hacer login
            res_login = self.client.post("/auth/login", json={
                "email": self.email,
                "password": self.password,
            })
            if res_login.status_code == 200:
                self.token = res_login.json().get("token")

    @task(10)
    def verificar_salud(self):
        """Verificación de salud del endpoint (Keep-alive)."""
        self.client.get("/health", name="[GET] /health")

    @task(25)
    def consultar_menu(self):
        """Comensal navegando y revisando los guisados y bebidas disponibles."""
        self.client.get("/menu", name="[GET] /menu")

    @task(35)
    def crear_pedido_tacos(self):
        """Comensal armando su pedido con guisados y bebidas."""
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        # Guisados comunes (IDs 1 al 8) y bebidas (IDs 9 al 14)
        items = [
            {
                "producto_id": random.choice([1, 2, 3, 4, 5]),  # Guisados populares
                "cantidad": random.randint(1, 4),
                "salsa": random.choice(["verde", "roja"]),
            },
            {
                "producto_id": random.choice([9, 10, 11]),      # Bebida
                "cantidad": 1,
                "salsa": "sin_salsa",
            }
        ]

        tipo_entrega = random.choices(["aqui", "domicilio", "llevar"], weights=[50, 40, 10])[0]

        payload = {
            "tipo_entrega": tipo_entrega,
            "notas": "Salsa aparte por favor",
            "items": items,
        }

        self.client.post(
            "/pedidos",
            json=payload,
            headers=headers,
            name="[POST] /pedidos",
        )

    @task(5)
    def consultar_historial_pedidos(self):
        """Comensal o dueña revisando el estado de sus pedidos."""
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get("/pedidos", headers=headers, name="[GET] /pedidos")

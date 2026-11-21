# Tacos Las Cazuelitas – Plataforma de Pedidos y Analítica

> Sistema integral para la taquería **Las Cazuelitas**: toma de pedidos en mostrador/domicilio,
> procesamiento asíncrono con cola de mensajes, almacenamiento de datos en la nube (MinIO/S3),
> modelos predictivos de demanda y un tablero de analítica en tiempo real construido con Streamlit.

---

## Entregables del proyecto

| ID  | Entregable                             | Descripción                                              | Estado       |
|-----|----------------------------------------|----------------------------------------------------------|--------------|
| E0  | Infraestructura base                   | Repo, Docker Compose, esquema PostgreSQL, CI             | ✅ Completo  |
| E1  | API de pedidos + worker                | FastAPI, cola RabbitMQ/SQS, ingesta a MinIO              | 🔄 En curso  |
| E2  | Tablero de analítica                   | Dashboard Streamlit: ventas, productos, pronóstico       | 🔄 En curso  |
| E3  | Modelos predictivos                    | ARIMA/SARIMA para demanda diaria, servido via FastAPI    | ⏳ Pendiente |

---

## Prerequisitos

| Herramienta        | Versión mínima | Notas                                      |
|--------------------|----------------|--------------------------------------------|
| Docker Desktop     | 4.x            | Con Docker Compose v2 integrado            |
| Python             | 3.11+          | Solo necesario para desarrollo local sin contenedor |
| Git                | 2.x            | —                                          |

---

## Quickstart

```bash
# 1. Clona el repositorio
git clone <url-del-repo>
cd data-startup-taqueria

# 2. Configura las variables de entorno
cp .env.example .env
# Edita .env y cambia los valores marcados como "cambia_esto"

# 3. Levanta todos los servicios
docker-compose up --build

# 4. Accede a los servicios
#    Tablero Streamlit  → http://localhost:8501
#    API de pedidos     → http://localhost:8000/docs
#    Servicio modelos   → http://localhost:8001/docs
#    MinIO consola      → http://localhost:9001
#    RabbitMQ admin     → http://localhost:15672
```

---

## Estructura de carpetas

```
data-startup-taqueria/
├── .devcontainer/
│   └── devcontainer.json        # Entorno de desarrollo reproducible
├── db/
│   └── migrations/
│       ├── 001_schema_inicial.sql
│       └── 002_seed_productos.sql
├── infra/
│   └── terraform/               # IaC para despliegue en nube (E3+)
├── notebooks/                   # Análisis EDA (Jupyter)
├── services/
│   ├── pedidos/                 # API REST FastAPI (pedidos)
│   │   └── Dockerfile
│   ├── worker/                  # Consumidor de cola (procesamiento)
│   │   └── Dockerfile
│   ├── modelos/                 # Servicio de predicción ARIMA
│   │   └── Dockerfile
│   └── tablero/                 # Dashboard Streamlit
│       ├── Dashboard.py
│       └── Dockerfile
├── tests/                       # Suite de pruebas (pytest)
├── data/
│   └── sample/                  # CSVs de muestra (sí trackeados en git)
├── models/                      # Modelos entrenados (*.pkl excluidos en git)
├── .env.example
├── .gitignore
├── docker-compose.yml
├── pytest.ini
├── requirements.txt
├── requirements-eda.txt
├── requirements-pipeline.txt
├── requirements-modelos.txt
├── streamlit_app.py             # Punto de entrada para Streamlit Cloud
└── README.md
```

---

## Desarrollo local sin Docker

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

---

## Pruebas

```bash
# Ejecuta todos los tests con reporte corto
pytest

# Con cobertura
pip install pytest-cov
pytest --cov=services --cov-report=term-missing
```

---

## Uso de IA generativa

Este proyecto fue desarrollado con asistencia de **Antigravity (Google Gemini)** para:

- Generación del scaffolding inicial (estructura de carpetas, archivos de configuración, esquema SQL).
- Revisión de patrones de arquitectura para sistemas de pedidos con colas de mensajes.
- Sugerencias de versiones de dependencias compatibles entre sí.

**Todo el código generado fue revisado, probado y validado por el equipo humano** antes de integrarse al repositorio. La IA actúa como asistente de productividad, no como autor final.

---

## Licencia

Uso interno — Tacos Las Cazuelitas © 2024. Todos los derechos reservados.

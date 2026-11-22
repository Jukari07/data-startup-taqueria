# Tacos Las Cazuelitas – Plataforma de Pedidos y Analítica

> Sistema integral para la taquería **Las Cazuelitas**: toma de pedidos en mostrador/domicilio,
> procesamiento asíncrono con cola de mensajes, almacenamiento de datos en la nube (MinIO/S3),
> modelos predictivos de demanda y un tablero de analítica en tiempo real construido con Streamlit.

---

## Entregables del proyecto

| ID  | Entregable                             | Descripción                                              | Estado       |
|-----|----------------------------------------|----------------------------------------------------------|--------------|
| E0  | Propuesta de Negocio & Nube Base       | Propuesta de valor, presupuesto $0, IAM, MFA, repo, CI   | ✅ Completo  |
| E1  | Tablero Analítico & Calidad de Datos   | Dashboard Streamlit, 5 pilares limpieza, EDA, calibración| ✅ Completo  |
| E2  | Arquitectura Cloud & Series de Tiempo  | API FastAPI, Worker RabbitMQ/SQS, RDS/MinIO, OLS manual  | ✅ Completo  |
| E3  | Producción, MLOps & Resiliencia        | Docker multi-stage, K8s, Terraform, Locust, SARIMA/Churn| ✅ Completo  |

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
│   └── devcontainer.json        # Entorno reproducible (Python 3.11 + Docker-in-Docker)
├── data/
│   ├── raw/generar_pedidos.py   # Generador calibrado con entrevista de Doña Rocío
│   ├── clean/                   # Dataset limpio y reporte JSON de calidad
│   └── sample/                  # Muestra representativa trackeada en git
├── db/migrations/               # Migraciones PostgreSQL (DDL + catálogo)
├── docs/                        # Entregables E0, E1, E2, E3 y evidencias IAM/Presupuesto
├── infra/
│   ├── terraform/               # IaC para AWS (S3, SQS, IAM)
│   ├── lambda_worker/           # Handler AWS Lambda con soporte batch failure
│   └── *.json                   # Políticas IAM de despliegue y worker
├── k8s/                         # Manifiestos Kubernetes (HPA, Deployment, Service, Secrets)
├── notebooks/                   # EDA reproducible en Jupyter (01_eda_pedidos.ipynb)
├── services/
│   ├── pedidos/                 # API REST FastAPI (pedidos, auth JWT/bcrypt, S3/SQS)
│   ├── worker/                  # Consumidor asíncrono con reintentos y DLQ
│   ├── modelos/                 # Servicio de inferencia ML (SARIMA + Churn)
│   ├── analitica/               # OLS manual por ecuación normal y series de tiempo
│   ├── ingesta/                 # Ingesta masiva de CSV a cola/S3
│   └── tablero/                 # Dashboard Streamlit v1 y v3
├── tests/                       # Suite automatizada (23 pruebas unitarias y de integración)
│   ├── test_limpieza/
│   ├── test_api/
│   ├── test_worker/
│   ├── test_analitica/
│   └── locust/                  # Pruebas de carga (50 usuarios concurrentes)
├── .env.example
├── .gitignore
├── docker-compose.yml
├── pytest.ini
├── requirements.txt
├── requirements-eda.txt
├── requirements-pipeline.txt
├── requirements-modelos.txt
├── streamlit_app.py             # Punto de entrada para Streamlit
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

## Variables de entorno: localhost vs. Docker

> [!IMPORTANT]
> `.env.example` usa `localhost` para todos los servicios. Esto es correcto cuando ejecutas la API, el worker o el tablero **directamente en tu máquina** (fuera de contenedores).
>
> Cuando usas `docker-compose up`, los contenedores se comunican por la **red interna de Docker** mediante los **nombres de servicio** (`minio`, `rabbitmq`, `postgres`). Las variables necesarias se definen directamente en la sección `environment` de cada servicio en `docker-compose.yml` y **sobreescriben** las del `.env` automáticamente.
>
> | Variable | Valor en `.env.example` (local sin Docker) | Valor en docker-compose (dentro de contenedor) |
> |---|---|---|
> | `POSTGRES_HOST` | `localhost` | `postgres` |
> | `MINIO_ENDPOINT` | `http://localhost:9000` | `http://minio:9000` |
> | `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/` | `amqp://guest:guest@rabbitmq:5672/` |
>
> **Nunca cambies** el `.env.example` a nombres de servicio: está pensado para uso local sin Docker.

---

## Datos y tablero sin conexión a MinIO

El tablero genera automáticamente los datos de muestra al arrancar si no encuentra
`data/clean/pedidos_clean.csv`. El script `scripts/preparar_datos.py`:

1. Genera `pedidos_raw.csv` usando el simulador con `SEED=42` (reproducible).
2. Aplica los 5 pilares de limpieza para producir `pedidos_clean.csv`.
3. Sube `pedidos_clean.csv` a MinIO (zona `clean/`) si está disponible.

El tablero siempre lee primero desde MinIO; si no está, usa el archivo local.

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

# ============================================================
# Dockerfile — Servicio de Modelos ML (services/modelos)
# Multi-stage: builder instala dependencias y entrena los modelos,
# runtime es una imagen ligera con usuario no-root.
# Los modelos .pkl se generan durante la construcción de la imagen
# para garantizar que siempre existan al arrancar el contenedor.
# ============================================================

# ── Stage 1: builder ────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gfortran \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de ML + pipeline (necesarias para entrenar)
COPY requirements-modelos.txt requirements-pipeline.txt requirements-eda.txt ./
RUN pip install --no-cache-dir --prefix=/install \
        -r requirements-modelos.txt \
        -r requirements-pipeline.txt \
        -r requirements-eda.txt

# ── Stage 2: entrenamiento de modelos ────────────────────────
FROM python:3.11-slim AS trainer

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/build

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Copiar código necesario para el entrenamiento
COPY services/modelos/ ./services/modelos/
COPY services/worker/limpieza.py ./services/worker/limpieza.py
COPY data/raw/generar_pedidos.py ./data/raw/generar_pedidos.py

# Crear directorios de salida
RUN mkdir -p data/raw data/clean data/sample models services/modelos/models

# Generar datos limpios con semilla fija (SEED=42) y entrenar modelos
# Si el entrenamiento falla, el build falla (no se sirve sin modelos)
RUN python data/raw/generar_pedidos.py && \
    python -c " \
import sys; sys.path.insert(0, '.'); \
from services.worker.limpieza import limpiar_pedidos; \
limpiar_pedidos('data/raw/pedidos_raw.csv', 'data/clean/pedidos_clean.csv'); \
print('[trainer] Datos limpios generados.');" && \
    python -m services.modelos.entrenar

# ── Stage 3: runtime ─────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar paquetes instalados desde el builder
COPY --from=builder /install /usr/local

# Crear usuario no-root por seguridad
RUN useradd --create-home --shell /bin/bash appuser

# Copiar código del servicio
COPY services/modelos/ ./services/modelos/

# Copiar modelos entrenados desde el stage trainer a AMBAS rutas que busca el código:
#   - services/modelos/models/  (DIR_MODELOS en main.py)
#   - models/                   (DIR_MODELOS_ROOT en entrenar.py)
COPY --from=trainer /build/models/ ./models/
COPY --from=trainer /build/services/modelos/models/ ./services/modelos/models/

# Asegurar permisos del usuario no-root
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

CMD ["uvicorn", "services.modelos.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "1"]

# ============================================================
# Dockerfile — Worker (services/worker)
# Procesa mensajes de la cola y ejecuta el pipeline ETL
# ============================================================

# ── Stage 1: builder ────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Solo instala las dependencias del pipeline (más ligero que la API completa)
COPY requirements-pipeline.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-pipeline.txt

# ── Stage 2: runtime ────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copiar paquetes instalados
COPY --from=builder /install /usr/local

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash appuser

# Copiar el código fuente necesario
COPY services/ ./services/
COPY db/ ./db/

USER appuser

# El worker se ejecuta como módulo Python para resolver imports correctamente
CMD ["python", "-m", "services.worker.worker"]

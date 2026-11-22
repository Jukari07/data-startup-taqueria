# ============================================================
# Dockerfile — Servicio de Modelos ML (services/modelos)
# Multi-stage: builder instala dependencias pesadas de ML,
# runtime es una imagen ligera con usuario no-root.
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

COPY requirements-modelos.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-modelos.txt

# ── Stage 2: runtime ────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copiar paquetes instalados desde el builder
COPY --from=builder /install /usr/local

# Crear usuario no-root por seguridad
RUN useradd --create-home --shell /bin/bash appuser

# Copiar código del servicio y modelos
COPY services/modelos/ ./services/modelos/
COPY models/ ./models/

# Asegurar permisos del usuario no-root
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

CMD ["uvicorn", "services.modelos.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "1"]

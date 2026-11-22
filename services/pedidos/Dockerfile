# ============================================================
# Dockerfile — Servicio API (services/pedidos)
# Multi-stage: builder instala dependencias, runtime es mínimo
# ============================================================

# ── Stage 1: builder ────────────────────────────────────────
FROM python:3.11-slim AS builder

# Evitar archivos .pyc y buffering en logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Instalar compiladores necesarios para algunas dependencias
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar y preinstalar dependencias del pipeline (capa de caché separada)
COPY requirements-pipeline.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-pipeline.txt

# Copiar e instalar dependencias completas de la API (fijando bcrypt==4.0.1 compatible con passlib)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install bcrypt==4.0.1 \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Ruta donde se instalaron los paquetes en el builder
    PYTHONPATH=/app

WORKDIR /app

# Instalar solo libpq en runtime (necesaria para psycopg2 en tiempo de ejecución)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copiar paquetes instalados desde el builder (sin compiladores)
COPY --from=builder /install /usr/local

# Crear usuario no-root para mayor seguridad
RUN useradd --create-home --shell /bin/bash appuser

# Copiar el código fuente del proyecto
COPY services/ ./services/
COPY db/ ./db/

# Cambiar al usuario no-root antes de ejecutar
USER appuser

# Exponer puerto de la API
EXPOSE 8000

# Comando de inicio: uvicorn con recarga deshabilitada en producción
CMD ["uvicorn", "services.pedidos.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2"]

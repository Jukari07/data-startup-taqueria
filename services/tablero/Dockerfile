# ============================================================
# Dockerfile — Tablero de Analítica (services/tablero)
# Multi-stage: builder instala dependencias,
# runtime expone Streamlit en puerto 8501 con usuario no-root.
# Al arrancar, si falta data/clean/pedidos_clean.csv lo genera
# y lo sube a MinIO automáticamente (scripts/preparar_datos.py).
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

# Instalar dependencias del tablero + pipeline (para preparar_datos.py)
COPY requirements.txt requirements-eda.txt requirements-pipeline.txt ./
RUN pip install --no-cache-dir --prefix=/install bcrypt==4.0.1 \
    && pip install --no-cache-dir --prefix=/install \
        -r requirements.txt \
        -r requirements-eda.txt \
        -r requirements-pipeline.txt

# ── Stage 2: runtime ────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

RUN useradd --create-home --shell /bin/bash appuser

# Copiar código fuente completo que necesita el tablero y preparar_datos.py
COPY streamlit_app.py ./
COPY services/ ./services/
COPY data/raw/generar_pedidos.py ./data/raw/generar_pedidos.py
COPY scripts/ ./scripts/

# Crear directorio de datos clean (se llenará en runtime o por preparar_datos.py)
RUN mkdir -p data/clean data/sample

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Ejecutar preparar_datos.py antes de lanzar Streamlit
CMD ["sh", "-c", \
     "python scripts/preparar_datos.py && \
      streamlit run streamlit_app.py \
        --server.port=8501 \
        --server.address=0.0.0.0"]

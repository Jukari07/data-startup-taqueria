"""
API FastAPI para los modelos de Machine Learning de Tacos Las Cazuelitas.

Endpoints disponibles:
- GET  /pronostico  → serie de pedidos pronosticados por franja horaria
- POST /clasificar  → clasifica si un cliente está en riesgo de no volver
- GET  /health      → verificación de salud del servicio
"""

import os
import logging
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ─── Configuración de logging ────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── Rutas de modelos ─────────────────────────────────────────────────────────
DIR_MODELOS = Path(__file__).parent / "models"

# Franjas horarias disponibles y sus rangos en horas
FRANJAS = {
    "manana": (7, 9),    # 07:00 – 09:00
    "media":  (9, 11),   # 09:00 – 11:00
    "cierre": (11, 12),  # 11:00 – 12:00
}

# ─── Carga de modelos al arrancar ─────────────────────────────────────────────
modelos_cargados: dict = {}

def _cargar_modelos() -> None:
    """Intenta cargar todos los modelos desde el directorio models/.
    Si alguno falta, deja modelos_cargados vacío para retornar 503.
    """
    rutas = {
        "sarima":   DIR_MODELOS / "sarima_pedidos.pkl",
        "nb_churn": DIR_MODELOS / "nb_churn.pkl",
        "arbol":    DIR_MODELOS / "arbol_churn.pkl",
    }
    for nombre, ruta in rutas.items():
        if not ruta.exists():
            logger.warning("Modelo no encontrado: %s", ruta)
            return  # sale sin cargar nada → modelos_cargados queda vacío
        modelos_cargados[nombre] = joblib.load(ruta)
        logger.info("Modelo '%s' cargado desde %s", nombre, ruta)
    logger.info("Todos los modelos cargados correctamente.")


# ─── Aplicación FastAPI ───────────────────────────────────────────────────────
app = FastAPI(
    title="API de Modelos ML – Taquería Las Cazuelitas",
    description="Servicio de pronóstico de pedidos y clasificación de riesgo de churn.",
    version="3.0.0",
)


@app.on_event("startup")
async def startup_event():
    """Se ejecuta al iniciar el servidor: carga modelos en memoria."""
    _cargar_modelos()


def _verificar_modelos():
    """Lanza 503 si los modelos no están cargados."""
    if not modelos_cargados:
        raise HTTPException(
            status_code=503,
            detail="Modelos no entrenados: ejecuta scripts/entrenar_modelos.py",
        )


# ─── Endpoint: Health ─────────────────────────────────────────────────────────
@app.get("/health", summary="Verificación de salud")
async def health():
    """Retorna el estado del servicio e indica si los modelos están listos."""
    listos = bool(modelos_cargados)
    return {
        "status": "ok" if listos else "degradado",
        "modelos_listos": listos,
        "modelos_cargados": list(modelos_cargados.keys()),
    }


# ─── Endpoint: Pronóstico ─────────────────────────────────────────────────────
@app.get("/pronostico", summary="Pronóstico de pedidos por franja horaria")
async def pronostico(
    franja: Literal["manana", "media", "cierre"] = Query(
        "manana", description="Franja horaria a pronosticar"
    ),
    dias: int = Query(7, ge=1, le=30, description="Número de días a pronosticar"),
):
    """
    Retorna una serie de pedidos pronosticados para la franja horaria indicada.

    - **franja**: 'manana' (7-9h), 'media' (9-11h) o 'cierre' (11-12h)
    - **dias**: cuántos días hacia adelante pronosticar (1-30)

    Respuesta:
    ```json
    {
      "franja": "manana",
      "dias": 7,
      "pronostico": [
        {"dia": 1, "fecha": "2024-01-15", "pedidos": 42, "ic_inf": 36, "ic_sup": 48},
        ...
      ]
    }
    ```
    """
    _verificar_modelos()

    modelo_sarima = modelos_cargados["sarima"]

    try:
        # Genera pronóstico con intervalo de confianza del 95 %
        pred = modelo_sarima.get_forecast(steps=dias)
        media = pred.predicted_mean.values
        ic = pred.conf_int(alpha=0.05)  # DataFrame con lower/upper
        ic_inf = ic.iloc[:, 0].values
        ic_sup = ic.iloc[:, 1].values
    except Exception as exc:
        logger.error("Error generando pronóstico SARIMA: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error en pronóstico: {exc}")

    # Construye fecha de inicio desde hoy
    hoy = pd.Timestamp.today().normalize()
    fechas = pd.date_range(start=hoy + pd.Timedelta(days=1), periods=dias, freq="B")  # días hábiles

    serie = []
    for i, fecha in enumerate(fechas):
        serie.append({
            "dia":     i + 1,
            "fecha":   fecha.strftime("%Y-%m-%d"),
            "pedidos": max(0, round(float(media[i]), 1)),
            "ic_inf":  max(0, round(float(ic_inf[i]), 1)),
            "ic_sup":  max(0, round(float(ic_sup[i]), 1)),
        })

    return {
        "franja":   franja,
        "rango_horario": f"{FRANJAS[franja][0]:02d}:00 – {FRANJAS[franja][1]:02d}:00",
        "dias":     dias,
        "pronostico": serie,
    }


# ─── Schema: clasificación de cliente ─────────────────────────────────────────
class DatosCliente(BaseModel):
    """Datos de entrada para clasificar el riesgo de churn de un cliente."""
    cliente_id:              str
    dias_sin_pedir:          float   # días desde el último pedido
    total_pedidos:           int     # historial total de pedidos
    ticket_promedio:         float   # gasto promedio por pedido (MXN)
    tipo_entrega_dominante:  str     # 'llevar', 'aqui' o 'domicilio'


# ─── Endpoint: Clasificación de riesgo ───────────────────────────────────────
@app.post("/clasificar", summary="Clasifica el riesgo de churn de un cliente")
async def clasificar(datos: DatosCliente):
    """
    Clasifica si un cliente está en riesgo de no volver a pedir.

    - **alto**:  probabilidad > 0.65
    - **medio**: probabilidad 0.35 – 0.65
    - **bajo**:  probabilidad < 0.35

    Usa el modelo con mayor F1 (árbol de decisión por defecto; se indica el modelo usado).
    """
    _verificar_modelos()

    # Convierte tipo de entrega a binario (1 = domicilio)
    es_domicilio = 1 if datos.tipo_entrega_dominante == "domicilio" else 0

    # Vector de features (mismo orden que en entrenamiento)
    X = np.array([[
        datos.dias_sin_pedir,
        datos.total_pedidos,
        datos.ticket_promedio,
        es_domicilio,
        0,  # variedad: no disponible en este endpoint, se imputa como 0
    ]])

    try:
        # Usamos árbol de decisión como modelo primario
        modelo = modelos_cargados["arbol"]
        nombre_modelo = "ArbolDecision"
        prob = float(modelo.predict_proba(X)[0][1])
    except Exception as exc:
        logger.error("Error en clasificación con árbol: %s — intenta Naive Bayes", exc)
        modelo = modelos_cargados["nb_churn"]
        nombre_modelo = "NaiveBayes"
        prob = float(modelo.predict_proba(X)[0][1])

    # Categoriza el nivel de riesgo
    if prob > 0.65:
        nivel = "alto"
    elif prob > 0.35:
        nivel = "medio"
    else:
        nivel = "bajo"

    logger.info("Cliente %s → riesgo %s (%.2f) con modelo %s",
                datos.cliente_id, nivel, prob, nombre_modelo)

    return {
        "cliente_id":  datos.cliente_id,
        "riesgo":      nivel,
        "probabilidad": round(prob, 4),
        "modelo":       nombre_modelo,
    }

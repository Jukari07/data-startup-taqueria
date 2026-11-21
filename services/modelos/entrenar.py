"""
Script de entrenamiento de modelos ML para Taquería Las Cazuelitas.

Modelos que entrena:
1. SARIMA  → pronóstico de volumen de pedidos por franja horaria
2. GaussianNB → clasificador de riesgo de churn
3. DecisionTreeClassifier → clasificador de riesgo de churn (alternativo)

Uso:
    python -m services.modelos.entrenar

Requiere pedidos_clean.csv en la raíz del proyecto (o conexión a PostgreSQL).
"""

import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from itertools import product as iproduct

# Statsmodels para SARIMA y diagnóstico ACF/PACF
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.graphics.tsaplots import acf, pacf

# Scikit-learn para clasificadores de churn
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report, confusion_matrix

# Módulo de ingeniería de features propio
from services.modelos.features import construir_features_churn, construir_serie_pedidos

# ─── Configuración de logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ─── Rutas ───────────────────────────────────────────────────────────────────
DIR_BASE    = Path(__file__).parent
DIR_MODELOS = DIR_BASE / "models"
DIR_MODELOS.mkdir(parents=True, exist_ok=True)

RUTA_CSV = Path("data/pedidos_clean.csv")


# ═════════════════════════════════════════════════════════════════════════════
# 1. CARGA DE DATOS
# ═════════════════════════════════════════════════════════════════════════════

def cargar_pedidos() -> pd.DataFrame:
    """Carga el CSV de pedidos limpios.

    Fallback: si no existe el CSV, intenta leer de PostgreSQL usando
    las variables de entorno definidas en .env.
    """
    if RUTA_CSV.exists():
        logger.info("Cargando datos desde %s", RUTA_CSV)
        df = pd.read_csv(RUTA_CSV, parse_dates=["fecha_hora"])
    else:
        logger.warning("CSV no encontrado; intentando conexión PostgreSQL...")
        try:
            import psycopg2
            from dotenv import load_dotenv
            import os
            load_dotenv()
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                dbname=os.getenv("POSTGRES_DB", "taqueria"),
                user=os.getenv("POSTGRES_USER", "taqueria_user"),
                password=os.getenv("POSTGRES_PASSWORD", ""),
            )
            query = """
                SELECT p.pedido_id, p.cliente_id, p.fecha_hora, p.tipo_entrega,
                       p.total, dp.producto_id, dp.cantidad, dp.precio_unitario
                FROM pedidos p
                JOIN detalle_pedido dp ON dp.pedido_id = p.pedido_id
            """
            df = pd.read_sql(query, conn, parse_dates=["fecha_hora"])
            conn.close()
            logger.info("Datos cargados desde PostgreSQL: %d registros", len(df))
        except Exception as exc:
            logger.error("No se pudo cargar datos: %s", exc)
            raise FileNotFoundError(
                "No se encontró pedidos_clean.csv ni conexión PostgreSQL válida."
            ) from exc
    return df


# ═════════════════════════════════════════════════════════════════════════════
# 2. ENTRENAMIENTO SARIMA
# ═════════════════════════════════════════════════════════════════════════════

def _aic_grid_search(serie: pd.Series, franja: str) -> dict:
    """
    Grid search de parámetros SARIMA con ACF/PACF como orientación.

    Parámetros evaluados:
        p ∈ {0, 1, 2}  (AR)
        d ∈ {0, 1}     (integración)
        q ∈ {0, 1, 2}  (MA)
        P=1, D=1, Q=1, s=5  (componente estacional semanal)

    Criterio de selección: menor AIC.
    """
    mejor_aic = np.inf
    mejor_params = (1, 1, 1)

    # Referencia visual de ACF/PACF para justificación (no se plotea en headless)
    acf_vals  = acf(serie.dropna(),  nlags=20, fft=True)
    pacf_vals = pacf(serie.dropna(), nlags=20)
    logger.info("ACF (lags 1-5):  %s", np.round(acf_vals[1:6], 3))
    logger.info("PACF (lags 1-5): %s", np.round(pacf_vals[1:6], 3))

    for p, d, q in iproduct(range(3), range(2), range(3)):
        try:
            modelo = SARIMAX(
                serie,
                order=(p, d, q),
                seasonal_order=(1, 1, 1, 5),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            resultado = modelo.fit(disp=False)
            if resultado.aic < mejor_aic:
                mejor_aic    = resultado.aic
                mejor_params = (p, d, q)
                mejor_modelo = resultado
        except Exception:
            pass  # algunos parámetros pueden no converger

    logger.info(
        "Franja '%s' → mejor SARIMA(%s,%s,%s)(1,1,1,5)  AIC=%.2f",
        franja, *mejor_params, mejor_aic,
    )
    return {"modelo": mejor_modelo, "params": mejor_params, "aic": mejor_aic}


def entrenar_sarima(df: pd.DataFrame) -> None:
    """
    Entrena un modelo SARIMA para pronóstico de pedidos por franja horaria.

    - Agrega pedidos por franja y día.
    - Realiza grid search de p,d,q minimizando AIC.
    - Guarda el mejor modelo en models/sarima_pedidos.pkl.
    - Imprime intervalo de confianza del pronóstico a 7 días.
    """
    logger.info("=== Entrenando SARIMA ===")

    # Entrena para la franja 'manana' (representativa); se puede extender a todas
    franja_objetivo = "manana"
    serie = construir_serie_pedidos(df, franja=franja_objetivo)
    logger.info("Serie de entrenamiento: %d días, media=%.1f pedidos/día",
                len(serie), serie.mean())

    resultado = _aic_grid_search(serie, franja_objetivo)
    mejor_modelo = resultado["modelo"]

    # Muestra pronóstico de 7 días con IC 95 %
    pred = mejor_modelo.get_forecast(steps=7)
    ic   = pred.conf_int(alpha=0.05)
    logger.info("Pronóstico a 7 días (IC 95%%):")
    for i, (media_val, (ic_inf, ic_sup)) in enumerate(
        zip(pred.predicted_mean, ic.values), start=1
    ):
        logger.info("  Día %d: %.1f pedidos  [%.1f – %.1f]", i, media_val, ic_inf, ic_sup)

    # Guarda el modelo entrenado
    ruta_salida = DIR_MODELOS / "sarima_pedidos.pkl"
    joblib.dump(mejor_modelo, ruta_salida)
    logger.info("Modelo SARIMA guardado en %s", ruta_salida)


# ═════════════════════════════════════════════════════════════════════════════
# 3. ENTRENAMIENTO CLASIFICADORES DE CHURN
# ═════════════════════════════════════════════════════════════════════════════

def entrenar_clasificadores_churn(df: pd.DataFrame) -> None:
    """
    Entrena dos clasificadores de riesgo de churn:
      - GaussianNB (Naive Bayes)
      - DecisionTreeClassifier (Árbol de decisión)

    Features:
        dias_sin_pedir   : días desde el último pedido
        total_pedidos    : cantidad total de pedidos históricos
        ticket_promedio  : gasto promedio por pedido (MXN)
        es_domicilio     : 1 si el tipo de entrega dominante es domicilio
        variedad         : número de productos distintos pedidos

    Label:
        en_riesgo (1 si no pidió en los últimos 30 días, 0 si no)
    """
    logger.info("=== Entrenando clasificadores de churn ===")

    # Construye el dataset de features por cliente
    df_feat = construir_features_churn(df)
    if df_feat.empty:
        logger.error("No hay datos suficientes para entrenar clasificadores.")
        return

    FEATURES = ["dias_sin_pedir", "total_pedidos", "ticket_promedio",
                "es_domicilio", "variedad"]
    LABEL    = "en_riesgo"

    X = df_feat[FEATURES].fillna(0)
    y = df_feat[LABEL]

    logger.info("Dataset de churn: %d clientes, %.1f%% en riesgo",
                len(y), 100 * y.mean())

    # División train/test 80/20 con semilla fija para reproducibilidad
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    metricas = {}

    for nombre, clf in [
        ("NaiveBayes",      GaussianNB()),
        ("ArbolDecision",   DecisionTreeClassifier(max_depth=5, random_state=42)),
    ]:
        logger.info("--- Entrenando %s ---", nombre)
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)

        # Reporte de clasificación
        reporte = classification_report(y_test, y_pred, output_dict=True)
        cm      = confusion_matrix(y_test, y_pred).tolist()

        logger.info("Matriz de confusión:\n%s", confusion_matrix(y_test, y_pred))
        logger.info("Precisión: %.4f | Recall: %.4f | F1: %.4f",
                    reporte["1"]["precision"],
                    reporte["1"]["recall"],
                    reporte["1"]["f1-score"])

        metricas[nombre] = {
            "precision": round(reporte["1"]["precision"], 4),
            "recall":    round(reporte["1"]["recall"],    4),
            "f1":        round(reporte["1"]["f1-score"],  4),
            "accuracy":  round(reporte["accuracy"],       4),
            "confusion_matrix": cm,
        }

        # Ruta de guardado
        nombre_archivo = "nb_churn.pkl" if nombre == "NaiveBayes" else "arbol_churn.pkl"
        ruta = DIR_MODELOS / nombre_archivo
        joblib.dump(clf, ruta)
        logger.info("Modelo %s guardado en %s", nombre, ruta)

    # Guarda reporte JSON con métricas de ambos modelos
    ruta_metricas = DIR_MODELOS / "metricas_modelos.json"
    with open(ruta_metricas, "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)
    logger.info("Métricas guardadas en %s", ruta_metricas)

    # Resumen comparativo
    logger.info("=== Comparación de modelos ===")
    for nombre, m in metricas.items():
        logger.info("%-20s  Precisión=%.4f  Recall=%.4f  F1=%.4f",
                    nombre, m["precision"], m["recall"], m["f1"])


# ═════════════════════════════════════════════════════════════════════════════
# 4. PUNTO DE ENTRADA
# ═════════════════════════════════════════════════════════════════════════════

def main():
    """Función principal: carga datos y entrena todos los modelos."""
    logger.info("Inicio del entrenamiento de modelos — Taquería Las Cazuelitas")

    df = cargar_pedidos()

    entrenar_sarima(df)
    entrenar_clasificadores_churn(df)

    logger.info("Entrenamiento completado. Modelos disponibles en %s", DIR_MODELOS)


if __name__ == "__main__":
    main()

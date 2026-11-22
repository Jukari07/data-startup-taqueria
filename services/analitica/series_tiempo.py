"""
series_tiempo.py
================
Módulo de analítica de series temporales para Tacos Las Cazuelitas (Entregable E2).

Funcionalidades:
  1. Agrupación y relleno continuo de la serie diaria de pedidos únicos.
  2. Descomposición aditiva clásica (observada, tendencia, estacionalidad, residuo).
  3. Prueba de estacionariedad Augmented Dickey-Fuller (ADF) con interpretación.
  4. Funciones de autocorrelación (ACF) y autocorrelación parcial (PACF).
  5. Regresión lineal por Mínimos Cuadrados Ordinarios (OLS) calculada a mano
     con NumPy mediante la ecuación normal:
         beta = (X^T * X)^(-1) * X^T * y
     comparada rigurosamente contra scikit-learn (MSE, RMSE, MAE, R2 y residuos).
"""

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import acf, adfuller, pacf


def pedidos_por_dia(df: pd.DataFrame) -> pd.Series:
    """
    Agrupa los pedidos limpios por fecha única y calcula el total de pedidos únicos diarios.
    Rellena huecos (ej. domingos y lunes cerrados) con 0 para garantizar frecuencia diaria continua.
    """
    if "fecha_hora" not in df.columns or "pedido_id" not in df.columns:
        raise ValueError("El DataFrame debe contener las columnas 'fecha_hora' y 'pedido_id'.")

    df_copia = df.copy()
    df_copia["fecha_hora"] = pd.to_datetime(df_copia["fecha_hora"], errors="coerce")
    df_copia = df_copia.dropna(subset=["fecha_hora"])

    serie = (
        df_copia.groupby(df_copia["fecha_hora"].dt.date)["pedido_id"]
        .nunique()
        .rename("pedidos_unicos")
    )
    serie.index = pd.DatetimeIndex(serie.index)
    serie_continua = serie.asfreq("D", fill_value=0)
    return serie_continua


def descomponer(serie: pd.Series, periodo: int = 7) -> pd.DataFrame:
    """
    Aplica descomposición aditiva clásica sobre la serie de pedidos.
    Periodo predeterminado: 7 días (ciclo semanal martes-sábado).
    """
    if len(serie) < 2 * periodo:
        raise ValueError(f"Se requieren al menos {2 * periodo} días para una descomposición estacional de periodo {periodo}.")

    resultado = seasonal_decompose(
        serie.astype(float),
        model="additive",
        period=periodo,
        extrapolate_trend="freq"
    )
    return pd.DataFrame({
        "observado": resultado.observed,
        "tendencia": resultado.trend,
        "estacional": resultado.seasonal,
        "residuo": resultado.resid,
    })


def probar_estacionariedad_adf(serie: pd.Series) -> Dict[str, Any]:
    """
    Ejecuta el test Augmented Dickey-Fuller (ADF) para evaluar estacionariedad.
    H0: La serie tiene raíz unitaria (no es estacionaria).
    H1: La serie no tiene raíz unitaria (es estacionaria).
    """
    valores = serie.to_numpy(dtype=float)
    if len(valores) < 15 or np.ptp(valores) == 0:
        return {
            "disponible": False,
            "estadistico": None,
            "p_valor": None,
            "es_estacionaria": False,
            "interpretacion": "Serie demasiado corta o constante para test ADF.",
        }

    estadistico, p_valor, rezagos, n_obs, valores_criticos, _ = adfuller(valores, autolag="AIC")
    es_estacionaria = bool(p_valor < 0.05)

    if es_estacionaria:
        interp = (
            f"La serie ES estacionaria (p-valor = {p_valor:.4e} < 0.05). "
            "Se rechaza la hipótesis nula de raíz unitaria: media y varianza son estables en el tiempo."
        )
    else:
        interp = (
            f"La serie NO es estacionaria (p-valor = {p_valor:.4f} >= 0.05). "
            "No se puede rechazar la hipótesis nula: presenta tendencia o varianza no constante."
        )

    return {
        "disponible": True,
        "estadistico": float(estadistico),
        "p_valor": float(p_valor),
        "es_estacionaria": es_estacionaria,
        "rezagos_usados": int(rezagos),
        "n_observaciones": int(n_obs),
        "valores_criticos": valores_criticos,
        "interpretacion": interp,
    }


def calcular_acf_pacf(serie: pd.Series, lags: int = 30) -> Dict[str, Any]:
    """Calcula las funciones de autocorrelación simple (ACF) y parcial (PACF)."""
    valores = serie.to_numpy(dtype=float)
    n_lags = min(lags, (len(valores) // 2) - 1)
    if n_lags < 2:
        return {"disponible": False, "acf": [], "pacf": []}

    valores_acf = acf(valores, nlags=n_lags, fft=True)
    valores_pacf = pacf(valores, nlags=n_lags, method="ywm")

    return {
        "disponible": True,
        "acf": valores_acf.tolist(),
        "pacf": valores_pacf.tolist(),
        "n_lags": n_lags,
    }


def _metricas_evaluacion(y_real: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calcula las métricas estándar de regresión."""
    errores = y_real - y_pred
    mse = float(np.mean(errores ** 2))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(errores)))
    
    varianza_total = float(np.sum((y_real - np.mean(y_real)) ** 2))
    suma_errores_cuad = float(np.sum(errores ** 2))
    r2 = float(1.0 - (suma_errores_cuad / varianza_total)) if varianza_total > 0 else 0.0

    return {
        "MSE": round(mse, 4),
        "RMSE": round(rmse, 4),
        "MAE": round(mae, 4),
        "R2": round(r2, 4),
    }


def regresion_ols(serie: pd.Series, test_frac: float = 0.20) -> Dict[str, Any]:
    """
    Ajusta una regresión lineal sobre el tiempo por dos vías:
      a) Cálculo manual con NumPy aplicando la Ecuación Normal:
             beta = (X^T * X)^(-1) * X^T * y
      b) Modelo con scikit-learn (LinearRegression).
    
    Retorna coeficientes de ambas implementaciones, métricas en test (MSE, RMSE, MAE, R²)
    y el vector de residuos.
    """
    y = serie.to_numpy(dtype=float)
    n = len(y)
    if n < 10:
        raise ValueError("La serie requiere al menos 10 observaciones para regresión OLS.")

    n_train = int(n * (1.0 - test_frac))
    t = np.arange(n, dtype=float)

    # Matriz de diseño con columna de unos para el intercepto: X = [1, t]
    X = np.column_stack([np.ones(n), t])

    X_train, y_train = X[:n_train], y[:n_train]
    X_test, y_test = X[n_train:], y[n_train:]
    t_test = t[n_train:]

    # ── a) Cálculo manual con NumPy (ecuación normal) ─────────────────────────
    # beta = pinv(X^T @ X) @ (X^T @ y)
    beta_manual = np.linalg.pinv(X_train.T @ X_train) @ (X_train.T @ y_train)
    y_pred_manual = X_test @ beta_manual

    # ── b) Cálculo con scikit-learn ───────────────────────────────────────────
    modelo_sklearn = LinearRegression().fit(t[:n_train, None], y_train)
    y_pred_sklearn = modelo_sklearn.predict(t_test[:, None])

    beta_sklearn = np.array([modelo_sklearn.intercept_, modelo_sklearn.coef_[0]])

    # ── Métricas y comparación ────────────────────────────────────────────────
    metricas_manual = _metricas_evaluacion(y_test, y_pred_manual)
    metricas_sklearn = _metricas_evaluacion(y_test, y_pred_sklearn)

    # Residuos en el conjunto de prueba
    residuos = y_test - y_pred_manual

    return {
        "coeficientes_manual": {
            "intercepto": round(float(beta_manual[0]), 4),
            "pendiente": round(float(beta_manual[1]), 4),
        },
        "coeficientes_sklearn": {
            "intercepto": round(float(beta_sklearn[0]), 4),
            "pendiente": round(float(beta_sklearn[1]), 4),
        },
        "metricas_manual": metricas_manual,
        "metricas_sklearn": metricas_sklearn,
        "coinciden_exactamente": bool(np.allclose(beta_manual, beta_sklearn, atol=1e-5)),
        "n_train": n_train,
        "n_test": n - n_train,
        "fechas_test": [str(d.date()) for d in serie.index[n_train:]],
        "y_real_test": y_test.tolist(),
        "y_pred_test": y_pred_manual.tolist(),
        "residuos_test": residuos.tolist(),
    }


# Alias retrocompatible
test_adf = probar_estacionariedad_adf

"""
test_series_tiempo.py
=====================
Pruebas para el módulo de analítica de series de tiempo (Entregable E2).
"""

import pytest
import numpy as np
import pandas as pd

from services.analitica.series_tiempo import (
    pedidos_por_dia,
    descomponer,
    probar_estacionariedad_adf,
    calcular_acf_pacf,
    regresion_ols,
)


@pytest.fixture
def serie_pedidos_sintetica():
    """Genera una serie diaria sintética de 60 días para pruebas."""
    np.random.seed(42)
    fechas = pd.date_range("2024-01-01", periods=60, freq="D")
    t = np.arange(60)
    estacional = 10 * np.sin(2 * np.pi * t / 7)
    valores = np.maximum(5, (30 + 0.1 * t + estacional + np.random.normal(0, 3, 60))).round()
    return pd.Series(valores, index=fechas, name="pedidos_unicos")


def test_descomposicion_serie(serie_pedidos_sintetica):
    """Valida la descomposición aditiva en 4 componentes."""
    df_desc = descomponer(serie_pedidos_sintetica, periodo=7)
    assert set(df_desc.columns) == {"observado", "tendencia", "estacional", "residuo"}
    assert len(df_desc) == len(serie_pedidos_sintetica)


def test_prueba_adf(serie_pedidos_sintetica):
    """Valida la ejecución del test Dickey-Fuller aumentado."""
    res_adf = probar_estacionariedad_adf(serie_pedidos_sintetica)
    assert res_adf["disponible"] is True
    assert "estadistico" in res_adf
    assert "p_valor" in res_adf
    assert "es_estacionaria" in res_adf
    assert isinstance(res_adf["interpretacion"], str)


def test_acf_pacf(serie_pedidos_sintetica):
    """Valida el cálculo de autocorrelaciones simple y parcial."""
    res = calcular_acf_pacf(serie_pedidos_sintetica, lags=15)
    assert res["disponible"] is True
    assert len(res["acf"]) > 5
    assert len(res["pacf"]) > 5


def test_regresion_ols_manual_vs_sklearn(serie_pedidos_sintetica):
    """
    Valida que la regresión manual por ecuación normal en NumPy:
    beta = pinv(X^T @ X) @ (X^T @ y)
    coincida exactamente con scikit-learn LinearRegression.
    """
    res = regresion_ols(serie_pedidos_sintetica, test_frac=0.20)
    assert res["coinciden_exactamente"] is True
    assert res["metricas_manual"]["R2"] == res["metricas_sklearn"]["R2"]
    assert res["metricas_manual"]["MSE"] == res["metricas_sklearn"]["MSE"]
    assert len(res["residuos_test"]) == res["n_test"]

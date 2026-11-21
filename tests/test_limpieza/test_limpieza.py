"""
test_limpieza.py
================
Pruebas unitarias para el módulo de limpieza reproducible (limpieza.py)
y validación de las reglas de negocio de la entrevista para "Las Cazuelitas".

Cubre:
  1. Eliminación de duplicados exactos
  2. Imputación de nulos en cantidad mediante mediana por categoría
  3. Normalización de nombres mal escritos usando el mapa canónico
  4. Corrección de errores lógicos (cantidades negativas y totales recalculados)
  5. Tratamiento de outliers en cantidad (capping al percentil 95)
  6. Estructura y coherencia del reporte de limpieza generado
  7. Manejo de pedidos multi-línea y conteo de pedidos únicos por pedido_id
  8. Validación de reglas de entrevista:
     - Quincena como dato real (~60 pedidos vs ~30 en día normal)
     - Lengua se agota a las 10 a.m. (Pepena es guisado normal todo el día)
     - Reparto de tipo_entrega y aumento de domicilio en lluvia como supuesto del modelo
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os

from services.worker.limpieza import (
    limpiar_pedidos,
    MAPA_CANONICO,
    PRODUCTOS_OFICIALES,
)
from data.raw.generar_pedidos import generar_pedidos, sembrar_errores, es_quincena


@pytest.fixture
def datos_sinteticos_sucios():
    """Genera un DataFrame pequeño con errores conocidos para pruebas unitarias."""
    filas = [
        # Pedido 1 (Multi-línea: 2 líneas normales)
        {
            "pedido_id": "ped-001",
            "fecha_hora": "2024-03-05 08:30:00",
            "cliente_id": "cli-101",
            "tipo_entrega": "aqui",
            "producto": "Pepena",
            "categoria": "guisado",
            "cantidad": 2,
            "precio_unitario": 20.0,
            "salsa": "verde",
            "total": 40.0,
            "estado": "entregado",
        },
        {
            "pedido_id": "ped-001",
            "fecha_hora": "2024-03-05 08:30:00",
            "cliente_id": "cli-101",
            "tipo_entrega": "aqui",
            "producto": "Coca-Cola",
            "categoria": "bebida",
            "cantidad": 1,
            "precio_unitario": 25.0,
            "salsa": "sin_salsa",
            "total": 25.0,
            "estado": "entregado",
        },
        # Fila duplicada exacta de la anterior
        {
            "pedido_id": "ped-001",
            "fecha_hora": "2024-03-05 08:30:00",
            "cliente_id": "cli-101",
            "tipo_entrega": "aqui",
            "producto": "Coca-Cola",
            "categoria": "bebida",
            "cantidad": 1,
            "precio_unitario": 25.0,
            "salsa": "sin_salsa",
            "total": 25.0,
            "estado": "entregado",
        },
        # Pedido 2 con cantidad nula y nombre mal escrito
        {
            "pedido_id": "ped-002",
            "fecha_hora": "2024-03-05 09:15:00",
            "cliente_id": "cli-102",
            "tipo_entrega": "domicilio",
            "producto": "chicharron",  # Mal escrito
            "categoria": "guisado",
            "cantidad": np.nan,  # Nulo
            "precio_unitario": 20.0,
            "salsa": "roja",
            "total": 20.0,
            "estado": "entregado",
        },
        # Pedido 3 con cantidad negativa y total mal calculado
        {
            "pedido_id": "ped-003",
            "fecha_hora": "2024-03-05 10:45:00",
            "cliente_id": "cli-103",
            "tipo_entrega": "llevar",
            "producto": "Rajas con Crema",  # Mal escrito
            "categoria": "guisado",
            "cantidad": -3,  # Negativo
            "precio_unitario": 20.0,
            "salsa": "verde",
            "total": 999.0,  # Total absurdo que no cuadra
            "estado": "entregado",
        },
        # Pedido 4 con outlier extremo en cantidad y producto Lengua
        {
            "pedido_id": "ped-004",
            "fecha_hora": "2024-03-05 08:10:00",
            "cliente_id": "cli-104",
            "tipo_entrega": "domicilio",
            "producto": "lengua",  # Configurable mal escrito
            "categoria": "guisado",
            "cantidad": 150,  # Outlier extremo
            "precio_unitario": 20.0,
            "salsa": "verde",
            "total": 3000.0,
            "estado": "entregado",
        },
    ]
    return pd.DataFrame(filas)


def test_duplicados_eliminados(datos_sinteticos_sucios, tmp_path):
    """Paso 1: Valida que las filas duplicadas exactas se eliminen."""
    raw_file = tmp_path / "raw.csv"
    clean_file = tmp_path / "clean.csv"
    rep_file = tmp_path / "rep.json"

    datos_sinteticos_sucios.to_csv(raw_file, index=False)
    df_clean, reporte = limpiar_pedidos(str(raw_file), str(clean_file), str(rep_file))

    assert reporte["paso1_duplicados_eliminados"] == 1
    assert len(df_clean) == len(datos_sinteticos_sucios) - 1


def test_nulos_cantidad_imputados(datos_sinteticos_sucios, tmp_path):
    """Paso 2: Valida que los valores nulos en cantidad sean imputados con valores positivos."""
    raw_file = tmp_path / "raw.csv"
    clean_file = tmp_path / "clean.csv"
    rep_file = tmp_path / "rep.json"

    datos_sinteticos_sucios.to_csv(raw_file, index=False)
    df_clean, reporte = limpiar_pedidos(str(raw_file), str(clean_file), str(rep_file))

    assert reporte["paso2_nulos_imputados"] == 1
    assert df_clean["cantidad"].isna().sum() == 0
    fila_imputada = df_clean[df_clean["pedido_id"] == "ped-002"]
    assert fila_imputada["cantidad"].iloc[0] > 0


def test_nombres_normalizados_canonicos(datos_sinteticos_sucios, tmp_path):
    """Paso 3: Valida que 'chicharron', 'Rajas con Crema' y 'lengua' se normalicen al catálogo oficial."""
    raw_file = tmp_path / "raw.csv"
    clean_file = tmp_path / "clean.csv"
    rep_file = tmp_path / "rep.json"

    datos_sinteticos_sucios.to_csv(raw_file, index=False)
    df_clean, reporte = limpiar_pedidos(str(raw_file), str(clean_file), str(rep_file))

    assert reporte["paso3_nombres_corregidos"] >= 3
    nombres_limpios = df_clean["producto"].tolist()
    assert "Chicharrón" in nombres_limpios
    assert "Rajas con crema y elote" in nombres_limpios
    assert "Lengua" in nombres_limpios
    assert "chicharron" not in nombres_limpios
    assert "Rajas con Crema" not in nombres_limpios
    assert "lengua" not in nombres_limpios


def test_cantidades_negativas_corregidas(datos_sinteticos_sucios, tmp_path):
    """Paso 4a: Valida que cantidades negativas (-3) se conviertan a positivas (+3)."""
    raw_file = tmp_path / "raw.csv"
    clean_file = tmp_path / "clean.csv"
    rep_file = tmp_path / "rep.json"

    datos_sinteticos_sucios.to_csv(raw_file, index=False)
    df_clean, reporte = limpiar_pedidos(str(raw_file), str(clean_file), str(rep_file))

    assert reporte["paso4_negativos_corregidos"] == 1
    assert (df_clean["cantidad"] <= 0).sum() == 0
    fila_corregida = df_clean[df_clean["pedido_id"] == "ped-003"]
    assert fila_corregida["cantidad"].iloc[0] == 3


def test_totales_recalculados(datos_sinteticos_sucios, tmp_path):
    """Paso 4b: Valida que totales discordantes se recalculen como cantidad * precio_unitario."""
    raw_file = tmp_path / "raw.csv"
    clean_file = tmp_path / "clean.csv"
    rep_file = tmp_path / "rep.json"

    datos_sinteticos_sucios.to_csv(raw_file, index=False)
    df_clean, reporte = limpiar_pedidos(str(raw_file), str(clean_file), str(rep_file))

    fila_corregida = df_clean[df_clean["pedido_id"] == "ped-003"]
    assert fila_corregida["total"].iloc[0] == 60.0
    assert np.allclose(df_clean["total"], df_clean["cantidad"] * df_clean["precio_unitario"], rtol=0.01)


def test_outliers_capping_p95(datos_sinteticos_sucios, tmp_path):
    """Paso 5: Valida que valores extremos en cantidad sufran capping según p95."""
    raw_file = tmp_path / "raw.csv"
    clean_file = tmp_path / "clean.csv"
    rep_file = tmp_path / "rep.json"

    datos_sinteticos_sucios.to_csv(raw_file, index=False)
    df_clean, reporte = limpiar_pedidos(str(raw_file), str(clean_file), str(rep_file))

    assert reporte["paso5_outliers_capped"] >= 1
    assert df_clean.loc[df_clean["pedido_id"] == "ped-004", "cantidad"].iloc[0] < 150


def test_reporte_limpieza_estructura(datos_sinteticos_sucios, tmp_path):
    """Valida que el archivo JSON de reporte se cree con todas las claves métricas requeridas."""
    raw_file = tmp_path / "raw.csv"
    clean_file = tmp_path / "clean.csv"
    rep_file = tmp_path / "rep.json"

    datos_sinteticos_sucios.to_csv(raw_file, index=False)
    df_clean, reporte = limpiar_pedidos(str(raw_file), str(clean_file), str(rep_file))

    assert os.path.exists(rep_file)
    with open(rep_file, "r", encoding="utf-8") as f:
        rep_cargado = json.load(f)

    claves_esperadas = [
        "n_registros_raw",
        "n_pedidos_unicos_raw",
        "paso1_duplicados_eliminados",
        "paso2_nulos_imputados",
        "paso3_nombres_corregidos",
        "paso4_negativos_corregidos",
        "paso4_totales_recalculados",
        "paso5_outliers_capped",
        "n_registros_clean",
        "n_pedidos_unicos_clean",
    ]
    for clave in claves_esperadas:
        assert clave in rep_cargado


def test_pedidos_multilinea_conteo_unico(datos_sinteticos_sucios, tmp_path):
    """
    Valida el enfoque de negocio: un pedido agrupa varias líneas de producto.
    El conteo de pedidos únicos debe ser por pedido_id único.
    """
    raw_file = tmp_path / "raw.csv"
    clean_file = tmp_path / "clean.csv"
    rep_file = tmp_path / "rep.json"

    datos_sinteticos_sucios.to_csv(raw_file, index=False)
    df_clean, reporte = limpiar_pedidos(str(raw_file), str(clean_file), str(rep_file))

    lineas_ped1 = df_clean[df_clean["pedido_id"] == "ped-001"]
    assert len(lineas_ped1) == 2
    assert df_clean["pedido_id"].nunique() == 4
    assert len(df_clean) == 5


def test_mapa_canonico_soporta_lengua():
    """Valida que el catálogo reconozca Lengua como producto configurable del negocio."""
    assert MAPA_CANONICO["lengua"] == "Lengua"
    assert "Lengua" in PRODUCTOS_OFICIALES


def test_simulador_calibracion_entrevista():
    """
    Valida las reglas clave de la entrevista:
    1. Quincena duplicando pedidos (~60 pedidos vs ~30 en día normal).
    2. Cierre domingo y lunes (0 pedidos).
    3. LENGUA se agota a las 10 a.m. (después de las 10 < 2%).
    4. PEPENA es guisado normal todo el día (mantiene > 10% antes y después de las 10 h).
    5. Reparto de tipo_entrega global normal (10% llevar, 50% aqui, 40% domicilio).
    """
    df_sim = generar_pedidos()
    df_sim["fecha_hora"] = pd.to_datetime(df_sim["fecha_hora"])
    df_sim["hora"] = df_sim["fecha_hora"].dt.hour
    df_sim["dia_semana_num"] = df_sim["fecha_hora"].dt.dayofweek
    df_sim["fecha_date"] = df_sim["fecha_hora"].dt.date
    df_sim["dia_mes"] = df_sim["fecha_hora"].dt.day

    # 1. Domingo (6) y lunes (0) cerrados
    assert (df_sim["dia_semana_num"] == 6).sum() == 0
    assert (df_sim["dia_semana_num"] == 0).sum() == 0

    # 2. Promedio de pedidos: normal ~30 vs quincena ~60
    pedidos_por_dia = df_sim.groupby("fecha_date").agg({
        "pedido_id": "nunique",
        "dia_mes": "first"
    })
    
    es_quincena_mask = pedidos_por_dia["dia_mes"].isin([1, 15, 16, 30])
    prom_normal = pedidos_por_dia.loc[~es_quincena_mask, "pedido_id"].mean()
    prom_quincena = pedidos_por_dia.loc[es_quincena_mask, "pedido_id"].mean()

    assert 28.0 <= prom_normal <= 34.0, f"Promedio normal esperado ~30, obtenido: {prom_normal:.1f}"
    assert 55.0 <= prom_quincena <= 65.0, f"Promedio quincena esperado ~60, obtenido: {prom_quincena:.1f}"

    # 3. LENGUA se agota a las 10 a.m.:
    guisados_pre_10 = df_sim[(df_sim["categoria"] == "guisado") & (df_sim["hora"] < 10)]
    tasa_lengua_pre = (guisados_pre_10["producto"] == "Lengua").mean()

    guisados_post_10 = df_sim[(df_sim["categoria"] == "guisado") & (df_sim["hora"] >= 10)]
    tasa_lengua_post = (guisados_post_10["producto"] == "Lengua").mean()

    assert tasa_lengua_pre > 0.12, f"Lengua antes de 10 a.m. esperada > 12%, obtenida: {tasa_lengua_pre:.2%}"
    assert tasa_lengua_post < 0.02, f"Lengua post 10 a.m. esperada < 2%, obtenida: {tasa_lengua_post:.2%}"

    # 4. PEPENA se mantiene constante como guisado normal todo el día:
    tasa_pepena_pre = (guisados_pre_10["producto"] == "Pepena").mean()
    tasa_pepena_post = (guisados_post_10["producto"] == "Pepena").mean()

    assert tasa_pepena_pre > 0.10, f"Pepena antes de 10 a.m. esperada > 10%, obtenida: {tasa_pepena_pre:.2%}"
    assert tasa_pepena_post > 0.15, f"Pepena post 10 a.m. esperada > 15%, obtenida: {tasa_pepena_post:.2%}"

    # 5. Proporción de entrega global
    pedidos_unicos = df_sim.drop_duplicates(subset=["pedido_id"])
    dist_entrega = pedidos_unicos["tipo_entrega"].value_counts(normalize=True)

    assert 0.07 <= dist_entrega["llevar"] <= 0.14
    assert 0.35 <= dist_entrega["aqui"] <= 0.55
    assert 0.35 <= dist_entrega["domicilio"] <= 0.55

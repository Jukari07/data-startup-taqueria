"""
limpieza.py
===========
Módulo de limpieza reproducible para los pedidos de "Las Cazuelitas".
Puede importarse como módulo o ejecutarse directamente como script.

Uso como módulo:
    from services.worker.limpieza import limpiar_pedidos
    df_limpio, reporte = limpiar_pedidos("data/raw/pedidos_raw.csv", "data/clean/pedidos_clean.csv")

Uso como script:
    python services/worker/limpieza.py

Función principal:
    limpiar_pedidos(raw_path, clean_path) -> (DataFrame, dict)

5 pilares de limpieza de datos:
    1. Duplicados exactos (drop_duplicates)
    2. Nulos en cantidad → imputar con mediana de valores válidos por categoría
    3. Nombres mal escritos → mapa canónico de productos del menú
    4. Errores lógicos: cantidad ≤ 0 → abs; total incorrecto → recalcular
    5. Outliers en cantidad → capping al percentil 95 por categoría

Calibración validada con la entrevista real:
    - Pedidos únicos: un pedido contiene varias líneas de producto; el conteo
      de pedidos por día es por pedido_id único.
    - Quincena (es_quincena): DATO DE LA ENTREVISTA (la dueña confirmó ~60 pedidos en
      quincena vs ~30 en día normal en días 1, 15, 16 y 30).
    - Lengua: guisado configurable en catálogo interno que se agota a las 10:00 a.m.
    - Pepena: guisado oficial normal que se sirve durante toda la jornada.
"""

import os
import json
import pandas as pd
import numpy as np

# ── Rutas por defecto ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RAW = os.path.join(BASE_DIR, "..", "..", "data", "raw", "pedidos_raw.csv")
DEFAULT_CLEAN = os.path.join(BASE_DIR, "..", "..", "data", "clean", "pedidos_clean.csv")
DEFAULT_REPORTE = os.path.join(BASE_DIR, "..", "..", "data", "clean", "reporte_limpieza.json")

# ── Mapa canónico de productos ────────────────────────────────────────────────
MAPA_CANONICO: dict[str, str] = {
    # Guisados oficiales del menú publicado
    "pepena":                         "Pepena",
    "Pepena":                         "Pepena",
    "carne de puerco con calabacita": "Carne de puerco con calabacita",
    "chicharron":                     "Chicharrón",
    "chicharrón":                     "Chicharrón",
    "Chicharron":                     "Chicharrón",
    "machaca":                        "Machaca",
    "Machaca":                        "Machaca",
    "carne de res a la mexicana":     "Carne de res a la mexicana",
    "rajas con crema y elote":        "Rajas con crema y elote",
    "Rajas con Crema":                "Rajas con crema y elote",
    "rajas con crema":                "Rajas con crema y elote",
    "frijoles":                       "Frijoles",
    "Frijoles":                       "Frijoles",
    "huevo con jamón":                "Huevo con jamón",
    "huevo con jamon":                "Huevo con jamón",
    # Guisado configurable en catálogo (DATO ENTREVISTA: se agota a las 10 a.m.)
    "lengua":                         "Lengua",
    "Lengua":                         "Lengua",
    # Bebidas oficiales
    "agua fresca del día":            "Agua fresca del día",
    "agua fresca":                    "Agua fresca del día",
    "coca-cola":                      "Coca-Cola",
    "coca cola":                      "Coca-Cola",
    "coca-cola light":                "Coca-Cola Light",
    "coca cola light":                "Coca-Cola Light",
    "squirt":                         "Squirt",
    "fanta de naranja":               "Fanta de Naranja",
    "manzanita sidral":               "Manzanita Sidral",
    "manzanita":                      "Manzanita Sidral",
}

# Nombres oficiales reconocidos en el sistema
PRODUCTOS_OFICIALES = {
    "Pepena", "Carne de puerco con calabacita", "Chicharrón", "Machaca",
    "Carne de res a la mexicana", "Rajas con crema y elote", "Frijoles",
    "Huevo con jamón", "Lengua",
    "Agua fresca del día", "Coca-Cola", "Coca-Cola Light", "Squirt",
    "Fanta de Naranja", "Manzanita Sidral",
}


def limpiar_pedidos(
    raw_path: str = DEFAULT_RAW,
    clean_path: str = DEFAULT_CLEAN,
    reporte_path: str = DEFAULT_REPORTE,
) -> tuple[pd.DataFrame, dict]:
    """
    Lee el CSV raw, aplica los 5 pasos de limpieza, guarda el CSV limpio
    y el reporte JSON. Retorna (df_limpio, reporte).
    """
    reporte: dict = {}

    # ── Carga ─────────────────────────────────────────────────────────────────
    print(f"Cargando datos desde: {raw_path}")
    df = pd.read_csv(raw_path, encoding="utf-8", low_memory=False)
    n_inicial = len(df)
    reporte["n_registros_raw"] = n_inicial
    reporte["n_pedidos_unicos_raw"] = int(df["pedido_id"].nunique()) if "pedido_id" in df.columns else 0
    print(f"  Registros cargados: {n_inicial:,} ({reporte['n_pedidos_unicos_raw']:,} pedidos únicos)")

    # ── Paso 0: parsear fecha_hora ────────────────────────────────────────────
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors="coerce")
    n_fechas_nulas = df["fecha_hora"].isna().sum()
    if n_fechas_nulas:
        print(f"  Advertencia: {n_fechas_nulas} registros con fecha inválida, se eliminarán.")
        df = df.dropna(subset=["fecha_hora"])
    reporte["fechas_invalidas_eliminadas"] = int(n_fechas_nulas)

    # ── Paso 1: Duplicados exactos ────────────────────────────────────────────
    n_antes = len(df)
    df = df.drop_duplicates()
    n_dup_eliminados = n_antes - len(df)
    reporte["paso1_duplicados_eliminados"] = int(n_dup_eliminados)
    print(f"Paso 1 – Duplicados eliminados: {n_dup_eliminados:,}")

    # ── Paso 2: Nulos en 'cantidad' → mediana de positivos por categoría ──────
    n_nulos_antes = df["cantidad"].isna().sum()
    for categoria in df["categoria"].unique():
        mascara_cat = df["categoria"] == categoria
        mascara_positivos = mascara_cat & (df["cantidad"] > 0)
        mediana = df.loc[mascara_positivos, "cantidad"].median()
        if pd.isna(mediana) or mediana <= 0:
            mediana = 1.0
        mascara_nulo = mascara_cat & df["cantidad"].isna()
        df.loc[mascara_nulo, "cantidad"] = max(1.0, float(mediana))
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    n_nulos_imputados = int(n_nulos_antes)
    reporte["paso2_nulos_imputados"] = n_nulos_imputados
    print(f"Paso 2 – Nulos en cantidad imputados: {n_nulos_imputados:,}")

    # ── Paso 3: Nombres mal escritos → nombre canónico ───────────────────────
    n_nombres_antes = (~df["producto"].isin(PRODUCTOS_OFICIALES)).sum()
    df["producto"] = df["producto"].apply(
        lambda p: MAPA_CANONICO.get(str(p).strip(), str(p).strip())
    )
    n_nombres_corregidos = int(n_nombres_antes)
    reporte["paso3_nombres_corregidos"] = n_nombres_corregidos
    print(f"Paso 3 – Nombres corregidos: {n_nombres_corregidos:,}")

    # ── Paso 4: Errores lógicos ───────────────────────────────────────────────
    # 4a. Cantidades ≤ 0 → valor absoluto (mínimo 1)
    mascara_neg = df["cantidad"] <= 0
    n_negativos = int(mascara_neg.sum())
    df.loc[mascara_neg, "cantidad"] = df.loc[mascara_neg, "cantidad"].abs()
    df.loc[df["cantidad"] == 0, "cantidad"] = 1

    # 4b. Total incorrecto → recalcular precio_unitario × cantidad
    total_esperado = (df["precio_unitario"] * df["cantidad"]).round(2)
    mascara_total_mal = ~np.isclose(df["total"], total_esperado, rtol=0.01)
    n_total_recalculado = int(mascara_total_mal.sum())
    df.loc[mascara_total_mal, "total"] = total_esperado[mascara_total_mal]

    reporte["paso4_negativos_corregidos"] = n_negativos
    reporte["paso4_totales_recalculados"] = n_total_recalculado
    print(f"Paso 4 – Cantidades negativas corregidas: {n_negativos:,}")
    print(f"Paso 4 – Totales recalculados: {n_total_recalculado:,}")

    # ── Paso 5: Outliers en cantidad (capping al percentil 95 por categoría) ──
    n_outliers_total = 0
    for categoria in df["categoria"].unique():
        mascara_cat = df["categoria"] == categoria
        limite_sup = df.loc[mascara_cat, "cantidad"].quantile(0.95)
        mascara_outlier = mascara_cat & (df["cantidad"] > limite_sup)
        n_outliers = int(mascara_outlier.sum())
        df.loc[mascara_outlier, "cantidad"] = limite_sup
        n_outliers_total += n_outliers
    df["cantidad"] = df["cantidad"].round().astype(int)

    # Recalcular totales con consistencia estricta
    df["total"] = (df["precio_unitario"] * df["cantidad"]).round(2)
    reporte["paso5_outliers_capped"] = n_outliers_total
    print(f"Paso 5 – Outliers en cantidad (capping p95): {n_outliers_total:,}")

    # ── Columnas auxiliares derivadas de fecha_hora ───────────────────────────
    dias_es = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
               4: "viernes", 5: "sábado", 6: "domingo"}
    df["dia_semana"] = df["fecha_hora"].dt.dayofweek.map(dias_es)
    df["hora"] = df["fecha_hora"].dt.hour

    # DATO DE LA ENTREVISTA: Quincena confirmada en días 1, 15, 16 y 30
    df["es_quincena"] = df["fecha_hora"].dt.day.isin([1, 15, 16, 30])
    df["es_pico_matutino"] = (df["hora"] >= 7) & (df["hora"] < 10)

    # ── Métricas finales ──────────────────────────────────────────────────────
    reporte["n_registros_clean"] = len(df)
    reporte["n_pedidos_unicos_clean"] = int(df["pedido_id"].nunique())
    reporte["reduccion_total"] = n_inicial - len(df)
    print(f"\nRegistros en CSV limpio: {len(df):,} ({reporte['n_pedidos_unicos_clean']:,} pedidos únicos)")

    # ── Guardar CSV limpio y JSON ─────────────────────────────────────────────
    os.makedirs(os.path.dirname(clean_path), exist_ok=True)
    df.to_csv(clean_path, index=False, encoding="utf-8")
    print(f"CSV limpio guardado en: {clean_path}")

    os.makedirs(os.path.dirname(reporte_path), exist_ok=True)
    with open(reporte_path, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"Reporte JSON guardado en: {reporte_path}")

    return df, reporte


if __name__ == "__main__":
    df_limpio, reporte = limpiar_pedidos()
    print("\nReporte de limpieza:")
    for clave, valor in reporte.items():
        print(f"  {clave}: {valor}")
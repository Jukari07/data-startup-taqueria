"""
Módulo de ingeniería de features para los modelos ML de Taquería Las Cazuelitas.

Funciones:
- construir_features_churn(df_pedidos) → DataFrame con features por cliente
- construir_serie_pedidos(df_pedidos, franja) → Series diaria para SARIMA
"""

import logging
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

# ─── Definición de franjas horarias ──────────────────────────────────────────
FRANJAS_HORARIAS = {
    "manana": (7, 9),    # 07:00 – 09:00
    "media":  (9, 11),   # 09:00 – 11:00
    "cierre": (11, 12),  # 11:00 – 12:00
}


def construir_features_churn(df_pedidos: pd.DataFrame) -> pd.DataFrame:
    """
    Construye el dataset de features para el clasificador de riesgo de churn.

    Agrupa los pedidos por cliente y calcula:
      - dias_sin_pedir   : días desde el último pedido hasta hoy
      - total_pedidos    : número total de pedidos históricos
      - ticket_promedio  : gasto promedio por pedido (columna 'total')
      - tipo_entrega_dominante : tipo de entrega más frecuente
      - es_domicilio     : 1 si tipo_entrega_dominante == 'domicilio'
      - variedad         : número de productos distintos pedidos
      - en_riesgo        : 1 si dias_sin_pedir > 30, 0 en caso contrario

    Parámetros:
        df_pedidos : DataFrame con columnas mínimas:
                     ['pedido_id', 'cliente_id', 'fecha_hora',
                      'tipo_entrega', 'total', 'producto_id']

    Retorna:
        DataFrame indexado por cliente_id con todas las features.
    """
    # Verificar columnas mínimas
    cols_requeridas = {"cliente_id", "fecha_hora", "tipo_entrega", "total", "producto_id"}
    cols_faltantes  = cols_requeridas - set(df_pedidos.columns)
    if cols_faltantes:
        logger.error("Columnas faltantes en df_pedidos: %s", cols_faltantes)
        return pd.DataFrame()

    # Asegurar tipo datetime
    df = df_pedidos.copy()
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
    hoy = pd.Timestamp(date.today())

    # ── Agrupar por pedido para evitar duplicar por producto ──────────────────
    # (un pedido puede tener varios productos → tomamos el primer registro por pedido)
    pedidos_unicos = df.drop_duplicates(subset=["pedido_id", "cliente_id"]) if "pedido_id" in df.columns \
                     else df.drop_duplicates(subset=["cliente_id", "fecha_hora"])

    # ── Último pedido por cliente ─────────────────────────────────────────────
    ultimo_pedido = (
        pedidos_unicos
        .groupby("cliente_id")["fecha_hora"]
        .max()
        .rename("ultimo_pedido")
    )

    # ── Total de pedidos por cliente ──────────────────────────────────────────
    total_pedidos = (
        pedidos_unicos
        .groupby("cliente_id")["fecha_hora"]
        .count()
        .rename("total_pedidos")
    )

    # ── Ticket promedio ───────────────────────────────────────────────────────
    ticket_prom = (
        pedidos_unicos
        .groupby("cliente_id")["total"]
        .mean()
        .rename("ticket_promedio")
    )

    # ── Tipo de entrega dominante ─────────────────────────────────────────────
    tipo_dominante = (
        df.groupby("cliente_id")["tipo_entrega"]
        .agg(lambda x: x.mode().iloc[0] if not x.empty else "desconocido")
        .rename("tipo_entrega_dominante")
    )

    # ── Variedad de productos ─────────────────────────────────────────────────
    variedad = (
        df.groupby("cliente_id")["producto_id"]
        .nunique()
        .rename("variedad")
    )

    # ── Combinar todas las features ───────────────────────────────────────────
    df_feat = pd.concat(
        [ultimo_pedido, total_pedidos, ticket_prom, tipo_dominante, variedad],
        axis=1,
    )

    # ── Features derivadas ────────────────────────────────────────────────────
    df_feat["dias_sin_pedir"] = (hoy - df_feat["ultimo_pedido"]).dt.days
    df_feat["es_domicilio"]   = (df_feat["tipo_entrega_dominante"] == "domicilio").astype(int)
    df_feat["en_riesgo"]      = (df_feat["dias_sin_pedir"] > 30).astype(int)

    logger.info(
        "Features de churn construidas: %d clientes, %.1f%% en riesgo",
        len(df_feat), 100 * df_feat["en_riesgo"].mean(),
    )
    return df_feat.reset_index()


def construir_serie_pedidos(
    df_pedidos: pd.DataFrame,
    franja: str = "manana",
) -> pd.Series:
    """
    Construye una serie temporal diaria de conteo de pedidos para una franja horaria.

    Filtra los pedidos que caen dentro del rango horario de la franja indicada,
    agrupa por día y cuenta. Los días sin pedidos se rellenan con 0.

    Parámetros:
        df_pedidos : DataFrame con al menos ['fecha_hora'] (datetime)
        franja     : 'manana', 'media' o 'cierre'

    Retorna:
        pd.Series indexada por fecha (DatetimeIndex diario) con conteos.
    """
    if franja not in FRANJAS_HORARIAS:
        raise ValueError(
            f"Franja '{franja}' no válida. Opciones: {list(FRANJAS_HORARIAS.keys())}"
        )

    hora_ini, hora_fin = FRANJAS_HORARIAS[franja]

    df = df_pedidos.copy()
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])

    # Filtrar por franja horaria
    mask = (df["fecha_hora"].dt.hour >= hora_ini) & (df["fecha_hora"].dt.hour < hora_fin)
    df_franja = df.loc[mask].copy()

    if df_franja.empty:
        logger.warning("Sin datos para franja '%s'", franja)
        return pd.Series(dtype=float)

    # Extraer solo la fecha (sin hora)
    df_franja["fecha"] = df_franja["fecha_hora"].dt.normalize()

    # Contar pedidos únicos por día
    if "pedido_id" in df_franja.columns:
        serie_diaria = df_franja.groupby("fecha")["pedido_id"].nunique()
    else:
        serie_diaria = df_franja.groupby("fecha").size()

    serie_diaria.index = pd.DatetimeIndex(serie_diaria.index)
    serie_diaria.name  = f"pedidos_{franja}"

    # Rellenar fechas sin pedidos con 0 (rango completo)
    rango_completo = pd.date_range(serie_diaria.index.min(), serie_diaria.index.max(), freq="D")
    serie_diaria   = serie_diaria.reindex(rango_completo, fill_value=0)

    logger.info(
        "Serie '%s': %d días, media=%.1f, máx=%d pedidos/día",
        franja, len(serie_diaria), serie_diaria.mean(), serie_diaria.max(),
    )
    return serie_diaria

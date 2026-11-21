"""
Tablero v3 – Versión final del Dashboard de Taquería Las Cazuelitas.

Extiende el Tablero v2 añadiendo la pestaña "Pronóstico e IA" que:
  - Llama a la API de modelos para obtener el pronóstico de pedidos.
  - Muestra la gráfica de pronóstico con banda de confianza (Plotly).
  - Muestra una tabla de clientes en riesgo de no volver (clasificación de churn).
  - En caso de que la API no responda, usa datos locales de respaldo.

Configuración:
  MODELOS_API_URL : URL base de la API de modelos (default: http://localhost:8001)
"""

import os
import logging
import random
from datetime import datetime, timedelta

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ─── Importar las pestañas de versiones anteriores ───────────────────────────
# Se asume que Dashboard_v2.py expone render_tab_general() y render_tab_pedidos()
try:
    from services.tablero.Dashboard_v2 import render_tab_general, render_tab_pedidos
except ImportError:
    # Si no existe v2, definimos stubs que no hacen nada
    def render_tab_general():
        st.info("Pestaña General no disponible (Dashboard_v2 no encontrado).")
    def render_tab_pedidos():
        st.info("Pestaña Pedidos no disponible (Dashboard_v2 no encontrado).")

# ─── Configuración ────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODELOS_API_URL = os.getenv("MODELOS_API_URL", "http://localhost:8001")
TIMEOUT_API     = 5.0  # segundos

# ─── Funciones de llamada a la API ───────────────────────────────────────────

def obtener_pronostico(franja: str = "manana", dias: int = 7) -> dict | None:
    """
    Llama a GET /pronostico de la API de modelos.
    Retorna el dict de respuesta o None si la API no está disponible.
    """
    try:
        url = f"{MODELOS_API_URL}/pronostico"
        resp = httpx.get(url, params={"franja": franja, "dias": dias}, timeout=TIMEOUT_API)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("API de modelos no disponible: %s", exc)
        return None


def clasificar_clientes(df_clientes: pd.DataFrame) -> pd.DataFrame:
    """
    Llama a POST /clasificar para cada cliente en el DataFrame.
    Agrega columnas: riesgo, probabilidad, modelo.
    Si la API falla, retorna DataFrame con columnas vacías.
    """
    resultados = []
    for _, fila in df_clientes.iterrows():
        payload = {
            "cliente_id":             str(fila.get("cliente_id", "")),
            "dias_sin_pedir":         float(fila.get("dias_sin_pedir", 0)),
            "total_pedidos":          int(fila.get("total_pedidos", 0)),
            "ticket_promedio":        float(fila.get("ticket_promedio", 0.0)),
            "tipo_entrega_dominante": str(fila.get("tipo_entrega_dominante", "llevar")),
        }
        try:
            url  = f"{MODELOS_API_URL}/clasificar"
            resp = httpx.post(url, json=payload, timeout=TIMEOUT_API)
            resp.raise_for_status()
            datos = resp.json()
            resultados.append({
                "cliente_id":  datos["cliente_id"],
                "riesgo":      datos["riesgo"],
                "probabilidad": datos["probabilidad"],
                "modelo":       datos["modelo"],
            })
        except Exception as exc:
            logger.warning("Error clasificando cliente %s: %s", payload["cliente_id"], exc)
            resultados.append({
                "cliente_id":  payload["cliente_id"],
                "riesgo":      "desconocido",
                "probabilidad": None,
                "modelo":       "error",
            })
    return pd.DataFrame(resultados)


# ─── Datos locales de respaldo ────────────────────────────────────────────────

def _generar_pronostico_local(dias: int = 7) -> dict:
    """Genera datos ficticios de pronóstico cuando la API no está disponible."""
    hoy    = datetime.today()
    serie  = []
    for i in range(dias):
        media = 40 + 10 * (i % 3)
        serie.append({
            "dia":     i + 1,
            "fecha":   (hoy + timedelta(days=i + 1)).strftime("%Y-%m-%d"),
            "pedidos": media,
            "ic_inf":  max(0, media - 8),
            "ic_sup":  media + 8,
        })
    return {"franja": "manana (local)", "dias": dias, "pronostico": serie}


def _generar_clientes_muestra() -> pd.DataFrame:
    """Genera un DataFrame de muestra de clientes para cuando la API falla."""
    random.seed(42)
    clientes = []
    for i in range(10):
        clientes.append({
            "cliente_id":             f"cliente_{i+1:03d}",
            "dias_sin_pedir":         random.randint(0, 60),
            "total_pedidos":          random.randint(1, 50),
            "ticket_promedio":        round(random.uniform(80, 300), 2),
            "tipo_entrega_dominante": random.choice(["llevar", "domicilio", "aqui"]),
        })
    return pd.DataFrame(clientes)


# ─── Pestaña: Pronóstico e IA ─────────────────────────────────────────────────

def render_tab_pronostico():
    """Renderiza la pestaña 'Pronóstico e IA' del tablero."""
    st.header("🤖 Pronóstico e IA")

    # ── Selección de parámetros ────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        franja = st.selectbox(
            "Franja horaria",
            options=["manana", "media", "cierre"],
            format_func=lambda x: {"manana": "Mañana (7-9h)", "media": "Media (9-11h)", "cierre": "Cierre (11-12h)"}[x],
        )
    with col2:
        dias = st.slider("Días a pronosticar", min_value=1, max_value=14, value=7)

    st.divider()

    # ─── SECCIÓN 1: Pronóstico SARIMA ─────────────────────────────────────────
    st.subheader("📈 Pronóstico de Pedidos")

    with st.spinner("Consultando API de modelos..."):
        datos_pred = obtener_pronostico(franja=franja, dias=dias)

    datos_locales = False
    if datos_pred is None:
        st.warning(
            "⚠️ La API de modelos no está disponible "
            f"(`{MODELOS_API_URL}`). Se muestran datos locales de ejemplo."
        )
        datos_pred   = _generar_pronostico_local(dias=dias)
        datos_locales = True

    df_pred = pd.DataFrame(datos_pred["pronostico"])

    # Gráfica Plotly con banda de confianza (fill='tonexty')
    fig = go.Figure()

    # Banda inferior (invisible, base del fill)
    fig.add_trace(go.Scatter(
        x=df_pred["fecha"],
        y=df_pred["ic_inf"],
        mode="lines",
        line=dict(width=0),
        name="IC inferior",
        showlegend=False,
        hoverinfo="skip",
    ))

    # Banda superior (rellena hasta la inferior)
    fig.add_trace(go.Scatter(
        x=df_pred["fecha"],
        y=df_pred["ic_sup"],
        mode="lines",
        line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(99,110,250,0.2)",
        name="Intervalo de confianza 95%",
        hoverinfo="skip",
    ))

    # Línea de pronóstico central
    fig.add_trace(go.Scatter(
        x=df_pred["fecha"],
        y=df_pred["pedidos"],
        mode="lines+markers",
        line=dict(color="#636EFA", width=2.5),
        marker=dict(size=7),
        name="Pedidos pronosticados",
    ))

    fig.update_layout(
        title=f"Pronóstico de pedidos – Franja {datos_pred['franja'].title()}"
              + (" (datos locales)" if datos_locales else ""),
        xaxis_title="Fecha",
        yaxis_title="Pedidos",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver datos de pronóstico"):
        st.dataframe(df_pred, use_container_width=True)

    st.divider()

    # ─── SECCIÓN 2: Clientes en riesgo ────────────────────────────────────────
    st.subheader("🚨 Clientes en Riesgo de No Volver")

    # Cargar datos de clientes (en producción: consultar DB o cache)
    df_clientes = _generar_clientes_muestra()

    with st.spinner("Clasificando clientes con el modelo de churn..."):
        df_riesgo = clasificar_clientes(df_clientes)

    if df_riesgo.empty or "riesgo" not in df_riesgo.columns:
        st.error("No se pudo obtener la clasificación de clientes.")
    else:
        # Une los datos originales con la clasificación
        df_vista = df_clientes.merge(
            df_riesgo[["cliente_id", "riesgo", "probabilidad", "modelo"]],
            on="cliente_id",
            how="left",
        )

        # Aplica colores según nivel de riesgo
        def colorear_riesgo(val):
            colores = {"alto": "background-color:#ffd6d6", "medio": "background-color:#fff3cd", "bajo": "background-color:#d6f5d6"}
            return colores.get(val, "")

        df_styled = df_vista.style.applymap(colorear_riesgo, subset=["riesgo"])

        st.dataframe(df_styled, use_container_width=True, height=380)

        # Resumen rápido
        conteos = df_riesgo["riesgo"].value_counts()
        c1, c2, c3 = st.columns(3)
        c1.metric("🔴 Riesgo Alto",  conteos.get("alto",  0))
        c2.metric("🟡 Riesgo Medio", conteos.get("medio", 0))
        c3.metric("🟢 Riesgo Bajo",  conteos.get("bajo",  0))


# ─── Aplicación principal ─────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Taquería Las Cazuelitas – Tablero v3",
        page_icon="🌮",
        layout="wide",
    )
    st.title("🌮 Taquería Las Cazuelitas — Tablero de Control v3")

    # Pestañas del tablero
    tab_general, tab_pedidos, tab_ia = st.tabs(
        ["📊 General", "📋 Pedidos", "🤖 Pronóstico e IA"]
    )

    with tab_general:
        render_tab_general()

    with tab_pedidos:
        render_tab_pedidos()

    with tab_ia:
        render_tab_pronostico()


if __name__ == "__main__":
    main()

# =============================================================
# streamlit_app.py — Punto de entrada principal del tablero
#
# Uso: streamlit run streamlit_app.py
#
# Este archivo es el punto de entrada raíz requerido por
# Streamlit Cloud y docker-compose. Delega toda la lógica
# al módulo Dashboard ubicado en services/tablero/.
# =============================================================

import runpy
import sys
import os

# Aseguramos que el directorio del tablero esté en el path
# para que las importaciones relativas funcionen correctamente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services", "tablero"))

# Ejecuta Dashboard.py como script principal de Streamlit
runpy.run_path(
    os.path.join("services", "tablero", "Dashboard.py"),
    run_name="__main__",
)

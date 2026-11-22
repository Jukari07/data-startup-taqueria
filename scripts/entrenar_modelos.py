"""
entrenar_modelos.py
===================
Script ejecutable para entrenar los modelos predictivos de Tacos Las Cazuelitas:
  1. SARIMA para pronóstico de pedidos por franja horaria (mañana, media, cierre).
  2. GaussianNB (Naive Bayes) para predicción de riesgo de abandono (churn).
  3. DecisionTreeClassifier (Árbol de Decisión) alternativo con métricas comparadas.

Guarda los modelos en models/ y services/modelos/models/ junto con metricas_modelos.json.

Uso:
    python scripts/entrenar_modelos.py
"""

import sys
import os
from pathlib import Path

# Añadir raíz al sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.modelos.entrenar import main

if __name__ == "__main__":
    print("==================================================================")
    print("🌮 ENTRENAMIENTO DE MODELOS ML — TAQUERÍA LAS CAZUELITAS")
    print("==================================================================")
    main()
    print("==================================================================")
    print("✅ Modelos entrenados y serializados exitosamente.")
    print("==================================================================")

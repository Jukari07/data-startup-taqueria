"""
Generador de ventas sintéticas para la taquería (Proyecto Integrador DATA STARTUP).
Calibrado con:
  - Medias por producto del CSV original de 4 semanas (ventas_tacos_4_semanas.csv)
  - Entrevista a la dueña: vende más martes, jueves y viernes (7 a 10 pm),
    sube en quincena, baja con lluvia, casi no hay merma.
Los datos son SINTÉTICOS. Reemplazar por ventas reales cuando existan.
"""
import numpy as np
import pandas as pd

SEMILLA = 2026
SEMANAS = 8                      # >= 6 para cumplir 500 registros (8 sem x 7 dias x 12 prod = 672)
INICIO = "2026-09-01"
SALIDA = "ventas_tacos_8_semanas.csv"

# Medias base por producto (tomadas del CSV de 4 semanas)
BASE = {
    "Agua del día": 10.8, "Chicharrón": 11.3, "Frijoles": 8.0, "Huevo con jamón": 9.5,
    "Lengua": 5.3, "Machaca": 6.1, "Pepena": 5.6, "Pollo con crema": 8.5,
    "Pollo en salsa verde": 9.0, "Puerco con calabacitas": 6.8, "Refresco": 11.0,
    "Res a la mexicana": 6.7,
}
PRECIO = {p: 15 for p in BASE}
PRECIO["Refresco"] = 20

# Efecto del día de la semana (0 = lunes) según la entrevista
F_DIA = {0: 0.90, 1: 1.20, 2: 0.95, 3: 1.20, 4: 1.25, 5: 0.85, 6: 0.80}
F_QUINCENA = 1.20   # días 15-16, 30-31 y 1
F_LLUVIA = 0.70     # si llueve, baja la venta
P_LLUVIA = 0.30     # temporada de lluvias en Colima (sep-oct)
P_AGOTADO = 0.02    # probabilidad de que un guisado se acabe / no se cocine
DISPERSION = 6.0    # menor = más variabilidad que Poisson

rng = np.random.default_rng(SEMILLA)
fechas = pd.date_range(INICIO, periods=SEMANAS * 7)
llovio = {f: int(rng.random() < P_LLUVIA) for f in fechas}

filas = []
for f in fechas:
    quincena = f.day in (1, 15, 16, 30, 31)
    for prod, media in BASE.items():
        mu = media * F_DIA[f.dayofweek] * (F_QUINCENA if quincena else 1.0)
        if llovio[f]:
            mu *= F_LLUVIA
        lam = rng.gamma(DISPERSION, mu / DISPERSION)      # sobredispersión
        cant = int(rng.poisson(lam))
        disponible = 1
        if prod not in ("Agua del día", "Refresco") and rng.random() < P_AGOTADO:
            cant, disponible = 0, 0                         # no se cocinó / se acabó
        filas.append([f.date().isoformat(), prod, cant, PRECIO[prod],
                      cant * PRECIO[prod], llovio[f], disponible])

df = pd.DataFrame(filas, columns=["Fecha", "Guisado o bebida", "Cantidad vendida",
                                  "Precio unitario (MXN)", "Total vendido (MXN)",
                                  "Llovió", "Disponible"])
df.to_csv(SALIDA, index=False, encoding="utf-8-sig")
print(f"{len(df)} registros, {df['Fecha'].nunique()} días -> {SALIDA}")

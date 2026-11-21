"""
generar_pedidos.py
==================
Generador de datos sintéticos para la taquería "Las Cazuelitas" (Tecomán, Colima).
Propósito: simular ~12 meses de pedidos en línea calibrados con la entrevista real
a la dueña, Doña Rocío de la Cruz.

DATOS VALIDADOS DE LA ENTREVISTA CON LA DUEÑA:
  - Horario operativo: Martes a sábado, 7:00 a 12:00 h (domingo y lunes cerrado).
  - Volumen en días normales: ~30 pedidos únicos al día en promedio.
  - Volumen en días de quincena (1, 15, 16 y 30): ~60 pedidos únicos al día (DATO DE LA ENTREVISTA:
    la dueña confirmó que en quincena las ventas prácticamente se duplican respecto al día normal).
  - Reparto normal de tipo_entrega: 10 % llevar, 50 % comer aquí, 40 % domicilio.
  - Agotamiento a las 10:00 a.m.: El producto que se agota a las 10 a.m. según la dueña es
    la LENGUA (guisado configurable en catálogo interno; no incluido en el menú publicado).
    La Pepena es un guisado normal y se vende a lo largo de toda la jornada.
  - Estructura multi-línea: Un pedido (pedido_id único) agrupa 1 a 4 líneas de productos.

SUPUESTOS CUANTITATIVOS DEL MODELO:
  - Lluvia (junio a septiembre): La dueña indicó que el total de pedidos NO disminuye y que
    los pedidos a domicilio aumentan; la cifra del 70 % para entrega a domicilio en días lluviosos
    es un SUPUESTO DEL MODELO (la dueña solo confirmó el incremento, sin porcentaje exacto).
  - Crecimiento leve acumulado: +1.5 % por trimestre.

Errores intencionales sembrados (~5 % del total) para práctica de limpieza:
  1. Duplicados exactos de fila completa
  2. Nulos en columna 'cantidad' (~2 % filas)
  3. Totales que no cuadran (precio × cantidad ≠ total en ~3 % filas)
  4. Nombres de producto mal escritos
  5. Cantidades negativas (~1 % filas)
  6. Duplicados de pedido_id con discordancias (~1 % filas)

Autor: Equipo Analítica y Nube
Semilla reproducible: SEED = 42
"""

import uuid
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

# ── Semilla reproducible ──────────────────────────────────────────────────────
SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

# ── Rutas de salida ───────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_PATH = os.path.join(BASE_DIR, "pedidos_raw.csv")
SAMPLE_DIR = os.path.join(BASE_DIR, "..", "sample")
SAMPLE_PATH = os.path.join(SAMPLE_DIR, "pedidos_muestra.csv")

# ── Catálogo del menú ─────────────────────────────────────────────────────────
# Guisados oficiales del menú publicado
GUISADOS_PUBLICADOS = [
    "Pepena",
    "Carne de puerco con calabacita",
    "Chicharrón",
    "Machaca",
    "Carne de res a la mexicana",
    "Rajas con crema y elote",
    "Frijoles",
    "Huevo con jamón",
]

# Guisado configurable en catálogo interno (DATO ENTREVISTA: se agota a las 10 a.m.)
GUISADOS_CONFIGURABLES = ["Lengua"]

# Catálogo completo de guisados en el sistema
GUISADOS = GUISADOS_PUBLICADOS + GUISADOS_CONFIGURABLES

BEBIDAS = [
    "Agua fresca del día",
    "Coca-Cola",
    "Coca-Cola Light",
    "Squirt",
    "Fanta de Naranja",
    "Manzanita Sidral",
]

PRECIO_GUISADO = 20.0
PRECIO_BEBIDA = 25.0

# Probabilidades de guisados antes de las 10 a.m.:
# Lengua tiene alta demanda matutina (0.18). Pepena es un guisado normal y constante (0.18).
# Orden: [Pepena, Carne puerco, Chicharrón, Machaca, Res mex, Rajas, Frijoles, Huevo jamón, Lengua]
PROB_GUISADOS_ANTES_10 = np.array([0.18, 0.12, 0.18, 0.10, 0.08, 0.08, 0.04, 0.04, 0.18])

# Probabilidades después de las 10 a.m.:
# LENGUA SE AGOTA a las 10 a.m. (probabilidad cae a ~0.005, casi no se pide por falta de producto).
# Pepena se mantiene como guisado normal (0.22) junto a Chicharrón (0.22).
PROB_GUISADOS_DESPUES_10 = np.array([0.22, 0.15, 0.22, 0.12, 0.10, 0.10, 0.045, 0.04, 0.005])
PROB_GUISADOS_DESPUES_10 = PROB_GUISADOS_DESPUES_10 / PROB_GUISADOS_DESPUES_10.sum()

# Probabilidad de cada bebida
PROB_BEBIDAS = [0.25, 0.30, 0.10, 0.15, 0.10, 0.10]

# Reparto de tipo de entrega normal (DATO DE LA ENTREVISTA):
# 10 % llevar, 50 % aqui, 40 % domicilio
TIPOS_ENTREGA = ["llevar", "aqui", "domicilio"]
PROB_ENTREGA_NORMAL = [0.10, 0.50, 0.40]

# Reparto en lluvia (SUPUESTO DEL MODELO: la dueña indicó que sube domicilio, modelamos 70 %)
PROB_ENTREGA_LLUVIA = [0.10, 0.20, 0.70]

SALSAS = ["verde", "roja", "sin_salsa"]

ESTADOS = ["entregado", "cancelado"]
PROB_ESTADO = [0.95, 0.05]

rng_aux = np.random.default_rng(SEED + 25)


def generar_dias_lluvia(year: int) -> set:
    """Genera fechas con lluvia simulada en temporada jun–sep."""
    dias_lluvia = set()
    for mes in range(6, 10):  # jun, jul, ago, sep
        num_dias = pd.Period(f"{year}-{mes:02d}").days_in_month
        n_lluvia = max(1, int(num_dias * 0.35))
        dias_mes = [datetime(year, mes, d) for d in range(1, num_dias + 1)]
        elegidos = rng_aux.choice(dias_mes, size=n_lluvia, replace=False)
        dias_lluvia.update([d.date() for d in elegidos])
    return dias_lluvia


def es_quincena(dia: int) -> bool:
    """DATO DE LA ENTREVISTA: Días de quincena son el 15, 16, 30 y 1 de cada mes."""
    return dia in {1, 15, 16, 30}


def factor_trimestre(fecha: datetime) -> float:
    """Crecimiento trimestral leve de 1.5 %."""
    trimestre = (fecha.month - 1) // 3
    return 1.0 + 0.015 * trimestre


def pedidos_dia(fecha: datetime, dias_lluvia: set) -> int:
    """
    Calcula el número de PEDIDOS ÚNICOS (pedido_id) para un día operativo:
    - Día normal (mar–sáb fuera de quincena): ~30 pedidos (DATO DE LA ENTREVISTA).
    - Día de quincena (1, 15, 16, 30 si es mar–sáb): ~60 pedidos (DATO DE LA ENTREVISTA: ventas se duplican).
    - En lluvia: el volumen no baja (validado en entrevista).
    """
    if es_quincena(fecha.day):
        # DATO ENTREVISTA: ~60 pedidos en quincena
        base = float(rng.normal(loc=60.0, scale=4.0))
        base = max(base, 48.0)
    else:
        # DATO ENTREVISTA: ~30 pedidos en día normal
        base = float(rng.normal(loc=30.0, scale=3.0))
        base = max(base, 22.0)

    # Crecimiento leve a lo largo del año
    base *= factor_trimestre(fecha)

    return int(round(base))


def hora_aleatoria(fecha: datetime) -> datetime:
    """
    Horario de atención: 7:00 a 12:00 h.
    Pico matutino temprano (7 a 10 h) con mayor intensidad los martes, jueves y viernes.
    """
    dow = fecha.isoweekday()  # 2=mar, 4=jue, 5=vie
    if dow in {2, 4, 5}:
        if rng.random() < 0.70:
            hora = int(rng.integers(7, 10))
        else:
            hora = int(rng.integers(10, 12))
    else:
        hora = int(rng.integers(7, 12))

    minuto = int(rng.integers(0, 60))
    segundo = int(rng.integers(0, 60))
    return fecha.replace(hour=hora, minute=minuto, second=segundo)


def generar_pedidos() -> pd.DataFrame:
    """
    Genera dataset de pedidos con calibración estricta de la entrevista:
    - ~30 pedidos/día normal, ~60 pedidos/día quincena (mar–sáb).
    - Domingo y lunes cerrado.
    - Reparto tipo_entrega: 10% llevar, 50% aqui, 40% domicilio (lluvia: 70% domicilio como supuesto).
    - LENGUA se agota a las 10 a.m. (Pepena es guisado normal todo el día).
    """
    print("Generando pedidos sintéticos con calibración final de entrevista...")

    fecha_inicio = datetime(2024, 1, 1)
    fecha_fin = datetime(2024, 12, 31)

    # Días operativos: Martes (2) a Sábado (6)
    dias_habiles = [
        fecha_inicio + timedelta(days=d)
        for d in range((fecha_fin - fecha_inicio).days + 1)
        if (fecha_inicio + timedelta(days=d)).isoweekday() in {2, 3, 4, 5, 6}
    ]

    dias_lluvia = generar_dias_lluvia(2024)

    n_clientes = 300
    clientes = [str(uuid.UUID(int=int(rng.integers(0, 2**63)))) for _ in range(n_clientes)]

    filas = []
    conteo_pedidos_totales = 0
    conteo_dias_normales = 0
    conteo_pedidos_normales = 0
    conteo_dias_quincena = 0
    conteo_pedidos_quincena = 0

    for fecha in dias_habiles:
        es_dia_lluvioso = fecha.date() in dias_lluvia
        n_pedidos = pedidos_dia(fecha, dias_lluvia)
        conteo_pedidos_totales += n_pedidos

        if es_quincena(fecha.day):
            conteo_dias_quincena += 1
            conteo_pedidos_quincena += n_pedidos
        else:
            conteo_dias_normales += 1
            conteo_pedidos_normales += n_pedidos

        # Proporción de entrega según lluvia (70% domicilio en lluvia es SUPUESTO DEL MODELO)
        probs_entrega = PROB_ENTREGA_LLUVIA if es_dia_lluvioso else PROB_ENTREGA_NORMAL

        for _ in range(n_pedidos):
            pedido_id = str(uuid.uuid4())
            cliente_id = random.choice(clientes)
            tipo_entrega = rng.choice(TIPOS_ENTREGA, p=probs_entrega)
            estado = rng.choice(ESTADOS, p=PROB_ESTADO)
            fecha_hora = hora_aleatoria(fecha)

            # 1 a 4 líneas de detalle por pedido
            n_lineas = int(rng.choice([1, 2, 3, 4], p=[0.20, 0.45, 0.25, 0.10]))

            # LENGUA se agota a las 10 a.m. (DATO ENTREVISTA)
            if fecha_hora.hour < 10:
                prob_guisados_hora = PROB_GUISADOS_ANTES_10
            else:
                prob_guisados_hora = PROB_GUISADOS_DESPUES_10

            for _ in range(n_lineas):
                if rng.random() < 0.65:
                    categoria = "guisado"
                    producto = rng.choice(GUISADOS, p=prob_guisados_hora)
                    precio_unitario = PRECIO_GUISADO
                    salsa = rng.choice(["verde", "roja"], p=[0.55, 0.45])
                else:
                    categoria = "bebida"
                    producto = rng.choice(BEBIDAS, p=PROB_BEBIDAS)
                    precio_unitario = PRECIO_BEBIDA
                    salsa = "sin_salsa"

                cantidad = int(rng.choice([1, 2, 3, 4, 5], p=[0.35, 0.35, 0.18, 0.08, 0.04]))
                total_linea = round(precio_unitario * cantidad, 2)

                filas.append({
                    "pedido_id": pedido_id,
                    "fecha_hora": fecha_hora.strftime("%Y-%m-%d %H:%M:%S"),
                    "cliente_id": cliente_id,
                    "tipo_entrega": tipo_entrega,
                    "producto": producto,
                    "categoria": categoria,
                    "cantidad": cantidad,
                    "precio_unitario": precio_unitario,
                    "salsa": salsa,
                    "total": total_linea,
                    "estado": estado,
                })

    df = pd.DataFrame(filas)
    prom_normal = conteo_pedidos_normales / max(1, conteo_dias_normales)
    prom_quincena = conteo_pedidos_quincena / max(1, conteo_dias_quincena)

    print(f"  Total pedidos únicos generados: {conteo_pedidos_totales:,}")
    print(f"  Líneas de detalle generadas: {len(df):,}")
    print(f"  Promedio en día normal: {prom_normal:.1f} pedidos/día")
    print(f"  Promedio en día de quincena: {prom_quincena:.1f} pedidos/día")
    return df


def sembrar_errores(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Siembra errores intencionales (~5 % del total) para validar pipeline de limpieza."""
    reporte = {}
    n = len(df)
    df = df.copy()

    # 1. Duplicados exactos (~1.5 % filas)
    n_dup = max(1, int(n * 0.015))
    idx_dup = rng.choice(df.index, size=n_dup, replace=False)
    duplicados = df.loc[idx_dup].copy()
    df = pd.concat([df, duplicados], ignore_index=True)
    reporte["duplicados_exactos"] = n_dup

    # 2. Nulos en cantidad (~2 % filas)
    n_nulos = max(1, int(n * 0.02))
    idx_nulos = rng.choice(df.index, size=n_nulos, replace=False)
    df.loc[idx_nulos, "cantidad"] = np.nan
    reporte["nulos_cantidad"] = n_nulos

    # 3. Totales que no cuadran (~3 % filas)
    n_total_mal = max(1, int(n * 0.03))
    idx_total = rng.choice(df.index, size=n_total_mal, replace=False)
    df.loc[idx_total, "total"] = (df.loc[idx_total, "total"] * rng.uniform(0.6, 1.4, size=n_total_mal)).round(2)
    reporte["totales_incorrectos"] = n_total_mal

    # 4. Nombres mal escritos
    nombres_mal = {
        "Chicharrón": "chicharron",
        "Pepena": "pepena",
        "Lengua": "lengua",
        "Rajas con crema y elote": "Rajas con Crema",
        "Machaca": "machaca",
        "Frijoles": "frijoles",
        "Agua fresca del día": "agua fresca",
    }
    n_nombres = 0
    for nombre_correcto, nombre_errado in nombres_mal.items():
        idx_prod = df[df["producto"] == nombre_correcto].index
        if len(idx_prod) == 0:
            continue
        n_cambiar = max(1, int(len(idx_prod) * 0.08))
        idx_cambiar = rng.choice(idx_prod, size=n_cambiar, replace=False)
        df.loc[idx_cambiar, "producto"] = nombre_errado
        n_nombres += n_cambiar
    reporte["nombres_mal_escritos"] = n_nombres

    # 5. Cantidades negativas (~1 % filas)
    n_neg = max(1, int(n * 0.01))
    idx_neg = rng.choice(df.index, size=n_neg, replace=False)
    df.loc[idx_neg, "cantidad"] = df.loc[idx_neg, "cantidad"].apply(
        lambda x: -abs(x) if pd.notna(x) else x
    )
    reporte["cantidades_negativas"] = n_neg

    # 6. Duplicados de pedido_id (~1 % filas)
    n_id_dup = max(1, int(n * 0.01))
    ids_existentes = df["pedido_id"].sample(n_id_dup, random_state=42).values
    idx_target = rng.choice(df.index, size=n_id_dup, replace=False)
    df.loc[idx_target, "pedido_id"] = ids_existentes
    reporte["duplicados_pedido_id"] = n_id_dup

    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    return df, reporte


def guardar_muestra(df: pd.DataFrame, path: str, n: int = 100) -> None:
    """Guarda muestra anonimizada."""
    muestra = df.sample(n=min(n, len(df)), random_state=SEED).copy()
    muestra["cliente_id"] = "cliente_anonimizado"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    muestra.to_csv(path, index=False, encoding="utf-8")
    print(f"  Muestra anonimizada guardada en: {path}")


if __name__ == "__main__":
    df_base = generar_pedidos()
    df_con_errores, reporte_errores = sembrar_errores(df_base)

    print(f"\nTotal registros en archivo raw (con errores sembrados): {len(df_con_errores):,}")
    print("Resumen de errores sembrados:")
    for clave, valor in reporte_errores.items():
        print(f"  - {clave}: {valor}")

    os.makedirs(os.path.dirname(RAW_PATH), exist_ok=True)
    df_con_errores.to_csv(RAW_PATH, index=False, encoding="utf-8")
    print(f"\nArchivo raw guardado en: {RAW_PATH}")

    guardar_muestra(df_con_errores, SAMPLE_PATH, n=100)
    print("¡Generación completada exitosamente!")

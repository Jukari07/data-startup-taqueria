# DATA STARTUP – Predicción de demanda para una taquería

Proyecto Integrador (Cómputo en la Nube IAD-2408 x Analítica IAD-2403).

## Problema
Predecir `cantidad_vendida` (regresión) por guisado/bebida y día, para ayudar a la dueña
a decidir cuánto cocinar y cuánta tortilla comprar.

## Estructura
- `avance1_eda_taqueria.ipynb`: Avance 1 (definición del problema + EDA).
- `generar_ventas_taqueria_v3.py`: generador calibrado con la entrevista a la dueña.
- `data/ventas_tacos_8_semanas.csv`: dataset sintético (672 registros, 8 semanas × 12 productos).
- `data/ventas_tacos_4_semanas.csv`: dataset inicial de 4 semanas (336 registros).

## Cómo ejecutarlo
Instala las dependencias, copia el CSV junto al notebook y ábrelo:

    pip install -r requirements.txt
    cp data/ventas_tacos_8_semanas.csv .
    jupyter notebook avance1_eda_taqueria.ipynb

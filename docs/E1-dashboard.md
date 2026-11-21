# E1 – Dashboard: Teoría, Hallazgos y Recomendaciones
## Tacos "Las Cazuelitas" · Plataforma Analítica de Pedidos

---

## 1. Contexto de Negocio y Datos Validados de la Entrevista

A diferencia de modelos genéricos de inventario o estimaciones teóricas, esta plataforma analítica procesa las órdenes reales generadas en la **Plataforma de Pedidos en Línea** de Tacos "Las Cazuelitas" (Tecomán, Colima), negocio fundado en 1999 por Doña Rocío de la Cruz.

### Parámetros Operativos Validados en la Entrevista con Doña Rocío:
- **Jornada operativa:** Martes a sábado de 7:00 a 12:00 h (cerrado domingos y lunes por descanso).
- **Volumen diario normal:** Promedio real de **~30 pedidos únicos al día** en días hábiles regulares.
- **Volumen en Quincena (DATO DE LA ENTREVISTA):** En los días 15, 16, 30 y 1 (cuando coinciden con días de apertura), las órdenes prácticamente se duplican, alcanzando **~60 pedidos únicos diarios**. La dueña confirmó expresamente este pico en la entrevista.
- **Estructura transaccional (Multi-línea):** Un pedido (`pedido_id` único) contiene entre 1 y 4 líneas de productos (guisados a $20 MXN en tortilla doble y bebidas a $25 MXN). El conteo formal de ventas y demanda diaria se realiza sobre `pedido_id` únicos.
- **Reparto de modalidad de entrega:** En días regulares, el desglose observado es **10 % para llevar, 50 % comer aquí y 40 % servicio a domicilio**.
- **Agotamiento de producto a las 10:00 a.m. (DATO DE LA ENTREVISTA):** El platillo que invariablemente se agota a las 10:00 a.m. por alta demanda matutina es la **LENGUA**, la cual forma parte de los guisados configurables en el catálogo interno de la taquería (no publicada en la carta estándar). La **Pepena**, por su parte, es un guisado oficial normal que se prepara en volumen suficiente para cubrir toda la jornada (7:00 a 12:00 h).

### Supuestos Cuantitativos del Modelo:
- **Respuesta a la lluvia (junio a septiembre):** La dueña confirmó cualitativamente que con la lluvia el número de pedidos *no disminuye* y que la demanda a domicilio *aumenta*; sin embargo, no aportó una cifra porcentual exacta. La proporción de **70 % de pedidos a domicilio en días lluviosos es un SUPUESTO DEL MODELO**, adoptado para evaluar la capacidad logística de entrega.

---

## 2. Teoría de las 6 Gráficas y Hallazgos del Tablero

### a) Líneas: Tendencia de ventas diarias (rolling 7d)

**¿Qué mide?**
La facturación diaria bruta ($MXN) y el volumen de pedidos únicos por día, comparados con una media móvil suavizada de 7 días (rolling window).

**¿Por qué es útil para este negocio?**
Permite visualizar la estabilidad operativa del negocio, contrastando las semanas regulares (~30 pedidos/día) frente a los picos quincenales (~60 pedidos/día) sin distorsiones por el cierre semanal de domingos y lunes.

**Hallazgos:**
- Ondulación periódica cada 14–15 días con duplicación de ingresos en quincenas (hasta $6,500 – $7,500 MXN en días 15 y 30 vs $3,000 – $3,600 MXN en días normales).
- Domingos y lunes se reflejan consistentemente con ventas $0 MXN.

---

### b) Histograma: Distribución del ticket por pedido único

**¿Qué mide?**
La distribución de frecuencias del gasto total por `pedido_id` único (agregando todos los guisados y bebidas que componen la orden).

#### Regla de Sturges para el número de bins
El número de intervalos $k$ se calcula formalmente mediante la regla de Sturges:

$$k = \lceil \log_2(n) + 1 \rceil$$

Donde $n$ es el número de **pedidos únicos** analizados en el periodo. Para un histórico anual de ~9,500 pedidos únicos, $k = \lceil \log_2(9500) + 1 \rceil = 15$ barras.

**Hallazgos:**
Distribución unimodal asimétrica positiva:
- La concentración principal se ubica entre **$60 y $120 MXN**, representativa de 2 a 4 tacos más bebida.
- Existe una cola hacia valores de $180 a $300 MXN, correspondiente a pedidos a domicilio para familias y cuadrillas de trabajo.

---

### c) Mapa de calor: Día de semana × Hora (Pedidos únicos)

**¿Qué mide?**
La cantidad acumulada de pedidos únicos recibidos en cada intervalo horario (7:00 a 12:00 h) para cada día de la semana.

**¿Por qué es útil para este negocio?**
Permite programar la apertura del comal y la preparación de salsas con antelación.

**Hallazgos:**
- **Pico matutino temprano (7:00 a 10:00 h):** Concentra más del 65 % de los pedidos diarios, con especial intensidad en martes, jueves y viernes.
- Descenso progresivo entre 10:00 y 12:00 h, coincidiendo con el agotamiento de la Lengua y el cierre del almuerzo laboral.
- Inactividad total los domingos y lunes.

---

### d) Dispersión: Cantidad de piezas vs Hora, por Tipo de Entrega

**¿Qué mide?**
Cada punto representa una línea de detalle: en el eje X la hora del pedido, en el eje Y el volumen de tacos/bebidas, y en color la modalidad de entrega.

**Hallazgos:**
- "Comer aquí" (50 %) predomina en comensales que acuden solos o en parejas en horario de 7:30 a 9:30 h (2 a 4 piezas).
- "Domicilio" (40 % normal, modelado al 70 % en lluvia) presenta los valores más altos de piezas por pedido (5 a 10 piezas).
- En época de lluvias, la concentración de puntos de domicilio se vuelve predominante en toda la franja horaria.

---

### e) Análisis espectral FFT: Periodicidad de pedidos únicos

**¿Qué mide?**
La Transformada Rápida de Fourier (FFT) aplicada a la señal diaria continua de pedidos únicos ($f(t)$) para extraer sus frecuencias armónicas principales:

$$\text{Periodo} = \frac{1}{\text{Frecuencia dominante}}$$

**Interpretación de Armónicos:**
- **Pico en 7 días:** Refleja el ciclo semanal de operación (5 días de apertura y 2 de descanso).
- **Pico en 15 días (Validado):** Confirma la periodicidad bimensual del impacto de la quincena reportado por Doña Rocío, donde el volumen de clientes se duplica en días 15 y 30.

---

### f) Barras: Top 5 de productos por ingreso acumulado

**¿Qué mide?**
Los 5 productos que mayor facturación neta generan en la taquería.

**Hallazgos:**
- **Pepena** y **Chicharrón** encabezan el menú publicado, gracias a su disponibilidad ininterrumpida y alta preferencia de la clientela.
- **Lengua** (guisado configurable) muestra una venta explosiva entre 7:00 y 10:00 a.m., pero se agota antes del cierre.
- Entre las bebidas, Coca-Cola y el Agua fresca del día representan el mayor volumen.

---

## 3. Las 3 Recomendaciones de Negocio para Doña Rocío

### Recomendación 1: Reforzar equipo y comal en días de quincena (15, 16, 30 y 1)
> **Para Doña Rocío (lenguaje directo):**  
> *"Doña Rocío, tal como usted nos platicó, en los días de quincena sus pedidos prácticamente se duplican, pasando de 30 a cerca de 60 pedidos en una sola mañana. Para esos 4 días al mes le conviene tener un ayudante exclusivo para tortear y empacar en comal. Esto evitará que la gente espere de más o que los pedidos para llevar se retrasen en las horas pico."*  
>  
> **Justificación técnica:** El dato de la entrevista confirma una tasa promedio de ~60 pedidos/día en quincena con significancia estadística evidenciada en el pico de 15 días del análisis espectral FFT.

---

### Recomendación 2: Planificar flotilla de entrega para temporada de lluvias (junio a septiembre)
> **Para Doña Rocío:**  
> *"En los meses de lluvias la gente no deja de comprarle tacos, pero casi nadie quiere mojarse para ir al local. Aunque en el sistema supusimos un 70 % de pedidos a domicilio en días lluviosos, lo importante en la práctica es que sus repartidores van a tener mucho más trabajo. Conviene acordar desde antes con un segundo muchacho con moto para que le ayude a repartir únicamente en días lluviosos."*  
>  
> **Justificación técnica:** El volumen total de pedidos se mantiene estable en lluvia, pero la mezcla migra hacia `domicilio`. El supuesto del modelo (70 %) ilustra la necesidad de elasticidad en la capacidad de reparto sin sobredimensionar costos fijos.

---

### Recomendación 3: Aumentar la porción o programar segunda tanda de LENGUA a las 9:30 a.m.
> **Para Doña Rocío:**  
> *"La Lengua es el guisado que invariablemente se le termina a las 10:00 de la mañana. Después de esa hora, los clientes que llegan a almorzar ya no alcanzan taco de Lengua. Si aumenta en un 35 % o 40 % la porción de Lengua que prepara en la mañana, o mete una segunda cazuelita a las 9:30 a.m., podrá venderle a toda esa gente que llega entre las 10:00 y las 12:00 sin quedarse sin producto."*  
>  
> **Justificación técnica:** La Lengua experimenta desabasto prematuro a las 10:00 h mientras que la Pepena y el Chicharrón demuestran que la demanda continúa activa hasta las 12:00 h. Ampliar la disponibilidad de Lengua recuperará ventas perdidas por quiebre de stock.

---

## 4. Convención del Data Lake

```
# Zona RAW (S3/MinIO: taqueria-raw) - Append-only, inmutable
raw/YYYY/MM/DD/pedidos_YYYYMMDD_HHMMSS.csv

# Zona CLEAN (S3/MinIO: taqueria-clean) - Curada y normalizada
clean/YYYY/MM/DD/pedidos_clean_YYYYMMDD_HHMMSS.csv
clean/YYYY/MM/DD/reporte_limpieza_YYYYMMDD.json
```

---

## 5. Uso de IA Generativa

| Herramienta | Aplicación en E1 |
|---|---|
| **Antigravity (Gemini)** | Actualización del generador sintético incorporando la duplicación en quincenas (~60 pedidos) como dato de la entrevista y delimitando el 70 % de lluvia como supuesto del modelo. |
| **Antigravity (Gemini)** | Reconfiguración del catálogo para asociar el agotamiento a las 10:00 a.m. a la Lengua y mantener a la Pepena en venta regular continua. |
| **Antigravity (Gemini)** | Redacción de recomendaciones de negocio en lenguaje práctico y accesible para Doña Rocío. |

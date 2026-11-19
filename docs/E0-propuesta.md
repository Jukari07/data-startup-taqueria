# E0 · Propuesta — Tacos Las Cazuelitas

**Proyecto Integrador DATA STARTUP** · Cómputo en la Nube (IAD-2408) × Analítica de Datos (IAD-2403)

## Equipo

| Integrante | Rol |
|---|---|
| Jukari Molinero De la Cruz | Cloud Lead y Data Lead (equipo de una persona) |

**Cliente:** Tacos Las Cazuelitas, de María Rocío De la Cruz Laurel
Lázaro Cárdenas #10, colonia Unión, Tecomán, Colima.

**Proveedor de nube elegido:** [elegir uno: AWS o Azure]

**Repositorio:** https://github.com/Jukari07/data-startup-taqueria

---

## 1. Problema y cliente

Rocío De la Cruz Laurel tiene una taquería de tacos de guisado desde hace 25 años. Hoy decide a ojo cuánta carne, qué tortilla y qué bebidas o refrescos comprar y preparar cada día. Cuando compra de más, desperdicia producto; cuando compra de menos, se queda sin carne y pierde ventas.

**Número que le vamos a dar:** cuántas piezas de cada guisado y bebida venderá cada día de la próxima semana, para que compre justo lo necesario.

### Entrevista con el cliente

**Fecha y medio de la entrevista:** [completar]

| Pregunta | Respuesta | Qué aprendimos |
|---|---|---|
| ¿Cuánto producto tiras o se echa a perder por semana? | Si acaso el agua; la comida la hacemos un día antes o todo al momento. | Casi no hay merma de comida. El problema principal no es el desperdicio, sino quedarse sin producto. |
| ¿Qué días y horas se venden más? ¿Cambian por quincena o con el clima? | Martes, jueves y viernes de 7 a 10. En quincena aumenta y baja cuando llueve. También manejan pedidos a domicilio. Lo sabe por experiencia. | Descansan domingo y lunes. Las ventas suben martes, jueves y viernes, en quincena, y bajan con lluvia. |
| ¿Cómo decides cuánta carne y tortilla comprar? | Por la cantidad de tacos del día, y de ahí me baso para los kilos de tortilla. | Estima los tacos del día y de ahí calcula la tortilla. No usa un registro ni un método, solo experiencia. |
| ¿Qué te gustaría saber antes de comprar que hoy no sabes? | La cantidad de comida que venderé. | Quiere un pronóstico de ventas con buena exactitud. |
| Si una herramienta te lo dijera, ¿cuánto pagarías al mes? | Estaría dispuesta a pagar $1,000. | Precio de referencia: $1,000 MXN al mes. |

### Lean Canvas

| Bloque | Contenido |
|---|---|
| Problema | La dueña decide cuánto comprar de tortilla y carne por experiencia, sin saber cuántos tacos venderá cada día. La demanda cambia por día, quincena, lluvia y pedidos a domicilio. |
| Segmento de clientes | Taquerías y fondas pequeñas de Tecomán con 1 a 3 empleados que cocinan al día. Cliente inicial: Tacos Las Cazuelitas. |
| Propuesta de valor | Sabe cuántos tacos vas a vender: pronóstico semanal por producto para planear tus compras, desde tu celular. |
| Solución | Tablero y pronóstico alimentados con las ventas diarias (CSV o API), que consideran día de la semana, quincena y lluvia. |
| Canales | Recomendación de boca en boca, WhatsApp y otras taquerías de la zona. |
| Fuentes de ingreso | Suscripción mensual de $1,000 MXN. |
| Estructura de costos | Nube (capas gratuitas por ahora), costo por cliente (se calcula en E5), tiempo de soporte y mantenimiento de los datos. |
| Métricas clave | Error del pronóstico (MAE/RMSE), días en que se agotó producto y diferencia entre lo comprado y lo vendido. |
| Ventaja injusta | Acceso directo a un negocio local real y una herramienta sencilla pensada para dueños que no son técnicos. |

---

## 2. Cadena de preguntas

| Eslabón | Contenido |
|---|---|
| Pregunta de negocio | ¿Cuánto guisado cocino y cuánta tortilla compro cada día para no quedarme sin producto ni comprar de más? |
| Pregunta analítica | ¿Cuántas piezas de cada guisado y bebida se venderán cada día durante la próxima semana? |
| Variable a predecir | `Cantidad vendida`: piezas vendidas por producto por día. Horizonte: 7 días. Alternativa agregada: demanda total diaria. |
| Cómo se mide el éxito | Error de predicción (MAE/RMSE) menor que el de una regla simple, como el promedio histórico del producto. |

---

## 3. Inventario de datos

| Campo | Descripción |
|---|---|
| Fuente | La taquería no lleva registro de ventas (ni cuaderno ni sistema), por lo que **no existen datos reales de ventas**. Se usan datos **sintéticos** generados con `generar_ventas_taqueria_v3.py` (8 semanas, calibrados con las respuestas de la entrevista: días fuertes, quincena y lluvia) y extendidos hacia atrás con `generar_ventas_taqueria_extendido.py`, que repite los patrones de esas 8 semanas con ruido aleatorio. La lluvia de los meses anteriores se simuló por temporada (más de junio a octubre). Si la dueña empieza a anotar sus ventas, los datos reales sustituyen a los sintéticos. |
| Columnas | `Fecha`, `Guisado o bebida` (12 productos), `Cantidad vendida`, `Precio unitario (MXN)`, `Total vendido (MXN)` (cantidad × precio), `Llovió` (1 = día con lluvia, 0 = sin lluvia). |
| Variable agregada | `Llovió`, a partir de lo que dijo la dueña sobre cómo baja la venta cuando llueve. Los pedidos a domicilio se incorporarán más adelante. |
| Periodo | 2 de septiembre de 2025 al 24 de octubre de 2026 (más de 14 meses, de martes a sábado, porque la taquería descansa domingo y lunes). |
| Volumen | 3,600 registros (12 productos × 300 días de venta). |
| Privacidad | No hay datos personales de clientes (sin nombres, teléfonos ni direcciones). En el repositorio solo se sube una muestra pequeña. |

---

## 4. Arranque técnico

| Elemento | Estado |
|---|---|
| Cuenta de nube con alerta de presupuesto activa | ☐ Captura en `docs/img/presupuesto.png` |
| Repositorio en GitHub con commits del integrante | ✅ `Jukari07/data-startup-taqueria` |
| Estructura inicial | ☐ `docs/`, `data/sample/`, `notebooks/`, `services/`, `infra/terraform/`, `k8s/`, `tests/` |
| Estimación de costos con la calculadora del proveedor (tema 1.1.4) | ☐ Costo mensual estimado: [___] |

---

## Uso de IA generativa

**Herramienta:** Claude (Anthropic).
**Uso:** ayuda para estructurar este documento y para adaptar el generador de datos sintéticos.
Todo lo entregado lo podemos explicar en la defensa.

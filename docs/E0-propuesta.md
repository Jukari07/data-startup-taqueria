# E0 · Propuesta de Plataforma de Pedidos y Analítica
## Tacos "Las Cazuelitas" · Tecomán, Colima

**Equipo:** Jukari Molinero De la Cruz (Cloud Lead y Data Lead; equipo individual)
**Materias:** Cómputo en la Nube (IAD-2408) × Analítica de Datos (IAD-2403)
**Fecha de entrega:** 16 de octubre de 2026 · **Proveedor de nube elegido:** AWS

---

## 1. Problema y cliente

**Cliente:** Rocío de la Cruz, fundadora de Tacos "Las Cazuelitas", en Tecomán, Colima, vende tacos de guisado de martes a sábado, de 7:00 a 12:00 h, es tia de jukari, lo que da acceso directo al negocio

**Menú:** 8 guisados a $20 MXN (Pepena, Carne de puerco con calabacita, Chicharrón, Machaca, Carne de res a la mexicana, Rajas con crema y elote, Frijoles, Huevo con jamón) y 6 bebidas a $25 MXN

**Situación actual (según la entrevista):**
- Recibe en promedio **30 pedidos en un día normal**.
- Cada pedido se atiende por teléfono o en el local, y no queda ningún registro digital.
- Los pedidos se reparten así: **10 % para llevar, 50 % para comer en el local y 40 % a domicilio**.
- **la lengua se agotan a las 10 a.m.** (por confirmar si la lengua es un guisado del día que no aparece en el menú publicado)
- Los pedidos a domicilio **aumentan** en temporada de lluvias, aunque el total no baja

**Problema central:** la dueña decide cuánto preparar y cuándo tener repartidor por experiencia, sin datos. Como el 40 % de los pedidos es a domicilio y los guisados más pedidos se agotan temprano, hay clientes que llegan o piden cuando ya no hay

**Supuestos por validar** existen errores al anotar pedidos por teléfono, se validarán con los datos reales de la plataforma

**Decisión que se quiere ayudar a tomar:** cuántos pedidos esperar por franja horaria para preparar la cantidad correcta de cada guisado y organizar el reparto

**Producto:** una plataforma web donde el cliente ve el menú y hace su pedido, y la dueña ve un tablero con sus pedidos. Cada pedido queda registrado y alimenta la analítica de forma automática, sin trabajo extra. Ya existe una primera versión del sitio con el menú, el registro y el inicio de sesión, publicada en Azure; este proyecto construye la plataforma de datos que la rodea

---

## 2. Entrevista con la dueña

**Entrevistada:** Doña Rocío de la Cruz · **Fecha:** [10 de octubre del 2026] · **Duración:** [15 minutos]

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿Cuántos pedidos recibe en un día normal y cuántos en quincena? | Unos 30 pedidos en un día normal y en quincena unos 60|
| 2 | ¿Cuál es el guisado que más le piden y a qué hora se agota? | La lengua se agotan a las 10. |
| 3 | ¿Cuántos piden para llevar, comen ahí o piden a domicilio? | 10 % para llevar, 50 % comen ahí y 40 % a domicilio. |
| 4 | ¿Bajan los pedidos en temporada de lluvias? | No bajan, pero aumentan los pedidos a domicilio |
| 5 | ¿Pagaría una suscripción mensual por una plataforma de pedidos con reporte semanal? ¿Cuánto? | Sí, $1,000 MXN al mes|

**Lo que aprendimos:**
1. El volumen es pequeño (30 pedidos al día), así que el modelo de negocio debe tener costos de nube muy bajos
2. El domicilio pesa mucho (40 %), por lo que la plataforma debe tratarlo como un canal principal
3. Los guisados se agotan temprano, lo que hace útil un pronóstico por franja horaria
4. Hay disposición de pago confirmada: $1,000 MXN al mes

**Pendientes con la dueña:** confirmar si la lengua es un guisado del día

---

## 3. Lean Canvas

| Bloque | Contenido |
|---|---|
| **Problema** | 1. Los pedidos no quedan registrados, así que no hay datos para decidir. 2. Los guisados más pedidos se agotan a las 10 a.m. sin que se anticipe. 3. El 40 % de los pedidos es a domicilio y se coordina sin sistema |
| **Segmento de clientes** | Taquerías y fondas familiares de ciudades medias, con 1 a 3 empleados y unos 30 a 100 pedidos al día. Cliente inicial: Las Cazuelitas, en Tecomán |
| **Propuesta de valor** | Pedidos en línea que se convierten solos en un tablero y en un pronóstico de pedidos por hora, para preparar lo justo y organizar el reparto |
| **Solución** | Sitio de pedidos con menú y carrito, API en la nube, tablero para la dueña y modelo de pronóstico de pedidos |
| **Canales** | El sitio propio, el teléfono, la página de Facebook del negocio, WhatsApp y recomendación entre taquerías. |
| **Fuentes de ingreso** | Suscripción mensual de $1,000 MXN por negocio (precio que la dueña dijo que pagaría)|
| **Estructura de costos** | Nube (AWS, capa gratuita y servicios de bajo costo; se calculará en E5 con la calculadora oficial), dominio y soporte. Desarrollo a cargo del equipo estudiantil |
| **Métricas clave** | Pedidos por día, ticket promedio, guisado más pedido, porcentaje de pedidos a domicilio, hora en que se agota cada guisado y clientes que repiten|
| **Ventaja injusta** | Acceso directo al negocio y a su dueña, un sitio con el menú real ya funcionando y conocimiento del giro obtenido en la entrevista|

---

## 4. Cadena de preguntas

**Cadena principal (la variable que se predice en E3):**

| Nivel | Contenido |
|---|---|
| Pregunta de negocio | ¿Cuánto debo preparar y cuándo necesito repartidor esta semana? |
| Pregunta analítica | ¿Cuántos pedidos llegarán por día y por franja horaria en los próximos 7 días? |
| Variable a predecir | `pedidos_por_dia` y `pedidos_por_franja` (unidad: pedidos; horizonte: 7 días) |

**Preguntas de apoyo para el tablero (E1):**

| Pregunta de negocio | Pregunta analítica | Variable |
|---|---|---|
| ¿Qué guisado debo preparar más? | ¿Cuál acumula más pedidos e ingreso? | `SUM(cantidad)` y `SUM(total)` por `producto` |
| ¿A qué hora se me agota cada guisado? | ¿A qué hora se acumula la mayoría de los pedidos de cada producto? | pedidos por `producto` y por hora |
| ¿Vale la pena el domicilio? | ¿El ticket promedio cambia según el tipo de entrega? | `AVG(total)` por `tipo_entrega` |
| ¿La lluvia cambia cómo piden? | ¿Aumenta la proporción de domicilio entre junio y septiembre? | proporción de `tipo_entrega = domicilio` por mes |
| ¿La quincena cambia mis ventas? | ¿Se duplican los pedidos en los días 15, 16, 30 y 1, como dice la dueña? | `es_quincena` (derivada de `fecha_hora`) |
| ¿Cuándo necesito más personal? | ¿Qué día y hora concentran los pedidos? | mapa de calor `dia_semana × hora` |

---

## 5. Inventario de datos

| Fuente | Columnas | Periodo | Volumen |
|---|---|---|---|
| Plataforma de pedidos (datos reales, una vez en operación) | `pedido_id`, `fecha_hora`, `cliente_id`, `tipo_entrega`, `producto`, `categoria`, `cantidad`, `precio_unitario`, `salsa`, `total`, `estado` | Desde el lanzamiento | Unos 30 pedidos al día (unos 60 en quincena) |
| Datos sintéticos (simulador `generar_pedidos.py`) | Las mismas columnas, con errores sembrados a propósito | Al menos 12 meses diarios | Al menos 5,000 registros |
| Catálogo del menú | `producto`, `categoria`, `precio_unitario` | Estático | 14 productos (8 guisados y 6 bebidas) |

**Cómo se generan los datos sintéticos:** el simulador se calibra con la entrevista: unos 30 pedidos por día normal y unos 60 en quincena, de martes a sábado, 10 % para llevar, 50 % en el local y 40 % a domicilio, más domicilio en la temporada de lluvias y agotamiento de la lengua a las 10 a.m. **Los datos son sintéticos; no se usaron datos personales de clientes.**

**Convención del data lake:**
- `raw/AAAA/MM/DD/pedidos_*.csv`: datos tal como llegan.
- `clean/AAAA/MM/DD/pedidos_clean_*.csv`: datos depurados.

---

## 6. Arranque técnico

- [x] Cuenta de AWS creada, con MFA activo en la cuenta raíz
- [ ] Un usuario IAM por integrante; la cuenta raíz no se usa para operar
- [x] Alerta de presupuesto activa, con aviso por correo
- [x] Repositorio en GitHub con commits de la integrante
- [ ] Estructura inicial del repositorio, `.env.example` y `.gitignore` que excluye `.env`, `*.tfstate` y los CSV completos

![Alerta de presupuesto](e0-alerta-presupuesto.png)
![MFA](evidencia/e0-mfa-cuenta-raiz.png)
![Usuario IAM](evidencia/e0-usuario-iam.png)

---

## 7. Modelo de ingresos

**Suscripción mensual (SaaS):** $1,000 MXN por negocio al mes, precio que la dueña dijo que pagaría en la entrevista

**Ejemplo conservador (a validar en E5 con la calculadora de AWS):**
- 10 negocios × $1,000 = $10,000 MXN al mes
- Costo de nube estimado: entre $150 y $300 MXN al mes para 10 negocios (supuesto por validar)
- Margen por cliente = Precio mensual − (Costo de nube mensual ÷ Número de clientes)

---

## 8. Uso de IA generativa

| Herramienta | Para qué se usó |
|---|---|
| Antigravity (agentes de código)| Generar el código, los tests y los borradores de la documentación a partir de un prompt con las especificaciones del proyecto |
| Claude (Anthropic) | Ayudar a redactar el prompt y explicar los pasos de configuración |

Todo lo generado fue revisado por el equipo. La entrevista y sus respuestas son de la persona entrevistada y no fueron generadas por IA.
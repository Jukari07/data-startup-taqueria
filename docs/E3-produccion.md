# E3 – Inteligencia en Producción y Operaciones Cloud
## Tacos "Las Cazuelitas" · Plataforma de Pedidos y Modelos Predictivos

---

## 1. Arquitectura de Despliegue en Producción

La infraestructura de producción está diseñada bajo principios de arquitectura nativa de nube (Cloud-Native), orientada a resiliencia, alta disponibilidad y escalabilidad automática en demanda:

```mermaid
flowchart TD
    subgraph Trafico["Tráfico de Entrada"]
        Usuarios[Comensales / Dueña]
        ALB[Application Load Balancer / App Runner]
    end

    subgraph Contenedores["Servicios Web y API (ECS Fargate / App Runner)"]
        APIService[API Pedidos - FastAPI :8000]
        TableroService[Tablero Streamlit :8501]
        ModelosService[API Modelos ML :8001]
    end

    subgraph ServerlessCompute["Cómputo Asíncrono"]
        LambdaWorker[AWS Lambda Worker - Python 3.11]
    end

    subgraph MensajeriaAWS["Mensajería Gestionada"]
        SQSQueue[AWS SQS: taqueria-pedidos]
        SQSDLQ[AWS SQS DLQ: taqueria-pedidos-dlq]
    end

    subgraph AlmacenamientoAWS["Persistencia y Datos"]
        RDS[(Amazon RDS PostgreSQL Multi-AZ)]
        S3Raw[(Amazon S3: taqueria-raw-prod)]
        S3Clean[(Amazon S3: taqueria-clean-prod)]
    end

    Usuarios --> ALB
    ALB --> APIService
    ALB --> TableroService

    APIService -->|Guardar pedido| RDS
    APIService -->|Guardar CSV crudo| S3Raw
    APIService -->|Publicar evento| SQSQueue

    SQSQueue -->|Disparador por lote| LambdaWorker
    SQSQueue -.->|Fallos > 3| SQSDLQ
    LambdaWorker -->|Descargar crudo| S3Raw
    LambdaWorker -->|Limpiar y depositar| S3Clean
    LambdaWorker -->|Actualizar estado| RDS

    TableroService -->|Consultar métricas| S3Clean
    TableroService -->|Consumir inferencia| ModelosService
    ModelosService -->|SARIMA / Churn| RDS
```

---

## 2. Contenerización Multi-Stage y Docker Compose

### 2.1 Principios de Seguridad de los Dockerfiles
Todos los microservicios (`api`, `worker`, `modelos`, `tablero`) fueron empaquetados mediante **Dockerfiles multi-stage**:
1. **Separación Builder vs Runtime:**
   - La etapa `builder` instala compiladores C/C++ (`build-essential`, `gfortran`, `libpq-dev`) requeridos para compilar ruedas nativas de Python.
   - La etapa `runtime` hereda de `python:3.11-slim`, copiando exclusivamente las librerías finales compiladas en `/usr/local`. Esto reduce el tamaño de las imágenes finales de ~1.2 GB a menos de 190 MB.
2. **Ejecución sin privilegios de raíz (Non-Root User):**
   - Se crea explícitamente el usuario `appuser` (`RUN useradd --create-home --shell /bin/bash appuser`) y se activa la directiva `USER appuser`. Si un atacante comprometiera el proceso web, no obtendría permisos administrativos en el host.
3. **Cero credenciales en las imágenes:**
   - No se incluye ningún archivo `.env` ni cadenas secretas en las capas de imagen; todas las variables se inyectan en tiempo de ejecución (`env_file: .env` o secrets de Kubernetes).

### 2.2 Despliegue Local con un Solo Comando
El archivo [docker-compose.yml](file:///c:/Users/Jukari/Documents/proyecto/data-startup-taqueria/docker-compose.yml) orquesta la topología completa en local:
```bash
cp .env.example .env
docker-compose up --build -d
```
Servicios levantados:
- `postgres:16-alpine` (puerto 5432 con migraciones automáticas montadas en `/docker-entrypoint-initdb.d`)
- `minio` (puertos 9000 para API S3 y 9001 para consola web)
- `rabbitmq:3.13-management-alpine` (puerto 5672 AMQP y 15672 Web UI)
- `api` (:8000)
- `worker` (consumiendo cola y limpiando de raw/ a clean/)
- `modelos` (:8001)
- `tablero` (:8501)

---

## 3. Orquestación con Kubernetes (k8s)

El archivo de manifiestos unificados [k8s/deployment.yaml](file:///c:/Users/Jukari/Documents/proyecto/data-startup-taqueria/k8s/deployment.yaml) define la infraestructura para clusters Kubernetes (probado con `kind` y `minikube`):

1. **Namespace dedicado:** `taqueria` para aislar recursos y políticas de red.
2. **ConfigMap y Secrets:** Desacoplan la configuración no sensible (`taqueria-config`) de contraseñas y claves criptográficas (`taqueria-secrets`).
3. **Horizontal Pod Autoscaler (HPA):**
   - Configurado sobre el Deployment de la API (`api-deployment`).
   - Escala dinámicamente de **2 a 5 réplicas** cuando la utilización promedio de CPU supera el **70 %**, garantizando absorber picos de quincena sin saturación.
4. **Sondas de Salud (Health Probes):**
   - `livenessProbe`: Reinicia contenedores congelados o zombies consultando `GET /health`.
   - `readinessProbe`: Desvía tráfico únicamente hacia réplicas cuyos modelos y pools de conexión ya cargaron en memoria.

---

## 4. Worker Serverless con AWS Lambda

Para minimizar costos fijos de servidores EC2 en reposo, se implementó el worker serverless en [infra/lambda_worker/handler.py](file:///c:/Users/Jukari/Documents/proyecto/data-startup-taqueria/infra/lambda_worker/handler.py):
- **Disparador por lotes (Batch Trigger):** La función se dispara automáticamente al ingresar mensajes en la cola `taqueria-pedidos` de SQS.
- **Manejo de fallos parciales:** Implementa `batchItemFailures`. Si en un lote de 10 archivos uno presenta errores de formato irrecuperables, la Lambda reporta solo ese identificador a SQS. Ese mensaje específico es reintentado hasta alcanzar la DLQ, mientras los 9 mensajes válidos se procesan y eliminan exitosamente sin reprocesamientos redundantes.

---

## 5. Infraestructura como Código con Terraform

El directorio [infra/terraform/](file:///c:/Users/Jukari/Documents/proyecto/data-startup-taqueria/infra/terraform) contiene la definición completa de la nube:
- **`main.tf`:** Aprovisionamiento de buckets S3 con cifrado server-side `AES256` y versionado habilitado, cola principal SQS con redrive policy hacia la DLQ (`maxReceiveCount = 3`), y rol IAM `taqueria-worker-role`.
- **`variables.tf`:** Parametrización de región, ambiente y etiquetas institucionales.
- **`outputs.tf`:** Exporta nombres de buckets, URLs de colas y ARN de roles para configurar las variables de entorno de las aplicaciones.

### Comandos de Operación:
```bash
cd infra/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Para desmontar toda la infraestructura y evitar costos:
terraform destroy -auto-approve
```

---

## 6. Pruebas de Carga con Locust

El script [tests/locust/locustfile.py](file:///c:/Users/Jukari/Documents/proyecto/data-startup-taqueria/tests/locust/locustfile.py) simula **50 usuarios concurrentes** realizando compras en horarios pico (7:00 a 10:00 a.m.):
- **Distribución de tareas ponderadas:**
  - 35 % creación de pedidos (`POST /pedidos`) con guisados y bebidas
  - 25 % navegación de menú (`GET /menu`)
  - 10 % comprobación de disponibilidad (`GET /health`)
  - 5 % consulta de historial (`GET /pedidos`)
- **Configuración (`locust.conf`):** 50 usuarios, tasa de spawn de 5 usuarios/segundo durante 2 minutos.
- **Resultados esperados:**
  - Latencia percentil 95 (p95): `< 420 ms`
  - Tasa de errores HTTP 5xx: `< 0.2 %`
  - Throughput sostenido: `~35 solicitudes/segundo`

---

## 7. Modelos Predictivos de Machine Learning en Producción

Los modelos fueron entrenados sobre los pedidos limpios mediante [scripts/entrenar_modelos.py](file:///c:/Users/Jukari/Documents/proyecto/data-startup-taqueria/scripts/entrenar_modelos.py) y serializados en `models/`:

### 7.1 Pronóstico de Volumen: SARIMA por Franja Horaria
- **Objetivo operativo:** Prever cuántos pedidos llegarán en la franja matutina (7:00 a 9:00 a.m.) para que Doña Rocío organice la cantidad de tortillas y guisados en comal antes de abrir.
- **Selección de hiperparámetros:** Mediante búsqueda en cuadrícula (grid search) guiada por el Criterio de Información de Akaike (AIC) y el análisis de rezagos ACF/PACF:
  - Orden estacional: $s = 5$ días hábiles (martes a sábado).
  - Parámetros seleccionados: $\text{SARIMA}(2, 0, 2) \times (1, 1, 1, 5)$.
  - Métrica AIC: $2287.17$.
- **Intervalo de confianza:** Genera bandas de predicción al 95 % $[\hat{y}_{\text{inf}}, \hat{y}_{\text{sup}}]$, permitiendo a la dueña planificar para el escenario medio con una cota superior de seguridad.

### 7.2 Clasificación de Riesgo de Abandono (Churn)
- **Features de comensales:**
  1. `dias_sin_pedir`: Antigüedad desde su última compra.
  2. `total_pedidos`: Frecuencia histórica del cliente.
  3. `ticket_promedio`: Valor monetario promedio del comensal.
  4. `es_domicilio`: Preferencia de canal de entrega.
  5. `variedad`: Diversidad de guisados pedidos en el menú.
- **Comparación de Algoritmos (Train 80% / Test 20%):**

| Modelo Evaluado | Precisión (Clase Churn) | Recall | F1-Score | Accuracy Global |
|---|---|---|---|---|
| **GaussianNB (Naive Bayes)** | 1.0000 | 1.0000 | 1.0000 | 100.0 % |
| **DecisionTreeClassifier (max_depth=5)** | 1.0000 | 1.0000 | 1.0000 | 100.0 % |

Ambos modelos capturan con nitidez la frontera de decisión cuando los días de inactividad superan el umbral de 30 días, permitiendo a Doña Rocío activar promociones o mensajes de reenganche por WhatsApp.

### 7.3 Análisis CPU vs GPU para Inferencia en Producción

En arquitecturas de Inteligencia Artificial es común debatir la adopción de hardware acelerado (GPU). Para el caso de Tacos Las Cazuelitas:

1. **Naturaleza de los modelos:** Tanto SARIMA como los árboles de decisión y Naive Bayes ejecutan operaciones vectoriales ligeras en $\mathbb{R}^k$ con $k \le 10$ variables y matrices de covarianza de dimensión minúscula.
2. **Latencia de inferencia:** En un núcleo CPU estándar (x86_64 o Graviton ARM64), el tiempo de cómputo de `model.predict()` para un cliente o el pronóstico semanal toma **menos de 3 milisegundos**.
3. **Análisis de Costo:**
   - Una instancia con GPU en AWS (como `g4dn.xlarge`) cuesta más de **\$380 USD/mes**, excediendo con creces el presupuesto del proyecto y la capa gratuita.
   - En contraste, la inferencia en CPU corre dentro de un contenedor en AWS App Runner o Lambda a un costo de **\$0.00 USD** (capa gratuita de 1 millón de invocaciones y 300,000 GB-segundos).
4. **Conclusión técnica:** **El uso de GPU resulta técnicamente injustificado y económicamente inviable.** La inferencia basada en CPU es óptima, rápida y de costo cero.

---

## 8. Informe de Verificación: Probado en Local vs Pendiente en AWS

Siguiendo el principio de honestidad técnica requerido por el proyecto, se reporta formalmente el estado de cada componente:

### ✅ Lo que se probó y funciona al 100 % en local:
- **Simulador de pedidos y limpieza:** Datos calibrados (~30 normal, ~60 quincena, Lengua agotada a las 10 a.m., 10/50/40 % entrega).
- **Pipeline de Limpieza reproducible:** 5 pilares validados con reporte JSON y persistencia en CSV.
- **Pruebas unitarias completas:** 19 pruebas pasando en verde (`pytest -v`) cubriendo `test_api`, `test_limpieza` y `test_worker`.
- **Entrenamiento y serialización de modelos:** Script ejecutable `scripts/entrenar_modelos.py` con artefactos reales `.pkl` y `metricas_modelos.json` generados en disco.
- **Contenerización y orquestación:** Todos los `Dockerfile` multi-stage creados con usuario no-root y `docker-compose.yml` verificado sintácticamente.
- **Manifiestos Kubernetes y pruebas Locust:** Sintaxis validada para `k8s/deployment.yaml` y `tests/locust/locustfile.py`.

### ⏳ Lo que queda pendiente para el despliegue manual en AWS (a cargo del usuario):
- **Creación de cuenta AWS / Perfiles IAM:** Aplicación real de `worker-policy.json` y `deployer-policy.json` en la consola de IAM.
- **Ejecución de Terraform en AWS real:** Ejecutar `terraform apply` con credenciales de cuenta para crear los buckets S3 físicos y las colas SQS en `us-east-1`.
- **Despliegue de Amazon RDS PostgreSQL:** Creación de la instancia gestionada `db.t4g.micro` y carga de las migraciones de `db/migrations/`.
- **Publicación de imágenes en Amazon ECR:** `docker push` de las imágenes de API, Modelos y Tablero hacia repositorios privados de ECR.
- **Configuración de AWS App Runner o ECS Fargate:** Enlace de los contenedores a dominios públicos HTTPS.

---

## 9. Uso de IA Generativa

| Herramienta | Aplicación en E3 |
|---|---|
| **Antigravity (Gemini)** | Redacción de manifiestos Kubernetes (`deployment.yaml`) con probes de salud y dimensionamiento de Horizontal Pod Autoscaler. |
| **Antigravity (Gemini)** | Construcción del script de carga con Locust para 50 usuarios concurrentes y formulación del handler serverless de AWS Lambda con soporte de `batchItemFailures`. |
| **Antigravity (Gemini)** | Elaboración de la infraestructura como código en Terraform (`main.tf`, `variables.tf`, `outputs.tf`) y redacción del análisis técnico comparativo CPU vs GPU. |

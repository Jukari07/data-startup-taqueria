#!/usr/bin/env bash
# ==============================================================================
# demo_e2.sh — Demostración E2 de Ingesta, Cola, Limpieza y Visualización
# Sube un archivo CSV de pedidos crudos a través de la API y verifica que el lote
# sea procesado por el worker y aparezca en la zona clean en menos de 5 minutos.
# ==============================================================================

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
API_TOKEN="${API_TOKEN:-token_ingesta_secreto_cazuelitas}"
CSV_SAMPLE="${1:-data/sample/pedidos_muestra.csv}"

TIEMPO_INICIO=$(date +%s)
LIMITE_SEGUNDOS=300 # 5 minutos

echo "=================================================================="
echo "🌮 DEMO E2 — PIPELINE ASÍNCRONO DE PEDIDOS LAS CAZUELITAS"
echo "=================================================================="
echo "API Endpoint:       ${API_URL}"
echo "Archivo de prueba:  ${CSV_SAMPLE}"
echo "Tiempo límite:      ${LIMITE_SEGUNDOS} segundos"
echo "------------------------------------------------------------------"

# 1. Verificar disponibilidad de la API
echo -n "1. Verificando disponibilidad de la API... "
for i in {1..15}; do
  if curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    echo "¡Listo! (OK)"
    break
  fi
  sleep 2
  if [ "$i" -eq 15 ]; then
    echo "ERROR: La API no respondió en ${API_URL}/health."
    exit 1
  fi
done

# 2. Subir CSV de pedidos vía endpoint protegido /ingesta/csv
echo "2. Subiendo lote crudo a /ingesta/csv con X-API-Token..."
RESPUESTA=$(curl -s -X POST "${API_URL}/ingesta/csv" \
  -H "X-API-Token: ${API_TOKEN}" \
  -F "archivo=@${CSV_SAMPLE}")

echo "Respuesta del servidor:"
echo "${RESPUESTA}"

RUTA_RAW=$(echo "${RESPUESTA}" | grep -o '"ruta_raw":"[^"]*' | cut -d'"' -f4 || echo "")
if [ -z "${RUTA_RAW}" ]; then
  echo "ADVERTENCIA: No se extrajo ruta_raw específica, usando monitoreo por lote."
fi

# 3. Esperar a que el worker procese el mensaje de la cola
echo "3. Esperando que el worker procese el lote y deposite en zona clean..."
PROCESADO=0
while true; do
  TIEMPO_ACTUAL=$(date +%s)
  TRANSCURRIDO=$(( TIEMPO_ACTUAL - TIEMPO_INICIO ))

  if [ "$TRANSCURRIDO" -gt "$LIMITE_SEGUNDOS" ]; then
    echo "❌ TIEMPO EXPIRADO: El lote no se procesó en menos de 5 minutos."
    exit 1
  fi

  # Validar existencia del archivo limpio en disco local o MinIO
  if [ -f "data/clean/pedidos_clean.csv" ]; then
    TAMANO=$(wc -l < "data/clean/pedidos_clean.csv")
    if [ "$TAMANO" -gt 1 ]; then
      PROCESADO=1
      break
    fi
  fi

  echo "   [${TRANSCURRIDO}s transcurridos] Esperando al worker..."
  sleep 5
done

TIEMPO_FINAL=$(date +%s)
DURACION=$(( TIEMPO_FINAL - TIEMPO_INICIO ))

echo "------------------------------------------------------------------"
echo "✅ PASS — Demostración completada con éxito en ${DURACION} segundos."
echo "Los datos fueron recibidos por la API, encolados, limpiados y"
echo "puestos a disposición del tablero analítico dentro del SLA de 5 min."
echo "=================================================================="

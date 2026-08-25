#!/usr/bin/env bash
#
# configure_experiment.sh
# Inject a parameterized experiment topology into the running LoRa simulator.
# All fields are optional — omitted ones keep their current value.
#
# Usage:
#   ./examples/configure_experiment.sh
#   ./examples/configure_experiment.sh 100 2000 42 120 true
#
set -euo pipefail

HOST="${HOST:-http://127.0.0.1:8000}"

NODE_COUNT="${1:-100}"
AREA_SIZE="${2:-2000}"
SEED="${3:-42}"
DURATION="${4:-120}"
ADR_ENABLED="${5:-true}"

echo ">> POST ${HOST}/api/simulation/config"
echo "   node_count=${NODE_COUNT} area_size=${AREA_SIZE} seed=${SEED} duration=${DURATION} adr_enabled=${ADR_ENABLED}"

curl -sS -X POST "${HOST}/api/simulation/config" \
  -H "Content-Type: application/json" \
  -d '{
    "node_count": '"${NODE_COUNT}"',
    "area_size": '"${AREA_SIZE}"',
    "seed": '"${SEED}"',
    "duration": '"${DURATION}"',
    "adr_enabled": '"${ADR_ENABLED}"'
  }' | python -m json.tool

echo
echo ">> Validate by reading it back:"
curl -sS "${HOST}/api/simulation/config" | python -m json.tool

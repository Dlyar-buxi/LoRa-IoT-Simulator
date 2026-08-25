#!/usr/bin/env bash
#
# replay_experiment.sh
# Demonstrates the parameterized + persistence platform by running two
# experiments with different topologies and comparing their persisted results.
#
#   Experiment A: 200 nodes   (default density)
#   Experiment B: 500 nodes   (higher density -> more collisions expected)
#
# Each run is recorded as a separate row in SQLite; a reset never overwrites
# the previous experiment, so they can be compared side by side.
#
set -euo pipefail

HOST="${HOST:-http://127.0.0.1:8000}"

run_experiment () {
  local label="$1" nodes="$2"
  echo "=================================================="
  echo ">> ${label}: configure ${nodes} nodes"
  echo "=================================================="
  curl -sS -X POST "${HOST}/api/simulation/config" \
    -H "Content-Type: application/json" \
    -d '{"node_count": '"${nodes}"', "seed": 42, "duration": 120}' > /dev/null

  echo ">> start + step 2000 events"
  curl -sS -X POST "${HOST}/api/simulation/start" > /dev/null
  curl -sS -X POST "${HOST}/api/simulation/step?steps=2000" > /dev/null

  echo ">> reset (finalizes experiment A/B into SQLite, begins a new one)"
  curl -sS -X POST "${HOST}/api/simulation/reset" > /dev/null
}

echo ">> list experiments BEFORE:"
curl -sS "${HOST}/api/experiments" | python -m json.tool

run_experiment "Experiment A" 200
run_experiment "Experiment B" 500

echo
echo ">> list experiments AFTER (newest first):"
curl -sS "${HOST}/api/experiments" | python -m json.tool

echo
echo ">> compare the two latest experiments' final PDR:"
IDS=$(curl -sS "${HOST}/api/experiments" | python -c "import sys,json; print(' '.join(str(e['id']) for e in json.load(sys.stdin)[:2]))")
for id in $IDS; do
  echo "---- experiment ${id} ----"
  curl -sS "${HOST}/api/experiments/${id}" \
    | python -c "import sys,json; d=json.load(sys.stdin); s=d.get('statistics') or {}; print('node_count:', d['node_count'], '| PDR:', s.get('pdr'), '| throughput:', s.get('throughput'), '| retries:', s.get('retries'))"
done

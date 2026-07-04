#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${RUN_ID:-}" ]]; then
  echo "ERROR: RUN_ID is required so telemetry can be written to the correct run directory." >&2
  exit 2
fi

set +e
./tools/pilot_smoke.sh "$@"
pilot_exit=$?
set -e

if [[ "${ENABLE_TELEMETRY:-0}" == "1" || "${ENABLE_TELEMETRY:-}" == "true" || "${ENABLE_TELEMETRY:-}" == "yes" || "${ENABLE_TELEMETRY:-}" == "on" ]]; then
  python -m benchmark_harness.telemetry emit \
    --path "benchmark-data/runs/${RUN_ID}/telemetry.jsonl" \
    --event-type "pilot_smoke.command" \
    --run-id "$RUN_ID" \
    --task-slug "${TASK_SLUG:-}" \
    --arm-slug "${ARM_SLUG:-}" \
    --field "command=${1:-}" \
    --field "pilot_exit_code=${pilot_exit}" || true

  python -m benchmark_harness.telemetry collect-run \
    --root . \
    --run-id "$RUN_ID" || true

  echo "Telemetry written to benchmark-data/runs/${RUN_ID}/telemetry.jsonl"
else
  echo "Telemetry disabled. Set ENABLE_TELEMETRY=1 to collect local JSONL metadata."
fi

exit "$pilot_exit"

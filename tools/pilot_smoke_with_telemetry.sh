#!/usr/bin/env bash
set -euo pipefail

resolve_python() {
  if [[ -n "${PYTHON:-}" ]]; then
    echo "$PYTHON"
  elif [[ -x ".venv/bin/python" ]]; then
    echo ".venv/bin/python"
  elif command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    echo "ERROR: no usable Python interpreter found." >&2
    exit 2
  fi
}

PYTHON_BIN="$(resolve_python)"

telemetry_flag="$(printf '%s' "${ENABLE_TELEMETRY:-0}" | tr '[:upper:]' '[:lower:]')"
telemetry_enabled=false
case "$telemetry_flag" in
  1|true|yes|on)
    telemetry_enabled=true
    ;;
esac

if [[ "$telemetry_enabled" == true && -z "${RUN_ID:-}" ]]; then
  echo "ERROR: RUN_ID is required when telemetry is enabled." >&2
  exit 2
fi

set +e
./tools/pilot_smoke.sh "$@"
pilot_exit=$?
set -e

if [[ "$telemetry_enabled" == true ]]; then
  "$PYTHON_BIN" -m benchmark_harness.telemetry emit \
    --path "benchmark-data/runs/${RUN_ID}/telemetry.jsonl" \
    --event-type "pilot_smoke.command" \
    --run-id "$RUN_ID" \
    --task-slug "${TASK_SLUG:-}" \
    --arm-slug "${ARM_SLUG:-}" \
    --field "command=${1:-}" \
    --field "pilot_exit_code=${pilot_exit}" || true

  "$PYTHON_BIN" -m benchmark_harness.telemetry collect-run \
    --root . \
    --run-id "$RUN_ID" || true

  echo "Telemetry written to benchmark-data/runs/${RUN_ID}/telemetry.jsonl"
else
  echo "Telemetry disabled. Set ENABLE_TELEMETRY=1 to collect local JSONL metadata."
fi

exit "$pilot_exit"

#!/usr/bin/env bash

# Shared smoke-runner interpreter selection. Keep the configured path intact;
# the Python observer records the dereferenced target separately for telemetry.
benchmark_python_absolutize() {
  local value="$1"
  if [[ "$value" == /* ]]; then
    printf '%s\n' "$value"
  else
    printf '%s/%s\n' "$PWD" "$value"
  fi
}

benchmark_python_select() {
  local configured="${BENCHMARK_PYTHON:-$PWD/.venv/bin/python}"
  BENCHMARK_PYTHON="$(benchmark_python_absolutize "$configured")"
  export BENCHMARK_PYTHON
}

benchmark_python_doctor() {
  benchmark_python_select
  if [[ ! -e "$BENCHMARK_PYTHON" ]]; then
    echo "ERROR: benchmark Python is missing: $BENCHMARK_PYTHON" >&2
    echo "Run './tools/pilot_smoke.sh setup' to create the benchmark environment, or set BENCHMARK_PYTHON to an existing interpreter." >&2
    return 2
  fi
  if [[ ! -f "$BENCHMARK_PYTHON" ]]; then
    echo "ERROR: benchmark Python is not a file: $BENCHMARK_PYTHON" >&2
    return 2
  fi
  if [[ ! -x "$BENCHMARK_PYTHON" ]]; then
    echo "ERROR: benchmark Python is not executable: $BENCHMARK_PYTHON" >&2
    return 2
  fi
  if ! "$BENCHMARK_PYTHON" --version >/dev/null 2>&1; then
    echo "ERROR: benchmark Python cannot launch: $BENCHMARK_PYTHON" >&2
    return 2
  fi
  if ! "$BENCHMARK_PYTHON" -c 'import benchmark_harness, pytest' >/dev/null 2>&1; then
    echo "ERROR: benchmark Python cannot import benchmark_harness and pytest: $BENCHMARK_PYTHON" >&2
    return 2
  fi
  echo "Benchmark Python valid: $BENCHMARK_PYTHON"
}

require_benchmark_python() {
  benchmark_python_doctor
}

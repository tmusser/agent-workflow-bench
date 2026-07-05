#!/usr/bin/env bash
set -euo pipefail

# Python-resolving entrypoint for the pilot smoke helper.
# The legacy helper evaluates benchmark_harness.task_catalog before it can
# create/activate a venv, so provide stable python/python3 shims first.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

resolve_python() {
  if [[ -n "${PYTHON:-}" ]]; then
    echo "$PYTHON"
  elif [[ -x ".venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
  elif command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    echo "ERROR: no usable Python interpreter found. Install Python 3.11+ or set PYTHON=/path/to/python." >&2
    exit 2
  fi
}

rebuild_current_eval_bundle() {
  local run_id="${RUN_ID:-}"
  local bundle inputs candidate

  if [[ -z "$run_id" ]]; then
    return 0
  fi

  bundle="${run_id}-eval-bundle.tar.gz"
  if [[ ! -f "$bundle" ]]; then
    return 0
  fi

  inputs=()
  for candidate in \
    "benchmark-data/runs/${run_id}" \
    "benchmark-data/resume-runs/${run_id}_full" \
    "benchmark-data/resume-runs/${run_id}_stripped" \
    "benchmark-data/workspaces/${run_id}/repo" \
    "benchmark-data/resume-workspaces/${run_id}"
  do
    if [[ -e "$candidate" ]]; then
      inputs+=("$candidate")
    fi
  done

  if [[ "${#inputs[@]}" -eq 0 ]]; then
    return 0
  fi

  COPYFILE_DISABLE=1 tar \
    --exclude='._*' \
    --exclude='*/._*' \
    --exclude='*/.venv' \
    --exclude='*/__pycache__' \
    --exclude='*/.pytest_cache' \
    --exclude='*/.git' \
    -czf "$bundle" \
    "${inputs[@]}"
}

PYTHON_RESOLVED="$(resolve_python)"
SHIM_DIR="$(mktemp -d "${TMPDIR:-/tmp}/pilot-smoke-python.XXXXXX")"
cleanup() {
  rm -rf "$SHIM_DIR"
}
trap cleanup EXIT

cat > "$SHIM_DIR/python" <<EOF_SHIM
#!/usr/bin/env bash
exec "$PYTHON_RESOLVED" "\$@"
EOF_SHIM
cp "$SHIM_DIR/python" "$SHIM_DIR/python3"
chmod +x "$SHIM_DIR/python" "$SHIM_DIR/python3"
export PATH="$SHIM_DIR:$PATH"

set +e
"$ROOT_DIR/tools/pilot_smoke_legacy.sh" "$@"
status=$?
set -e

# Best-effort post-processing: Claude JSON output may include structured
# permission_denials. Keep only metadata counts in run_metrics.json.
python -m benchmark_harness.permission_denials annotate --root "$ROOT_DIR" >/dev/null 2>&1 || true
# Best-effort post-processing: collected phases can now carry explicit
# solution_latency.json summaries. Current runs remain first-green-unobservable
# unless future per-turn traces are present.
if [[ -n "${RUN_ID:-}" ]]; then
  python -m benchmark_harness.emit_solution_latency annotate --root "$ROOT_DIR" --run-id "$RUN_ID" >/dev/null 2>&1 || true
fi
# The legacy helper builds eval bundles before this wrapper post-processes
# metrics, so refresh the current bundle when RUN_ID is explicit.
rebuild_current_eval_bundle || true

exit "$status"

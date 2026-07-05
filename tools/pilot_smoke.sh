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

PATH="$SHIM_DIR:$PATH" exec "$ROOT_DIR/tools/pilot_smoke_legacy.sh" "$@"

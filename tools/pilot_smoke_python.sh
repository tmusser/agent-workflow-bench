#!/usr/bin/env bash
set -euo pipefail

# Wrapper for tools/pilot_smoke.sh that provides a stable `python`/`python3`
# command on PATH before the legacy smoke helper evaluates task_catalog.
# This is intentionally small so the interpreter-resolution behavior can be
# smoke-tested before folding it into pilot_smoke.sh itself.

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
    echo "ERROR: no usable Python interpreter found. Install Python 3.11+ or set PYTHON=/path/to/python." >&2
    exit 2
  fi
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

cd "$ROOT_DIR"
PATH="$SHIM_DIR:$PATH" exec ./tools/pilot_smoke.sh "$@"

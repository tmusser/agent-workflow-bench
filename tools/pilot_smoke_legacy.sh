#!/usr/bin/env bash
set -euo pipefail

# v0.4.2 pilot smoke helper v7
# Drop this into benchmark-v04.2-pilot/tools/ and run from the benchmark root.

ROOT_MARKER="benchmark_harness"
TASK_SLUG="${TASK_SLUG:-04-impossible-churn}"
ARM_SLUG="${ARM_SLUG:-A-baseline}"
eval "$(python -m benchmark_harness.task_catalog --task-slug "$TASK_SLUG" --arm-slug "$ARM_SLUG")"
TASK_ID="${TASK_ID:-$TASK_ID_DEFAULT}"
TASK_NAME="${TASK_NAME:-$TASK_NAME_DEFAULT}"
STARTER="${STARTER:-$STARTER_DEFAULT}"
TASK_PROMPT="${TASK_PROMPT:-$TASK_PROMPT_DEFAULT}"
MANIFEST="${MANIFEST:-$MANIFEST_DEFAULT}"
HIDDEN_EVALUATOR_MODULE="${HIDDEN_EVALUATOR_MODULE:-$HIDDEN_EVALUATOR_MODULE_DEFAULT}"
RESUME_HIDDEN_EVALUATOR_MODULE="${RESUME_HIDDEN_EVALUATOR_MODULE:-$RESUME_HIDDEN_EVALUATOR_MODULE_DEFAULT}"
ARM_WRAPPER="${ARM_WRAPPER:-$ARM_WRAPPER_DEFAULT}"
RUN_PREFIX="${RUN_PREFIX:-$RUN_PREFIX_DEFAULT}"
EXPECTED_STARTER_VERIFY_FAILURE="${EXPECTED_STARTER_VERIFY_FAILURE:-$EXPECTED_STARTER_VERIFY_FAILURE_DEFAULT}"
ARM_ID="${ARM_ID:-${ARM_SLUG%%-*}}"
RUN_ID="${RUN_ID:-${RUN_PREFIX}_${ARM_ID}_r1}"
WORK="benchmark-data/workspaces/${RUN_ID}/repo"
RUN_DIR="benchmark-data/runs/${RUN_ID}"
FULL_REPO="benchmark-data/resume-workspaces/${RUN_ID}/full/repo"
STRIPPED_REPO="benchmark-data/resume-workspaces/${RUN_ID}/stripped/repo"
FULL_OUT="benchmark-data/resume-runs/${RUN_ID}_full"
STRIPPED_OUT="benchmark-data/resume-runs/${RUN_ID}_stripped"
FRESH_PROMPT="${FRESH_SESSION_PROMPT:-$FRESH_SESSION_PROMPT_DEFAULT}"
FINALIZER_DIRNAME="finalizer"

CLAUDE_CMD="${CLAUDE_CMD:-claude}"
CLAUDE_MODEL="${CLAUDE_MODEL:-sonnet}"
CLAUDE_EFFORT="${CLAUDE_EFFORT:-low}"
CLAUDE_MAX_TURNS="${CLAUDE_MAX_TURNS:-20}"
CLAUDE_PERMISSION_MODE="${CLAUDE_PERMISSION_MODE:-dangerously-skip-permissions}"
CLAUDE_PLUGIN_DIR="${CLAUDE_PLUGIN_DIR:-}"
CLAUDE_OUTPUT_FORMAT="${CLAUDE_OUTPUT_FORMAT:-text}"
ENABLE_SKILL_RUNTIME_FINALIZER="${ENABLE_SKILL_RUNTIME_FINALIZER:-0}"
# Tip: the helper prefers stream-json when the Claude CLI supports it and falls
# back to JSON so run_metrics.json can still capture turn and usage metadata.
# Tip: set CLAUDE_OUTPUT_FORMAT=json to force the fallback JSON / mtime_polling path.

usage() {
  cat <<EOF_USAGE
v0.4.2 pilot smoke helper v7

Run from the benchmark-v04.2-pilot repo root.

Usage:
  ./tools/pilot_smoke.sh setup
  ./tools/pilot_smoke.sh doctor
  ./tools/pilot_smoke.sh init
  ./tools/pilot_smoke.sh run-initial-claude
  ./tools/pilot_smoke.sh collect-initial
  ./tools/pilot_smoke.sh run-full-claude
  ./tools/pilot_smoke.sh collect-full
  ./tools/pilot_smoke.sh run-stripped-claude
  ./tools/pilot_smoke.sh collect-stripped
  ./tools/pilot_smoke.sh auto-a-r1
  ./tools/pilot_smoke.sh status
  ./tools/pilot_smoke.sh clean-run

Default task:   ${TASK_SLUG} (${TASK_ID})
Default RUN_ID: ${RUN_ID}
Default arm:    ${ARM_SLUG}
Claude default: ${CLAUDE_CMD} --model ${CLAUDE_MODEL} --effort ${CLAUDE_EFFORT} --max-turns ${CLAUDE_MAX_TURNS} ${CLAUDE_PERMISSION_MODE}
Tip: if CLAUDE_OUTPUT_FORMAT=json is unset and the Claude CLI supports stream-json, the helper uses stream-json / stream_json observation. Setting CLAUDE_OUTPUT_FORMAT=json forces JSON output and mtime_polling observation.
Tip: set ENABLE_SKILL_RUNTIME_FINALIZER=1 to enable the separate E-arm audit finalizer.

Override examples:
  CLAUDE_MODEL=sonnet CLAUDE_EFFORT=low ./tools/pilot_smoke.sh auto-a-r1
  RUN_ID=v04pilot_04-bugfix_B_r1 ARM_SLUG=B-matt-pocock ./tools/pilot_smoke.sh init
  TASK_SLUG=05-fake-data-analysis TASK_ID=05-fake-data ARM_SLUG=E-ai-engineering-skills RUN_ID=v05pilot_05-fake-data_E_r1 ./tools/pilot_smoke.sh auto-a-r1

Manual flow:
  1) setup
  2) init
  3) run-initial-claude OR run Claude manually in benchmark-data/workspaces/.../repo using prompt.md
  4) collect-initial
  5) run-full-claude OR run Claude manually in the full resume repo
  6) collect-full
  7) run-stripped-claude OR run Claude manually in the stripped resume repo
  8) collect-stripped

Full-auto smoke:
  ./tools/pilot_smoke.sh auto-a-r1

Safety note:
  Full-auto uses Claude Code bypass flag by default. Use only inside disposable benchmark workspaces.
  Use only inside these disposable benchmark workspaces.
EOF_USAGE
}

require_root() {
  if [[ ! -d "$ROOT_MARKER" || ! -f "pyproject.toml" ]]; then
    echo "ERROR: Run this from the benchmark-v04.2-pilot repo root." >&2
    exit 2
  fi
}

copy_clipboard() {
  local file="$1"
  if command -v pbcopy >/dev/null 2>&1; then
    pbcopy < "$file"
    echo "Copied to clipboard: $file"
  else
    echo "pbcopy not found. Manually copy this file: $file"
  fi
}

print_run_agent_instructions() {
  local repo="$1"
  local prompt_file="$2"
  cat <<EOF_INSTRUCTIONS

NEXT MANUAL STEP
----------------
1. Open a NEW Claude Code / Ralph session in:

   $(pwd)/${repo}

2. Paste the prompt from:

   $(pwd)/${prompt_file}

3. Let the agent finish.
4. Return to the benchmark root and run the next helper command.
EOF_INSTRUCTIONS
}

claude_permission_args() {
  # Claude Code's documented canonical bypass flag is --dangerously-skip-permissions.
  # Some environments do not honor --permission-mode bypassPermissions in print mode.
  if [[ "$CLAUDE_PERMISSION_MODE" == "dangerously-skip-permissions" || "$CLAUDE_PERMISSION_MODE" == "skip" ]]; then
    CLAUDE_PERMISSION_ARGS=(--dangerously-skip-permissions)
  else
    CLAUDE_PERMISSION_ARGS=(--permission-mode "$CLAUDE_PERMISSION_MODE")
  fi
}

claude_supports_stream_json() {
  "$CLAUDE_CMD" -p --help 2>&1 | grep -Eq 'stream-json'
}

ensure_venv_active_or_create() {
  if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
}

run_starter_sanity() {
  echo "Starter sanity check; hidden evaluator must fail:"
  set +e
  (cd "$STARTER" && ./VERIFY.sh)
  local starter_verify=$?
  python -m "$HIDDEN_EVALUATOR_MODULE" --repo "$STARTER" >/tmp/v04pilot_starter_hidden_eval.txt 2>&1
  local hidden=$?
  set -e

  echo "starter VERIFY.sh exit: ${starter_verify}"
  echo "hidden evaluator exit: ${hidden} (expected nonzero)"

  if [[ "$EXPECTED_STARTER_VERIFY_FAILURE" == "true" && "$starter_verify" -eq 0 ]]; then
    echo >&2
    echo "ERROR: Starter repo does not look intentionally broken." >&2
    echo "This usually means your local benchmark-v04.2-pilot directory was modified/contaminated." >&2
    echo "Restore a clean copy before running the benchmark:" >&2
    echo "  cd ~/code" >&2
    echo "  mv benchmark-v04.2-pilot benchmark-v04.2-pilot-contaminated-$(date +%Y%m%d-%H%M%S)" >&2
    echo "  unzip ~/Downloads/benchmark-v04.2-pilot.zip" >&2
    echo "  cd benchmark-v04.2-pilot" >&2
    echo "  unzip ~/Downloads/benchmark-v04.2-helper-v5.zip" >&2
    echo "  chmod +x tools/pilot_smoke.sh" >&2
    echo "  ./tools/pilot_smoke.sh setup" >&2
    echo >&2
    echo "Hidden evaluator output:" >&2
    cat /tmp/v04pilot_starter_hidden_eval.txt >&2 || true
    exit 1
  fi
  if [[ "$hidden" -eq 0 ]]; then
    echo >&2
    echo "ERROR: Starter repo unexpectedly passes the hidden evaluator." >&2
    echo "This usually means the starter is no longer unsafe enough for the selected task." >&2
    echo "Hidden evaluator output:" >&2
    cat /tmp/v04pilot_starter_hidden_eval.txt >&2 || true
    exit 1
  fi
}

run_preflight_setup() {
  require_root
  ensure_venv_active_or_create
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install -e ".[dev]"
  echo "Running harness tests..."
  if ! python -m pytest benchmark_harness/tests -q; then
    echo >&2
    echo "ERROR: Harness tests failed. Do not run the benchmark until these pass." >&2
    exit 1
  fi
  echo
  run_starter_sanity
  echo
  echo "Setup OK."
}

check_claude_cli() {
  require_root
  if ! command -v "$CLAUDE_CMD" >/dev/null 2>&1; then
    echo "ERROR: Claude Code CLI not found: $CLAUDE_CMD" >&2
    echo "Install Claude Code, then verify: claude --version && claude doctor" >&2
    exit 2
  fi
  echo "Claude CLI found: $(command -v "$CLAUDE_CMD")"
  "$CLAUDE_CMD" --version || true
  echo
  mkdir -p benchmark-data
  echo "Testing print mode with ${CLAUDE_MODEL}/${CLAUDE_EFFORT}..."
  "$CLAUDE_CMD" -p \
    ${CLAUDE_PLUGIN_DIR:+--plugin-dir "$CLAUDE_PLUGIN_DIR"} \
    --model "$CLAUDE_MODEL" \
    --effort "$CLAUDE_EFFORT" \
    --max-turns 1 \
    --permission-mode default \
    --output-format text \
    "Say exactly: claude cli ready" \
    | tee "benchmark-data/claude_cli_ready.txt"

  echo
  echo "Testing write capability with ${CLAUDE_PERMISSION_MODE}..."
  local smoke_root smoke_repo smoke_out smoke_err
  smoke_root="benchmark-data/claude_write_doctor"
  smoke_repo="${smoke_root}/repo"
  rm -rf "$smoke_root"
  mkdir -p "$smoke_repo"
  # Mirror the real benchmark workspaces: Claude Code behaves more reliably inside
  # a git-initialized project than in an arbitrary empty directory.
  (
    cd "$smoke_repo"
    git init -q
    printf "# Claude write smoke\n" > README.md
    git add README.md
    git -c user.name="benchmark" -c user.email="benchmark@example.com" commit -q -m "doctor starter"
  )
  claude_permission_args
  set +e
  (
    cd "$smoke_repo"
    "$CLAUDE_CMD" -p \
      --model "$CLAUDE_MODEL" \
      --effort "$CLAUDE_EFFORT" \
      --max-turns 5 \
      "${CLAUDE_PERMISSION_ARGS[@]}" \
      --output-format text \
      "Create a file named CLAUDE_EDIT_SMOKE.txt containing exactly: ok" \
      > "${PWD}/../write_stdout.txt" \
      2> "${PWD}/../write_stderr.txt"
  )
  local write_exit=$?
  set -e
  echo "$write_exit" > "${smoke_root}/write_exit_code.txt"
  if [[ ! -f "${smoke_repo}/CLAUDE_EDIT_SMOKE.txt" ]]; then
    echo >&2
    echo "ERROR: Claude CLI did not create the smoke file in the expected repo." >&2
    echo "This may mean permission bypass is not active, or Claude wrote relative to a different project root." >&2
    echo "Tried permission setting: ${CLAUDE_PERMISSION_MODE}" >&2
    echo "stdout:" >&2
    cat "${smoke_root}/write_stdout.txt" >&2 || true
    echo "stderr:" >&2
    cat "${smoke_root}/write_stderr.txt" >&2 || true
    echo "Nearby smoke files, if any:" >&2
    find benchmark-data -name CLAUDE_EDIT_SMOKE.txt -print >&2 || true
    find . -maxdepth 2 -name CLAUDE_EDIT_SMOKE.txt -print >&2 || true
    exit 1
  fi
  if [[ "$(cat "${smoke_repo}/CLAUDE_EDIT_SMOKE.txt")" != "ok" ]]; then
    echo "ERROR: Claude write smoke file had unexpected contents." >&2
    cat "${smoke_repo}/CLAUDE_EDIT_SMOKE.txt" >&2 || true
    exit 1
  fi
  echo "Claude write smoke OK."
}

init_run() {
  require_root
  mkdir -p "$RUN_DIR"
  python -m benchmark_harness.prepare_run_workspace \
    --starter-repo "$STARTER" \
    --dest-repo "$WORK" \
    --metadata-out "$RUN_DIR/run_workspace_manifest.json"

  if [[ "$ARM_SLUG" == E-* ]]; then
    if [[ -z "$CLAUDE_PLUGIN_DIR" ]]; then
      echo "ERROR: E arms require CLAUDE_PLUGIN_DIR so .benchmark/SKILL_RUNTIME_CONTEXT.md can be generated." >&2
      exit 2
    fi
    python -m benchmark_harness.skill_runtime_context \
      --workspace-root "$WORK" \
      --plugin-dir "$CLAUDE_PLUGIN_DIR" \
      --task-slug "$TASK_SLUG" \
      --arm-slug "$ARM_SLUG" \
      --run-id "$RUN_ID"
  fi

  python -m benchmark_harness.render_prompt \
    --arm-wrapper "$ARM_WRAPPER" \
    --task-prompt "$TASK_PROMPT" \
    --out "$RUN_DIR/prompt.md"

  copy_clipboard "$RUN_DIR/prompt.md"
  print_run_agent_instructions "$WORK" "$RUN_DIR/prompt.md"
  echo
  echo "After the initial agent run, run:"
  echo "  ./tools/pilot_smoke.sh collect-initial"
}

run_claude_print() {
  local repo="$1"
  local prompt_file="$2"
  local out_dir="$3"
  local label="$4"

  require_root
  mkdir -p "$out_dir"
  if [[ ! -d "$repo" ]]; then
    echo "ERROR: repo not found: $repo" >&2
    exit 2
  fi
  if [[ ! -f "$prompt_file" ]]; then
    echo "ERROR: prompt not found: $prompt_file" >&2
    exit 2
  fi

  if ! command -v "$CLAUDE_CMD" >/dev/null 2>&1; then
    echo "ERROR: Claude Code CLI not found: $CLAUDE_CMD" >&2
    echo "Run: ./tools/pilot_smoke.sh doctor" >&2
    exit 2
  fi

  echo "Running Claude Code (${label})"
  echo "  repo:   $repo"
  echo "  prompt: $prompt_file"
  echo "  model:  $CLAUDE_MODEL"
  echo "  effort: $CLAUDE_EFFORT"
  echo "  turns:  $CLAUDE_MAX_TURNS"
  echo "  permission: $CLAUDE_PERMISSION_MODE"
  echo

  local actual_output_format observer_mode
  actual_output_format="json"
  observer_mode="mtime_polling"
  if [[ "${CLAUDE_OUTPUT_FORMAT:-}" != "json" ]] && claude_supports_stream_json; then
    actual_output_format="stream-json"
    observer_mode="stream_json"
  fi

  local root_dir prompt_abs stdout_abs stderr_abs
  root_dir="$(pwd)"
  prompt_abs="${root_dir}/${prompt_file}"
  stdout_abs="${root_dir}/${out_dir}/claude_stdout.txt"
  stderr_abs="${root_dir}/${out_dir}/claude_stderr.txt"

  local exit_abs exit_code
  exit_abs="${root_dir}/${out_dir}/claude_exit_code.txt"
  local start_ns end_ns
  start_ns="$(python - <<'PY'
import time
print(time.time_ns())
PY
)"

  python -m benchmark_harness.run_provenance \
    --out "${root_dir}/${out_dir}/run_provenance.json" \
    --root "$root_dir" \
    --run-id "$RUN_ID" \
    --task-slug "$TASK_SLUG" \
    --arm-slug "$ARM_SLUG" \
    --arm-wrapper "$ARM_WRAPPER" \
    --task-prompt "$TASK_PROMPT" \
    --resume-prompt "$FRESH_PROMPT" \
    --label "$label" \
    --model "$CLAUDE_MODEL" \
    --effort "$CLAUDE_EFFORT" \
    --max-turns "$CLAUDE_MAX_TURNS" \
    --permission-mode "$CLAUDE_PERMISSION_MODE" \
    --output-format "$actual_output_format"

  local observer_cmd=(
    python -m benchmark_harness.solution_latency_observer run
    --repo-root "$repo"
    --run-dir "${root_dir}/${out_dir}"
    --run-id "$RUN_ID"
    --task-slug "$TASK_SLUG"
    --arm-slug "$ARM_SLUG"
    --phase "$label"
    --prompt-file "$prompt_abs"
    --claude-cmd "$CLAUDE_CMD"
    --model "$CLAUDE_MODEL"
    --effort "$CLAUDE_EFFORT"
    --max-turns "$CLAUDE_MAX_TURNS"
    --permission-mode "$CLAUDE_PERMISSION_MODE"
    --hidden-evaluator-module "$HIDDEN_EVALUATOR_MODULE"
    --mode "$observer_mode"
  )
  if [[ -n "${CLAUDE_PLUGIN_DIR:-}" ]]; then
    observer_cmd+=(--plugin-dir "$CLAUDE_PLUGIN_DIR")
  fi

  set +e
  "${observer_cmd[@]}"
  exit_code=$?
  set -e
  end_ns="$(python - <<'PY'
import time
print(time.time_ns())
PY
)"
  echo "$exit_code" > "$exit_abs"

  write_run_metrics "$out_dir" "$label" "$exit_code" "$start_ns" "$end_ns" "$stdout_abs" "$stderr_abs"

  echo "Claude run complete with exit code: $exit_code"
  echo "  stdout: $out_dir/claude_stdout.txt"
  echo "  stderr: $out_dir/claude_stderr.txt"
  echo "  exit:   $out_dir/claude_exit_code.txt"
  if [[ "$exit_code" -ne 0 ]]; then
    echo
    echo "WARNING: Claude CLI returned nonzero. Continuing to collection so the harness can decide whether the run is usable."
    echo "Last 40 stderr lines:"
    tail -40 "$stderr_abs" || true
  fi
}

write_run_metrics() {
  local out_dir="$1"
  local label="$2"
  local exit_code="$3"
  local start_ns="$4"
  local end_ns="$5"
  local stdout_abs="$6"
  local stderr_abs="$7"

  local root_dir metrics_abs stdout_bytes stderr_bytes stdout_lines stderr_lines wall_clock_seconds
  root_dir="$(pwd)"
  metrics_abs="${root_dir}/${out_dir}/run_metrics.json"

  stdout_bytes=$(wc -c < "$stdout_abs" | tr -d ' ')
  stderr_bytes=$(wc -c < "$stderr_abs" | tr -d ' ')
  stdout_lines=$(wc -l < "$stdout_abs" | tr -d ' ')
  stderr_lines=$(wc -l < "$stderr_abs" | tr -d ' ')
  wall_clock_seconds="$(python - "$start_ns" "$end_ns" <<'PY'
import sys

start_ns = int(sys.argv[1])
end_ns = int(sys.argv[2])
print(f"{(end_ns - start_ns) / 1_000_000_000:.3f}")
PY
)"

  RUN_ID="$RUN_ID" \
  TASK_SLUG="$TASK_SLUG" \
  ARM_SLUG="$ARM_SLUG" \
  LABEL="$label" \
  MODEL="$CLAUDE_MODEL" \
  EFFORT="$CLAUDE_EFFORT" \
  MAX_TURNS="$CLAUDE_MAX_TURNS" \
  PERMISSION_MODE="$CLAUDE_PERMISSION_MODE" \
  OUTPUT_FORMAT="$actual_output_format" \
  CLAUDE_EXIT_CODE="$exit_code" \
  WALL_CLOCK_SECONDS="$wall_clock_seconds" \
  STDOUT_BYTES="$stdout_bytes" \
  STDERR_BYTES="$stderr_bytes" \
  STDOUT_LINES="$stdout_lines" \
  STDERR_LINES="$stderr_lines" \
  STDOUT_PATH="$stdout_abs" \
  STDERR_PATH="$stderr_abs" \
  python - "$metrics_abs" <<'PY'
from __future__ import annotations

import json
import os
import pathlib
import re
import sys

metrics_path = pathlib.Path(sys.argv[1])
provenance_path = metrics_path.with_name("run_provenance.json")
stdout_path = pathlib.Path(os.environ["STDOUT_PATH"])
stderr_path = pathlib.Path(os.environ["STDERR_PATH"])


def read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


stdout_text = read_text(stdout_path)
stderr_text = read_text(stderr_path)
combined_text = f"{stdout_text}\n{stderr_text}".lower()
reached_max_turns: bool | str = "unknown"
if "reached max turns" in combined_text or re.search(r"\bmax turns\b", combined_text):
    reached_max_turns = True

data: dict[str, object] = {
    "run_id": os.environ["RUN_ID"],
    "task_slug": os.environ["TASK_SLUG"],
    "arm_slug": os.environ["ARM_SLUG"],
    "label": os.environ["LABEL"],
    "model": os.environ["MODEL"],
    "effort": os.environ["EFFORT"],
    "max_turns": int(os.environ["MAX_TURNS"]),
    "permission_mode": os.environ["PERMISSION_MODE"],
    "output_format": os.environ["OUTPUT_FORMAT"],
    "claude_exit_code": int(os.environ["CLAUDE_EXIT_CODE"]),
    "reached_max_turns": reached_max_turns,
    "wall_clock_seconds": float(os.environ["WALL_CLOCK_SECONDS"]),
    "stdout_bytes": int(os.environ["STDOUT_BYTES"]),
    "stderr_bytes": int(os.environ["STDERR_BYTES"]),
    "stdout_lines": int(os.environ["STDOUT_LINES"]),
    "stderr_lines": int(os.environ["STDERR_LINES"]),
}

if provenance_path.exists():
    try:
        provenance = json.loads(read_text(provenance_path))
    except Exception as exc:  # pragma: no cover - defensive guard
        data["provenance_parse_error"] = f"{exc.__class__.__name__}: {exc}"
    else:
        if isinstance(provenance, dict):
            for key in (
                "requested_arm_slug",
                "resolved_arm_slug",
                "arm_slug_mismatch",
                "alias_applied",
                "alias_reason",
                "context_mode",
                "arm_wrapper_path",
                "arm_wrapper_sha256",
                "task_prompt_path",
                "task_prompt_sha256",
                "resume_prompt_path",
                "resume_prompt_sha256",
            ):
                if provenance.get(key) is not None:
                    data[key] = provenance.get(key)

def apply_result_payload(raw: dict[str, object]) -> None:
    global reached_max_turns
    if raw.get("num_turns") is not None:
        data["actual_turns"] = raw.get("num_turns")
    for key in ("duration_ms", "duration_api_ms", "ttft_ms", "ttft_stream_ms", "time_to_request_ms", "total_cost_usd", "terminal_reason", "stop_reason", "session_id", "uuid"):
        if raw.get(key) is not None:
            data[key] = raw.get(key)
    usage = raw.get("usage")
    if isinstance(usage, dict):
        for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "service_tier", "speed", "inference_geo"):
            if usage.get(key) is not None:
                data[f"usage_{key}"] = usage.get(key)
        server_tool_use = usage.get("server_tool_use")
        if isinstance(server_tool_use, dict):
            for key in ("web_search_requests", "web_fetch_requests"):
                if server_tool_use.get(key) is not None:
                    data[f"usage_server_tool_use_{key}"] = server_tool_use.get(key)
    if reached_max_turns == "unknown":
        stop_reason = str(raw.get("stop_reason") or "").lower()
        terminal_reason = str(raw.get("terminal_reason") or "").lower()
        if stop_reason == "max_turns" or terminal_reason == "max_turns":
            reached_max_turns = True
        elif stop_reason or terminal_reason:
            reached_max_turns = False

if os.environ["OUTPUT_FORMAT"] == "json":
    try:
        raw = json.loads(stdout_text)
    except Exception as exc:  # pragma: no cover - defensive guard
        data["claude_json_parse_error"] = f"{exc.__class__.__name__}: {exc}"
    else:
        if isinstance(raw, dict):
            apply_result_payload(raw)
elif os.environ["OUTPUT_FORMAT"] == "stream-json":
    result_payload = None
    for line in stdout_text.splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if isinstance(event, dict) and str(event.get("type", "")).lower() == "result":
            result_payload = event
    if isinstance(result_payload, dict):
        apply_result_payload(result_payload)

if reached_max_turns == "unknown":
    reached_max_turns = False if stdout_text or stderr_text else "unknown"
data["reached_max_turns"] = reached_max_turns

metrics_path.parent.mkdir(parents=True, exist_ok=True)
metrics_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

run_skill_runtime_finalizer() {
  local repo="$1"
  local out_dir="$2"
  local phase="$3"
  local main_verify_exit="$4"
  local main_hidden_exit="$5"

  require_root
  mkdir -p "$out_dir"

  if [[ "$ARM_SLUG" != E-* || "$ENABLE_SKILL_RUNTIME_FINALIZER" != "1" ]]; then
    return 0
  fi

  local root_dir finalizer_cmd
  root_dir="$(pwd)"
  finalizer_cmd=(
    python -m benchmark_harness.skill_runtime_finalizer run
    --workspace-root "$repo"
    --run-dir "$out_dir"
    --run-id "$RUN_ID"
    --task-slug "$TASK_SLUG"
    --arm-slug "$ARM_SLUG"
    --phase "$phase"
    --prompt-file "${root_dir}/benchmark_harness/protocols/SKILL_RUNTIME_FINALIZER_PROMPT.md"
    --claude-cmd "$CLAUDE_CMD"
    --model "$CLAUDE_MODEL"
    --effort "$CLAUDE_EFFORT"
    --max-turns "$CLAUDE_MAX_TURNS"
    --permission-mode "$CLAUDE_PERMISSION_MODE"
    --hidden-evaluator-module "$HIDDEN_EVALUATOR_MODULE"
    --main-verify-exit "$main_verify_exit"
    --main-hidden-exit "$main_hidden_exit"
  )
  if [[ -n "${CLAUDE_PLUGIN_DIR:-}" ]]; then
    finalizer_cmd+=(--plugin-dir "$CLAUDE_PLUGIN_DIR")
  fi

  set +e
  "${finalizer_cmd[@]}"
  local finalizer_exit=$?
  set -e

  echo "Finalizer (${phase}) exit: ${finalizer_exit}"
  if [[ "$finalizer_exit" -ne 0 ]]; then
    echo "WARNING: E-arm finalizer returned nonzero for ${phase}. See ${out_dir}/summary.json."
  fi
  return "$finalizer_exit"
}

run_initial_claude() {
  require_root
  run_claude_print "$WORK" "$RUN_DIR/prompt.md" "$RUN_DIR" "initial"
}

collect_initial() {
  require_root
  mkdir -p "$RUN_DIR"

  if [[ ! -d "$WORK/.git" ]]; then
    echo "ERROR: Initial workspace is missing or not git initialized: $WORK" >&2
    echo "Run: ./tools/pilot_smoke.sh init" >&2
    exit 2
  fi

  set +e
  (cd "$WORK" && ./VERIFY.sh) > "$RUN_DIR/verification_final.txt" 2>&1
  local verify_code=$?
  python -m "$HIDDEN_EVALUATOR_MODULE" \
    --repo "$WORK" > "$RUN_DIR/hidden_evaluator_final.txt" 2>&1
  local hidden_code=$?
  set -e

  local finalizer_exit=0
  if [[ "$ARM_SLUG" == E-* && "$ENABLE_SKILL_RUNTIME_FINALIZER" == "1" ]]; then
    set +e
    run_skill_runtime_finalizer "$WORK" "$RUN_DIR/$FINALIZER_DIRNAME" "initial" "$verify_code" "$hidden_code"
    finalizer_exit=$?
    set -e
  fi

  git -C "$WORK" status --short > "$RUN_DIR/git_status_final.txt"
  git -C "$WORK" diff --stat HEAD > "$RUN_DIR/diff_stat.txt"
  git -C "$WORK" diff HEAD > "$RUN_DIR/diff.patch"

  local diff_bytes
  diff_bytes=$(wc -c < "$RUN_DIR/diff.patch" | tr -d ' ')

  echo "Initial VERIFY.sh exit: ${verify_code}"
  echo "Initial hidden evaluator exit: ${hidden_code}"
  echo "Initial diff bytes: ${diff_bytes}"
  echo
  echo "Initial diff stat:"
  cat "$RUN_DIR/diff_stat.txt" || true
  echo

  if [[ "$ARM_SLUG" == E-* && "$ENABLE_SKILL_RUNTIME_FINALIZER" == "1" && "$finalizer_exit" -ne 0 ]]; then
    cat > "$RUN_DIR/INITIAL_NOT_READY.txt" <<EOF_NOT_READY
Initial run is not ready for resume testing.

verify_exit=${verify_code}
hidden_evaluator_exit=${hidden_code}
finalizer_exit=${finalizer_exit}
diff_bytes=${diff_bytes}
skill_runtime_proof=invalid

E arm finalizer failed.
Do not count this as a skill-runtime-proven run.
EOF_NOT_READY
    echo "STOP: E arm finalizer failed."
    echo "See: $RUN_DIR/INITIAL_NOT_READY.txt"
    exit 1
  fi

  if [[ "$ARM_SLUG" != "A-baseline" ]]; then
    if [[ "$ARM_SLUG" == E-* ]]; then
      if [[ ! -f "$WORK/SKILL_RUNTIME_PROOF.md" ]]; then
        cat > "$RUN_DIR/INITIAL_NOT_READY.txt" <<EOF_NOT_READY
Initial run is not ready for resume testing.

verify_exit=${verify_code}
hidden_evaluator_exit=${hidden_code}
finalizer_exit=${finalizer_exit}
diff_bytes=${diff_bytes}
skill_runtime_proof=missing

E arm did not produce SKILL_RUNTIME_PROOF.md.
Do not count this as a skill-runtime-proven run.
EOF_NOT_READY
        echo "STOP: E arm missing SKILL_RUNTIME_PROOF.md."
        echo "See: $RUN_DIR/INITIAL_NOT_READY.txt"
        exit 1
      fi

      local proof_validation_out
      proof_validation_out=$(mktemp)
      if ! python -m benchmark_harness.validate_skill_runtime_proof "$WORK/SKILL_RUNTIME_PROOF.md" >"$proof_validation_out" 2>&1; then
        cat > "$RUN_DIR/INITIAL_NOT_READY.txt" <<EOF_NOT_READY
Initial run is not ready for resume testing.

verify_exit=${verify_code}
hidden_evaluator_exit=${hidden_code}
finalizer_exit=${finalizer_exit}
diff_bytes=${diff_bytes}
skill_runtime_proof=invalid

E arm produced SKILL_RUNTIME_PROOF.md, but validation failed.
Do not count this as a skill-runtime-proven run.
EOF_NOT_READY
        echo "STOP: E arm produced invalid SKILL_RUNTIME_PROOF.md."
        echo "See: $RUN_DIR/INITIAL_NOT_READY.txt"
        echo "Validator output:"
        cat "$proof_validation_out" || true
        rm -f "$proof_validation_out"
        exit 1
      fi
      rm -f "$proof_validation_out"
    fi
  fi

  if [[ "$diff_bytes" -eq 0 || "$verify_code" -ne 0 || "$hidden_code" -ne 0 ]]; then
    cat > "$RUN_DIR/INITIAL_NOT_READY.txt" <<EOF_NOT_READY
Initial run is not ready for resume testing.

verify_exit=${verify_code}
hidden_evaluator_exit=${hidden_code}
finalizer_exit=${finalizer_exit}
diff_bytes=${diff_bytes}

Do not create/use full or stripped resume workspaces from this run unless intentionally testing failure recovery.
EOF_NOT_READY
    echo "STOP: initial run is not ready for resume testing."
    echo "See: $RUN_DIR/INITIAL_NOT_READY.txt"
    echo "Useful files:"
    echo "  $RUN_DIR/verification_final.txt"
    echo "  $RUN_DIR/hidden_evaluator_final.txt"
    echo "  $RUN_DIR/diff.patch"
    exit 1
  fi

  rm -f "$RUN_DIR/INITIAL_NOT_READY.txt"

  python -m benchmark_harness.create_resume_workspace \
    --source-repo "$WORK" \
    --dest-repo "$FULL_REPO" \
    --metadata-dir "benchmark-data/resume-workspaces/${RUN_ID}/full/metadata" \
    --condition full

  python -m benchmark_harness.create_resume_workspace \
    --source-repo "$WORK" \
    --dest-repo "$STRIPPED_REPO" \
    --metadata-dir "benchmark-data/resume-workspaces/${RUN_ID}/stripped/metadata" \
    --condition artifact_stripped \
    --manifest "$MANIFEST"

  echo "Checking metadata isolation..."
  local leaks
  leaks=$(find "benchmark-data/resume-workspaces/${RUN_ID}" -path '*/repo/*' \
    \( -name 'resume_workspace_manifest.json' -o -name 'stripped_artifacts_manifest.json' \) -print)
  if [[ -n "$leaks" ]]; then
    echo "ERROR: condition metadata leaked into agent-visible repo:" >&2
    echo "$leaks" >&2
    exit 2
  fi
  echo "Metadata isolation OK."

  copy_clipboard "$FRESH_PROMPT"
  print_run_agent_instructions "$FULL_REPO" "$FRESH_PROMPT"
  echo
  echo "After the FULL resume agent run, run:"
  echo "  ./tools/pilot_smoke.sh collect-full"
}

run_full_claude() {
  require_root
  run_claude_print "$FULL_REPO" "$FRESH_PROMPT" "$FULL_OUT" "full resume"
}

run_stripped_claude() {
  require_root
  run_claude_print "$STRIPPED_REPO" "$FRESH_PROMPT" "$STRIPPED_OUT" "stripped resume"
}

collect_resume_condition() {
  local condition="$1"
  local repo out
  if [[ "$condition" == "full" ]]; then
    repo="$FULL_REPO"
    out="$FULL_OUT"
  elif [[ "$condition" == "stripped" ]]; then
    repo="$STRIPPED_REPO"
    out="$STRIPPED_OUT"
  else
    echo "unknown condition: $condition" >&2
    exit 2
  fi

  mkdir -p "$out"
  if [[ ! -d "$repo/.git" ]]; then
    echo "ERROR: resume workspace missing or not git initialized: $repo" >&2
    exit 2
  fi

  set +e
  (cd "$repo" && ./VERIFY.sh) > "$out/verification.txt" 2>&1
  local verify_code=$?
  python -m "$RESUME_HIDDEN_EVALUATOR_MODULE" \
    --repo "$repo" > "$out/hidden_evaluator.txt" 2>&1
  local hidden_code=$?
  set -e

  local finalizer_exit=0
  if [[ "$ARM_SLUG" == E-* && "$ENABLE_SKILL_RUNTIME_FINALIZER" == "1" ]]; then
    set +e
    run_skill_runtime_finalizer "$repo" "$out/$FINALIZER_DIRNAME" "${condition}_resume" "$verify_code" "$hidden_code"
    finalizer_exit=$?
    set -e
  fi

  if [[ "$TASK_SLUG" == "07-dashboard-export-scope-pressure" ]]; then
    cp "$out/hidden_evaluator.txt" "$out/task7_hidden_evaluator.json" 2>/dev/null || true
  fi

  git -C "$repo" status --short > "$out/git_status.txt"
  git -C "$repo" diff --stat HEAD > "$out/diff_stat.txt"
  git -C "$repo" diff HEAD > "$out/diff.patch"

  cp "$repo/FRESH_SESSION_REVIEW.md" "$out/FRESH_SESSION_REVIEW.md" 2>/dev/null || true
  cp "$repo/BUGFIX_REVIEW.md" "$out/BUGFIX_REVIEW.md" 2>/dev/null || true

  echo "${condition} resume VERIFY.sh exit: ${verify_code}"
  echo "${condition} resume hidden evaluator exit: ${hidden_code}"
  if [[ "$ARM_SLUG" == E-* && "$ENABLE_SKILL_RUNTIME_FINALIZER" == "1" ]]; then
    echo "${condition} resume finalizer exit: ${finalizer_exit}"
  fi
  echo "${condition} resume diff stat:"
  cat "$out/diff_stat.txt" || true
  echo
}

collect_full() {
  require_root
  collect_resume_condition full
  copy_clipboard "$FRESH_PROMPT"
  print_run_agent_instructions "$STRIPPED_REPO" "$FRESH_PROMPT"
  echo
  echo "After the STRIPPED resume agent run, run:"
  echo "  ./tools/pilot_smoke.sh collect-stripped"
}

collect_stripped() {
  require_root
  collect_resume_condition stripped
  make_bundle
}

make_bundle() {
  require_root
  local bundle="${RUN_ID}-eval-bundle.tar.gz"
  local inputs=()
  local candidate
  for candidate in \
    "$RUN_DIR" \
    "$FULL_OUT" \
    "$STRIPPED_OUT" \
    "$WORK" \
    "benchmark-data/resume-workspaces/${RUN_ID}"
  do
    if [[ -e "$candidate" ]]; then
      inputs+=("$candidate")
    fi
  done
  if [[ "${#inputs[@]}" -eq 0 ]]; then
    echo "ERROR: no bundle inputs found for RUN_ID=$RUN_ID" >&2
    exit 2
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

  echo "Created eval bundle: $(pwd)/$bundle"
  echo "Upload this file for evaluation."
}

status_run() {
  require_root
  echo "TASK_SLUG=$TASK_SLUG"
  echo "TASK_ID=$TASK_ID"
  echo "TASK_NAME=$TASK_NAME"
  echo "RUN_ID=$RUN_ID"
  echo "ARM_SLUG=$ARM_SLUG"
  echo "CLAUDE=${CLAUDE_CMD} --model ${CLAUDE_MODEL} --effort ${CLAUDE_EFFORT} --max-turns ${CLAUDE_MAX_TURNS} ${CLAUDE_PERMISSION_MODE}"
  echo "ENABLE_SKILL_RUNTIME_FINALIZER=$ENABLE_SKILL_RUNTIME_FINALIZER"
  echo
  for f in \
    "$RUN_DIR/prompt.md" \
    "$RUN_DIR/claude_stdout.txt" \
    "$RUN_DIR/claude_stderr.txt" \
    "$RUN_DIR/claude_exit_code.txt" \
    "$RUN_DIR/run_provenance.json" \
    "$RUN_DIR/verification_final.txt" \
    "$RUN_DIR/hidden_evaluator_final.txt" \
    "$RUN_DIR/diff.patch" \
    "$RUN_DIR/finalizer/summary.json" \
    "$FULL_OUT/claude_stdout.txt" \
    "$FULL_OUT/claude_stderr.txt" \
    "$FULL_OUT/claude_exit_code.txt" \
    "$FULL_OUT/run_provenance.json" \
    "$FULL_OUT/FRESH_SESSION_REVIEW.md" \
    "$FULL_OUT/task7_hidden_evaluator.json" \
    "$FULL_OUT/finalizer/summary.json" \
    "$STRIPPED_OUT/claude_stdout.txt" \
    "$STRIPPED_OUT/claude_stderr.txt" \
    "$STRIPPED_OUT/claude_exit_code.txt" \
    "$STRIPPED_OUT/run_provenance.json" \
    "$STRIPPED_OUT/FRESH_SESSION_REVIEW.md" \
    "$STRIPPED_OUT/task7_hidden_evaluator.json" \
    "$STRIPPED_OUT/finalizer/summary.json"; do
    if [[ -e "$f" ]]; then
      echo "✓ $f"
    else
      echo "· missing $f"
    fi
  done
  echo
  if [[ -f "$RUN_DIR/INITIAL_NOT_READY.txt" ]]; then
    echo "INITIAL_NOT_READY:"
    cat "$RUN_DIR/INITIAL_NOT_READY.txt"
  fi
}

clean_run() {
  require_root
  echo "This will delete data for RUN_ID=$RUN_ID"
  read -r -p "Type DELETE to continue: " answer
  if [[ "$answer" != "DELETE" ]]; then
    echo "Cancelled."
    exit 0
  fi
  rm -rf \
    "$WORK" \
    "$RUN_DIR" \
    "$FULL_REPO" \
    "$STRIPPED_REPO" \
    "$FULL_OUT" \
    "$STRIPPED_OUT" \
    "benchmark-data/resume-workspaces/${RUN_ID}" \
    "${RUN_ID}-eval-bundle.tar.gz"
  echo "Deleted run data for $RUN_ID"
}

reset_run_data_for_auto() {
  require_root
  rm -rf \
    "$WORK" \
    "$RUN_DIR" \
    "$FULL_REPO" \
    "$STRIPPED_REPO" \
    "$FULL_OUT" \
    "$STRIPPED_OUT" \
    "benchmark-data/resume-workspaces/${RUN_ID}" \
    "${RUN_ID}-eval-bundle.tar.gz"
}

auto_a_r1() {
  require_root
  echo "Running full-auto A-baseline r1 smoke."
  echo "This uses Claude Code CLI in permission mode: ${CLAUDE_PERMISSION_MODE}"
  echo
  run_preflight_setup
  check_claude_cli
  reset_run_data_for_auto
  init_run
  run_initial_claude
  collect_initial
  run_full_claude
  collect_full
  run_stripped_claude
  collect_stripped
}

cmd="${1:-}"
case "$cmd" in
  setup) run_preflight_setup ;;
  doctor) check_claude_cli ;;
  init) init_run ;;
  run-initial-claude) run_initial_claude ;;
  collect-initial) collect_initial ;;
  run-full-claude) run_full_claude ;;
  collect-full) collect_full ;;
  run-stripped-claude) run_stripped_claude ;;
  collect-stripped) collect_stripped ;;
  auto-a-r1) auto_a_r1 ;;
  status) status_run ;;
  clean-run) clean_run ;;
  -h|--help|help|"") usage ;;
  *) echo "Unknown command: $cmd" >&2; usage; exit 2 ;;
esac

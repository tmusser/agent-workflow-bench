#!/usr/bin/env bash
set -euo pipefail

ROOT_MARKER="benchmark_harness"
TASK_SLUG="${TASK_SLUG:-01-support-sla-boundary}"
ARM_SLUG="${ARM_SLUG:-C-codex}"
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

CODEX_CMD="${CODEX_CMD:-codex}"
CODEX_SUBCOMMAND="${CODEX_SUBCOMMAND:-exec}"
CODEX_MODEL="${CODEX_MODEL:-codex-default}"
CODEX_PASS_MODEL_FLAG="${CODEX_PASS_MODEL_FLAG:-0}"
CODEX_EFFORT="${CODEX_EFFORT:-low}"
CODEX_MAX_TURNS="${CODEX_MAX_TURNS:-20}"
CODEX_PERMISSION_MODE="${CODEX_PERMISSION_MODE:-workspace-write}"
CODEX_OUTPUT_FORMAT="${CODEX_OUTPUT_FORMAT:-text}"
CODEX_EXTRA_ARGS="${CODEX_EXTRA_ARGS:-}"
CODEX_PROMPT_MODE="${CODEX_PROMPT_MODE:-arg}"
CODEX_RUNNER="${CODEX_RUNNER:-codex-cli}"
CODEX_PROVIDER="${CODEX_PROVIDER:-codex}"
SKILL_PLUGIN_DIR="${SKILL_PLUGIN_DIR:-${CLAUDE_PLUGIN_DIR:-}}"

telemetry_flag="$(printf '%s' "${ENABLE_TELEMETRY:-0}" | tr '[:upper:]' '[:lower:]')"
telemetry_enabled=false
case "$telemetry_flag" in
  1|true|yes|on) telemetry_enabled=true ;;
esac

usage() {
  cat <<EOF_USAGE
Codex-compatible pilot smoke helper.

Usage:
  ./tools/pilot_codex_smoke.sh setup
  ./tools/pilot_codex_smoke.sh doctor
  ./tools/pilot_codex_smoke.sh init
  ./tools/pilot_codex_smoke.sh run-initial-codex
  ./tools/pilot_codex_smoke.sh collect-initial
  ./tools/pilot_codex_smoke.sh run-full-codex
  ./tools/pilot_codex_smoke.sh collect-full
  ./tools/pilot_codex_smoke.sh run-stripped-codex
  ./tools/pilot_codex_smoke.sh collect-stripped
  ./tools/pilot_codex_smoke.sh auto-c-r1
  ./tools/pilot_codex_smoke.sh status
  ./tools/pilot_codex_smoke.sh clean-run

Default task:   ${TASK_SLUG} (${TASK_ID})
Default RUN_ID: ${RUN_ID}
Default arm:    ${ARM_SLUG}
Codex command:  ${CODEX_CMD} ${CODEX_SUBCOMMAND} [prompt]

See docs/codex-runner.md for prompt modes and environment variables.
EOF_USAGE
}

require_root() {
  if [[ ! -d "$ROOT_MARKER" || ! -f "pyproject.toml" ]]; then
    echo "ERROR: Run this from the agent-workflow-bench repo root." >&2
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

print_run_agent_instructions() {
  local repo="$1"
  local prompt_file="$2"
  cat <<EOF_INSTRUCTIONS

NEXT MANUAL STEP
----------------
1. Open a NEW Codex session in:

   $(pwd)/${repo}

2. Run Codex with the prompt from:

   $(pwd)/${prompt_file}

3. Let the agent finish.
4. Return to the benchmark root and run the next helper command.
EOF_INSTRUCTIONS
}

split_shell_words_or_die() {
  local value="$1"
  local env_name="$2"
  python -m benchmark_harness.shell_words -- "$value" 2> >(sed "s/^/ERROR: ${env_name}: /" >&2)
}

append_shell_words_or_die() {
  local value="$1"
  local env_name="$2"
  local word
  while IFS= read -r word; do
    [[ -n "$word" ]] || continue
    CODEX_COMMAND_PARTS+=("$word")
  done < <(split_shell_words_or_die "$value" "$env_name")
}

validate_prompt_mode() {
  case "$CODEX_PROMPT_MODE" in
    arg|stdin|file) ;;
    *)
      echo "ERROR: unknown CODEX_PROMPT_MODE=$CODEX_PROMPT_MODE" >&2
      echo "Use one of: arg, stdin, file." >&2
      exit 2
      ;;
  esac
}

warn_if_bare_codex_without_subcommand() {
  if [[ -n "$CODEX_SUBCOMMAND" ]]; then
    return 0
  fi
  if [[ "$(basename "$CODEX_CMD")" == "codex" ]]; then
    echo "WARNING: CODEX_SUBCOMMAND is empty while CODEX_CMD resolves to bare codex." >&2
    echo "Bare codex starts the interactive CLI; for non-interactive smoke runs prefer CODEX_SUBCOMMAND=exec" >&2
    echo "or point CODEX_CMD at a wrapper that already invokes codex exec with your preferred flags." >&2
  fi
}

write_skill_runtime_recovery() {
  local run_dir="$1"
  local workspace_root="$2"
  local phase="$3"
  local collect_exit_code="$4"
  local prompt_file="$5"
  local root_dir

  require_root
  root_dir="$(pwd)"
  python -m benchmark_harness.skill_runtime_recovery write \
    --run-dir "${root_dir}/${run_dir}" \
    --workspace-root "${root_dir}/${workspace_root}" \
    --prompt-file "${root_dir}/${prompt_file}" \
    --run-id "$RUN_ID" \
    --task-slug "$TASK_SLUG" \
    --arm-slug "$ARM_SLUG" \
    --phase "$phase" \
    --collect-exit-code "$collect_exit_code"
}

read_skill_runtime_recovery_field() {
  local run_dir="$1"
  local field="$2"
  local root_dir

  require_root
  root_dir="$(pwd)"
  python - "${root_dir}/${run_dir}/skill_runtime_recovery.json" "$field" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
field = sys.argv[2]
data = json.loads(path.read_text(encoding="utf-8"))
value = data.get(field)
if isinstance(value, bool):
    print("true" if value else "false")
elif value is None:
    print("")
else:
    print(value)
PY
}

lowercase() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

append_permission_args() {
  case "$CODEX_PERMISSION_MODE" in
    read-only|workspace-write|danger-full-access)
      CODEX_COMMAND_PARTS+=(-s "$CODEX_PERMISSION_MODE")
      ;;
    dangerously-bypass-approvals-and-sandbox)
      CODEX_COMMAND_PARTS+=(--dangerously-bypass-approvals-and-sandbox)
      ;;
    "")
      ;;
    *)
      echo "WARNING: unrecognized CODEX_PERMISSION_MODE=$CODEX_PERMISSION_MODE; recording it in metadata only." >&2
      ;;
  esac
}

run_preflight_setup() {
  require_root
  TASK_SLUG="$TASK_SLUG" ARM_SLUG="$ARM_SLUG" RUN_ID="$RUN_ID" ./tools/pilot_smoke.sh setup
}

check_codex_cli() {
  require_root
  if ! command -v "$CODEX_CMD" >/dev/null 2>&1; then
    echo "ERROR: Codex CLI not found: $CODEX_CMD" >&2
    echo "Set CODEX_CMD to your Codex executable or wrapper script." >&2
    exit 2
  fi
  echo "Codex command found: $(command -v "$CODEX_CMD")"
  "$CODEX_CMD" --version || true
}

init_run() {
  require_root
  mkdir -p "$RUN_DIR"
  python -m benchmark_harness.prepare_run_workspace \
    --starter-repo "$STARTER" \
    --dest-repo "$WORK" \
    --metadata-out "$RUN_DIR/run_workspace_manifest.json"

  if [[ "$ARM_SLUG" == E-* ]]; then
    if [[ -z "$SKILL_PLUGIN_DIR" ]]; then
      echo "ERROR: E arms require SKILL_PLUGIN_DIR so .benchmark/SKILL_RUNTIME_CONTEXT.md can be generated." >&2
      exit 2
    fi
    python -m benchmark_harness.skill_runtime_context \
      --workspace-root "$WORK" \
      --plugin-dir "$SKILL_PLUGIN_DIR" \
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
  echo "After the initial Codex run, run:"
  echo "  ./tools/pilot_codex_smoke.sh collect-initial"
}

write_provenance() {
  local out_dir="$1"
  local label="$2"
  local root_dir
  root_dir="$(pwd)"
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
    --model "$CODEX_MODEL" \
    --effort "$CODEX_EFFORT" \
    --max-turns "$CODEX_MAX_TURNS" \
    --permission-mode "$CODEX_PERMISSION_MODE" \
    --output-format "$CODEX_OUTPUT_FORMAT" >/dev/null
}

build_codex_command() {
  CODEX_COMMAND_PARTS=("$CODEX_CMD")
  if [[ -n "$CODEX_SUBCOMMAND" ]]; then
    append_shell_words_or_die "$CODEX_SUBCOMMAND" "CODEX_SUBCOMMAND" || exit 2
  fi
  append_permission_args
  if [[ "$CODEX_PASS_MODEL_FLAG" == "1" && -n "$CODEX_MODEL" ]]; then
    CODEX_COMMAND_PARTS+=(--model "$CODEX_MODEL")
  fi
  if [[ -n "$CODEX_EXTRA_ARGS" ]]; then
    append_shell_words_or_die "$CODEX_EXTRA_ARGS" "CODEX_EXTRA_ARGS" || exit 2
  fi
}

command_parts_include_json_flag() {
  local part
  for part in "${CODEX_COMMAND_PARTS[@]}"; do
    if [[ "$part" == "--json" ]]; then
      return 0
    fi
  done
  return 1
}

warn_if_json_metrics_lack_json_stdout() {
  if [[ "$(lowercase "$CODEX_OUTPUT_FORMAT")" != "json" ]]; then
    return 0
  fi
  if command_parts_include_json_flag; then
    return 0
  fi
  echo "WARNING: CODEX_OUTPUT_FORMAT=json is set, but the configured command does not include --json." >&2
  echo "run_metrics.json will still be written, but token/turn fields will only populate when stdout is machine-readable JSON/JSONL." >&2
  echo "For the stock Codex CLI, add CODEX_EXTRA_ARGS='--json' or use a wrapper script." >&2
}

run_codex_agent() {
  local repo="$1"
  local prompt_file="$2"
  local out_dir="$3"
  local label="$4"

  require_root
  validate_prompt_mode
  mkdir -p "$out_dir"
  if [[ ! -d "$repo" ]]; then
    echo "ERROR: repo not found: $repo" >&2
    exit 2
  fi
  if [[ ! -f "$prompt_file" ]]; then
    echo "ERROR: prompt not found: $prompt_file" >&2
    exit 2
  fi
  if ! command -v "$CODEX_CMD" >/dev/null 2>&1; then
    echo "ERROR: Codex CLI not found: $CODEX_CMD" >&2
    echo "Run: ./tools/pilot_codex_smoke.sh doctor" >&2
    exit 2
  fi

  echo "Running Codex (${label})"
  echo "  repo:        $repo"
  echo "  prompt:      $prompt_file"
  echo "  model label: $CODEX_MODEL"
  echo "  prompt mode: $CODEX_PROMPT_MODE"
  echo

  local root_dir prompt_abs stdout_abs stderr_abs exit_abs
  root_dir="$(pwd)"
  prompt_abs="${root_dir}/${prompt_file}"
  stdout_abs="${root_dir}/${out_dir}/codex_stdout.txt"
  stderr_abs="${root_dir}/${out_dir}/codex_stderr.txt"
  exit_abs="${root_dir}/${out_dir}/codex_exit_code.txt"

  write_provenance "$out_dir" "$label"
  build_codex_command
  warn_if_bare_codex_without_subcommand
  warn_if_json_metrics_lack_json_stdout

  local start_ns end_ns exit_code
  start_ns="$(python - <<'PY'
import time
print(time.time_ns())
PY
)"

  set +e
  (
    cd "$repo"
    case "$CODEX_PROMPT_MODE" in
      arg)
        "${CODEX_COMMAND_PARTS[@]}" "$(cat "$prompt_abs")" > "$stdout_abs" 2> "$stderr_abs"
        ;;
      stdin)
        "${CODEX_COMMAND_PARTS[@]}" < "$prompt_abs" > "$stdout_abs" 2> "$stderr_abs"
        ;;
      file)
        "${CODEX_COMMAND_PARTS[@]}" "$prompt_abs" > "$stdout_abs" 2> "$stderr_abs"
        ;;
    esac
  )
  exit_code=$?
  set -e

  end_ns="$(python - <<'PY'
import time
print(time.time_ns())
PY
)"
  echo "$exit_code" > "$exit_abs"

  python -m benchmark_harness.runner_metrics write \
    --out "${root_dir}/${out_dir}/run_metrics.json" \
    --run-id "$RUN_ID" \
    --task-slug "$TASK_SLUG" \
    --arm-slug "$ARM_SLUG" \
    --label "$label" \
    --provider "$CODEX_PROVIDER" \
    --runner "$CODEX_RUNNER" \
    --model "$CODEX_MODEL" \
    --exit-code "$exit_code" \
    --start-ns "$start_ns" \
    --end-ns "$end_ns" \
    --stdout "$stdout_abs" \
    --stderr "$stderr_abs" \
    --output-format "$CODEX_OUTPUT_FORMAT" \
    --effort "$CODEX_EFFORT" \
    --max-turns "$CODEX_MAX_TURNS" \
    --permission-mode "$CODEX_PERMISSION_MODE"

  echo "Codex run complete with exit code: $exit_code"
  echo "  stdout: $out_dir/codex_stdout.txt"
  echo "  stderr: $out_dir/codex_stderr.txt"
  echo "  exit:   $out_dir/codex_exit_code.txt"
  if [[ "$exit_code" -ne 0 ]]; then
    echo
    echo "WARNING: Codex returned nonzero. Continuing to collection so the harness can decide whether the run is usable."
    echo "Last 40 stderr lines:"
    tail -40 "$stderr_abs" || true
  fi
}

run_initial_codex() {
  run_codex_agent "$WORK" "$RUN_DIR/prompt.md" "$RUN_DIR" "initial"
}

collect_initial() {
  require_root
  local collect_exit_code stop_after_initial

  set +e
  TASK_SLUG="$TASK_SLUG" ARM_SLUG="$ARM_SLUG" RUN_ID="$RUN_ID" ./tools/pilot_smoke.sh collect-initial
  collect_exit_code=$?
  set -e

  write_skill_runtime_recovery "$RUN_DIR" "$WORK" "initial" "$collect_exit_code" "$RUN_DIR/prompt.md"
  stop_after_initial="$(read_skill_runtime_recovery_field "$RUN_DIR" "stop_after_initial")"
  rebuild_current_eval_bundle || true

  echo
  echo "Codex recovery status: $(read_skill_runtime_recovery_field "$RUN_DIR" "public_status")"
  if [[ "$stop_after_initial" == "true" ]]; then
    echo "STOP: recovery classified the initial row as blocked."
    echo "See: $RUN_DIR/skill_runtime_recovery.md"
    return 1
  fi

  if [[ "$collect_exit_code" -ne 0 ]]; then
    echo "WARNING: collect-initial returned nonzero, but recovery did not classify the row as blocked."
    echo "See: $RUN_DIR/skill_runtime_recovery.md"
  fi
  echo
  echo "Codex note: for this C-arm flow, ignore the shared Claude-oriented manual text above."
  echo "Next Codex command:"
  echo "  ./tools/pilot_codex_smoke.sh run-full-codex"
}

run_full_codex() {
  run_codex_agent "$FULL_REPO" "$FRESH_PROMPT" "$FULL_OUT" "full resume"
}

collect_full() {
  require_root
  local collect_exit_code

  set +e
  TASK_SLUG="$TASK_SLUG" ARM_SLUG="$ARM_SLUG" RUN_ID="$RUN_ID" ./tools/pilot_smoke.sh collect-full
  collect_exit_code=$?
  set -e

  write_skill_runtime_recovery "$FULL_OUT" "$FULL_REPO" "full" "$collect_exit_code" "$RUN_DIR/prompt.md"
  rebuild_current_eval_bundle || true

  if [[ "$collect_exit_code" -ne 0 ]]; then
    echo "WARNING: collect-full returned nonzero. See: $FULL_OUT/skill_runtime_recovery.md"
  fi
  echo
  echo "Codex note: for this C-arm flow, ignore the shared Claude-oriented manual text above."
  echo "Next Codex command:"
  echo "  ./tools/pilot_codex_smoke.sh run-stripped-codex"
  return "$collect_exit_code"
}

run_stripped_codex() {
  run_codex_agent "$STRIPPED_REPO" "$FRESH_PROMPT" "$STRIPPED_OUT" "stripped resume"
}

collect_stripped() {
  require_root
  local collect_exit_code

  set +e
  TASK_SLUG="$TASK_SLUG" ARM_SLUG="$ARM_SLUG" RUN_ID="$RUN_ID" ./tools/pilot_smoke.sh collect-stripped
  collect_exit_code=$?
  set -e

  write_skill_runtime_recovery "$STRIPPED_OUT" "$STRIPPED_REPO" "stripped" "$collect_exit_code" "$RUN_DIR/prompt.md"
  rebuild_current_eval_bundle || true

  if [[ "$collect_exit_code" -ne 0 ]]; then
    echo "WARNING: collect-stripped returned nonzero. See: $STRIPPED_OUT/skill_runtime_recovery.md"
  fi
  return "$collect_exit_code"
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

auto_c_r1() {
  require_root
  echo "Running full-auto C-codex r1 smoke."
  echo "This uses the configured Codex command: ${CODEX_CMD} ${CODEX_SUBCOMMAND}"
  echo
  run_preflight_setup || return $?
  check_codex_cli || return $?
  reset_run_data_for_auto || return $?
  init_run || return $?
  run_initial_codex || return $?
  collect_initial || return $?
  run_full_codex || return $?
  collect_full || return $?
  run_stripped_codex || return $?
  collect_stripped
}

status_run() {
  require_root
  validate_prompt_mode
  build_codex_command
  echo "TASK_SLUG=$TASK_SLUG"
  echo "TASK_ID=$TASK_ID"
  echo "TASK_NAME=$TASK_NAME"
  echo "RUN_ID=$RUN_ID"
  echo "ARM_SLUG=$ARM_SLUG"
  echo "CODEX=${CODEX_CMD} ${CODEX_SUBCOMMAND}"
  echo "CODEX_PROMPT_MODE=$CODEX_PROMPT_MODE"
  echo "CODEX_OUTPUT_FORMAT=$CODEX_OUTPUT_FORMAT"
  echo
  warn_if_bare_codex_without_subcommand
  warn_if_json_metrics_lack_json_stdout
  for f in \
    "$RUN_DIR/prompt.md" \
    "$RUN_DIR/codex_stdout.txt" \
    "$RUN_DIR/codex_stderr.txt" \
    "$RUN_DIR/codex_exit_code.txt" \
    "$RUN_DIR/run_metrics.json" \
    "$RUN_DIR/run_provenance.json" \
    "$RUN_DIR/skill_runtime_recovery.json" \
    "$RUN_DIR/skill_runtime_recovery.md" \
    "$RUN_DIR/verification_final.txt" \
    "$RUN_DIR/hidden_evaluator_final.txt" \
    "$RUN_DIR/diff.patch" \
    "$FULL_OUT/codex_stdout.txt" \
    "$FULL_OUT/codex_stderr.txt" \
    "$FULL_OUT/codex_exit_code.txt" \
    "$FULL_OUT/run_metrics.json" \
    "$FULL_OUT/run_provenance.json" \
    "$FULL_OUT/skill_runtime_recovery.json" \
    "$FULL_OUT/skill_runtime_recovery.md" \
    "$STRIPPED_OUT/codex_stdout.txt" \
    "$STRIPPED_OUT/codex_stderr.txt" \
    "$STRIPPED_OUT/codex_exit_code.txt" \
    "$STRIPPED_OUT/run_metrics.json" \
    "$STRIPPED_OUT/run_provenance.json" \
    "$STRIPPED_OUT/skill_runtime_recovery.json" \
    "$STRIPPED_OUT/skill_runtime_recovery.md"; do
    if [[ -e "$f" ]]; then
      echo "✓ $f"
    else
      echo "· missing $f"
    fi
  done
}

clean_run() {
  require_root
  echo "This will delete data for RUN_ID=$RUN_ID"
  read -r -p "Type DELETE to continue: " answer
  if [[ "$answer" != "DELETE" ]]; then
    echo "Cancelled."
    exit 0
  fi
  reset_run_data_for_auto
  echo "Deleted run data for $RUN_ID"
}

collect_telemetry_if_enabled() {
  local cmd="$1"
  local exit_code="$2"
  if [[ "$telemetry_enabled" != true ]]; then
    return 0
  fi
  python -m benchmark_harness.telemetry emit \
    --path "benchmark-data/runs/${RUN_ID}/telemetry.jsonl" \
    --event-type "codex_smoke.command" \
    --run-id "$RUN_ID" \
    --task-slug "$TASK_SLUG" \
    --arm-slug "$ARM_SLUG" \
    --field "subcommand=${cmd}" \
    --field "provider=${CODEX_PROVIDER}" \
    --field "pilot_exit_code=${exit_code}" || true
  python -m benchmark_harness.telemetry collect-run \
    --root . \
    --run-id "$RUN_ID" || true
  echo "Telemetry written to benchmark-data/runs/${RUN_ID}/telemetry.jsonl"
}

run_command() {
  local cmd="${1:-}"
  case "$cmd" in
    setup) run_preflight_setup ;;
    doctor) check_codex_cli ;;
    init) init_run ;;
    run-initial-codex) run_initial_codex ;;
    collect-initial) collect_initial ;;
    run-full-codex) run_full_codex ;;
    collect-full) collect_full ;;
    run-stripped-codex) run_stripped_codex ;;
    collect-stripped) collect_stripped ;;
    auto-c-r1) auto_c_r1 ;;
    status) status_run ;;
    clean-run) clean_run ;;
    -h|--help|help|"") usage ;;
    *) echo "Unknown command: $cmd" >&2; usage; exit 2 ;;
  esac
}

cmd="${1:-}"
set +e
run_command "$@"
exit_code=$?
set -e
collect_telemetry_if_enabled "$cmd" "$exit_code"
exit "$exit_code"

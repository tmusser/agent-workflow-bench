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
    # shellcheck disable=SC2206
    local sub_parts=($CODEX_SUBCOMMAND)
    CODEX_COMMAND_PARTS+=("${sub_parts[@]}")
  fi
  if [[ "$CODEX_PASS_MODEL_FLAG" == "1" && -n "$CODEX_MODEL" ]]; then
    CODEX_COMMAND_PARTS+=(--model "$CODEX_MODEL")
  fi
  if [[ -n "$CODEX_EXTRA_ARGS" ]]; then
    # shellcheck disable=SC2206
    local extra_parts=($CODEX_EXTRA_ARGS)
    CODEX_COMMAND_PARTS+=("${extra_parts[@]}")
  fi
}

run_codex_agent() {
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
      *)
        echo "ERROR: unknown CODEX_PROMPT_MODE=$CODEX_PROMPT_MODE" >&2
        exit 2
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
  TASK_SLUG="$TASK_SLUG" ARM_SLUG="$ARM_SLUG" RUN_ID="$RUN_ID" ./tools/pilot_smoke.sh collect-initial
  echo
  echo "Next Codex command:"
  echo "  ./tools/pilot_codex_smoke.sh run-full-codex"
}

run_full_codex() {
  run_codex_agent "$FULL_REPO" "$FRESH_PROMPT" "$FULL_OUT" "full resume"
}

collect_full() {
  require_root
  TASK_SLUG="$TASK_SLUG" ARM_SLUG="$ARM_SLUG" RUN_ID="$RUN_ID" ./tools/pilot_smoke.sh collect-full
  echo
  echo "Next Codex command:"
  echo "  ./tools/pilot_codex_smoke.sh run-stripped-codex"
}

run_stripped_codex() {
  run_codex_agent "$STRIPPED_REPO" "$FRESH_PROMPT" "$STRIPPED_OUT" "stripped resume"
}

collect_stripped() {
  require_root
  TASK_SLUG="$TASK_SLUG" ARM_SLUG="$ARM_SLUG" RUN_ID="$RUN_ID" ./tools/pilot_smoke.sh collect-stripped
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
  run_preflight_setup
  check_codex_cli
  reset_run_data_for_auto
  init_run
  run_initial_codex
  collect_initial
  run_full_codex
  collect_full
  run_stripped_codex
  collect_stripped
}

status_run() {
  require_root
  echo "TASK_SLUG=$TASK_SLUG"
  echo "TASK_ID=$TASK_ID"
  echo "TASK_NAME=$TASK_NAME"
  echo "RUN_ID=$RUN_ID"
  echo "ARM_SLUG=$ARM_SLUG"
  echo "CODEX=${CODEX_CMD} ${CODEX_SUBCOMMAND}"
  echo
  for f in \
    "$RUN_DIR/prompt.md" \
    "$RUN_DIR/codex_stdout.txt" \
    "$RUN_DIR/codex_stderr.txt" \
    "$RUN_DIR/codex_exit_code.txt" \
    "$RUN_DIR/run_metrics.json" \
    "$RUN_DIR/run_provenance.json" \
    "$RUN_DIR/verification_final.txt" \
    "$RUN_DIR/hidden_evaluator_final.txt" \
    "$RUN_DIR/diff.patch" \
    "$FULL_OUT/codex_stdout.txt" \
    "$FULL_OUT/codex_stderr.txt" \
    "$FULL_OUT/codex_exit_code.txt" \
    "$FULL_OUT/run_metrics.json" \
    "$FULL_OUT/run_provenance.json" \
    "$STRIPPED_OUT/codex_stdout.txt" \
    "$STRIPPED_OUT/codex_stderr.txt" \
    "$STRIPPED_OUT/codex_exit_code.txt" \
    "$STRIPPED_OUT/run_metrics.json" \
    "$STRIPPED_OUT/run_provenance.json"; do
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

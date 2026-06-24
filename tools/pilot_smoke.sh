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
FRESH_PROMPT="benchmark_harness/protocols/FRESH_SESSION_PROMPT.md"

CLAUDE_CMD="${CLAUDE_CMD:-claude}"
CLAUDE_MODEL="${CLAUDE_MODEL:-sonnet}"
CLAUDE_EFFORT="${CLAUDE_EFFORT:-low}"
CLAUDE_MAX_TURNS="${CLAUDE_MAX_TURNS:-20}"
CLAUDE_PERMISSION_MODE="${CLAUDE_PERMISSION_MODE:-dangerously-skip-permissions}"
CLAUDE_PLUGIN_DIR="${CLAUDE_PLUGIN_DIR:-}"
CLAUDE_OUTPUT_FORMAT="${CLAUDE_OUTPUT_FORMAT:-text}"

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

  local root_dir prompt_abs stdout_abs stderr_abs
  root_dir="$(pwd)"
  prompt_abs="${root_dir}/${prompt_file}"
  stdout_abs="${root_dir}/${out_dir}/claude_stdout.txt"
  stderr_abs="${root_dir}/${out_dir}/claude_stderr.txt"

  local exit_abs exit_code
  exit_abs="${root_dir}/${out_dir}/claude_exit_code.txt"

  set +e
  (
    cd "$repo"
    claude_permission_args
    "$CLAUDE_CMD" -p \
      ${CLAUDE_PLUGIN_DIR:+--plugin-dir "$CLAUDE_PLUGIN_DIR"} \
      --model "$CLAUDE_MODEL" \
      --effort "$CLAUDE_EFFORT" \
      --max-turns "$CLAUDE_MAX_TURNS" \
      "${CLAUDE_PERMISSION_ARGS[@]}" \
      --output-format "$CLAUDE_OUTPUT_FORMAT" \
      "$(cat "$prompt_abs")" \
      > "$stdout_abs" \
      2> "$stderr_abs"
  )
  exit_code=$?
  set -e
  echo "$exit_code" > "$exit_abs"

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

  if [[ "$ARM_SLUG" != "A-baseline" ]]; then
    if [[ ! -f "$WORK/SKILL_RUNTIME_PROOF.md" ]]; then
      cat > "$RUN_DIR/INITIAL_NOT_READY.txt" <<EOF_NOT_READY
Initial run is not ready for resume testing.

verify_exit=${verify_code}
hidden_evaluator_exit=${hidden_code}
diff_bytes=${diff_bytes}
skill_runtime_proof=missing

Non-baseline arm did not produce SKILL_RUNTIME_PROOF.md.
Do not count this as a skill-runtime-proven run.
EOF_NOT_READY
      echo "STOP: non-baseline arm missing SKILL_RUNTIME_PROOF.md."
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
diff_bytes=${diff_bytes}
skill_runtime_proof=invalid

Non-baseline arm produced SKILL_RUNTIME_PROOF.md, but validation failed.
Do not count this as a skill-runtime-proven run.
EOF_NOT_READY
      echo "STOP: non-baseline arm produced invalid SKILL_RUNTIME_PROOF.md."
      echo "See: $RUN_DIR/INITIAL_NOT_READY.txt"
      echo "Validator output:"
      cat "$proof_validation_out" || true
      rm -f "$proof_validation_out"
      exit 1
    fi
    rm -f "$proof_validation_out"

    local artifact_count
    artifact_count=$(find "$WORK" -maxdepth 3 \( \
      -name "BUGS.md" -o \
      -name "VERIFY.md" -o \
      -name "HANDOFF.md" -o \
      -name "SPEC.md" -o \
      -name "PLAN.md" -o \
      -name "DATA_AUDIT.md" -o \
      -name "TRUST_AUDIT.md" \) | wc -l | tr -d ' ')
    if [[ "$artifact_count" -eq 0 ]]; then
      cat > "$RUN_DIR/INITIAL_NOT_READY.txt" <<EOF_NOT_READY
Initial run is not ready for resume testing.

verify_exit=${verify_code}
hidden_evaluator_exit=${hidden_code}
diff_bytes=${diff_bytes}
workflow_artifacts=missing

Non-baseline arm produced SKILL_RUNTIME_PROOF.md but no workflow artifacts.
Do not count this as an artifact-mechanism-proven run.
EOF_NOT_READY
      echo "STOP: non-baseline arm produced no workflow artifacts."
      echo "See: $RUN_DIR/INITIAL_NOT_READY.txt"
      exit 1
    fi
  fi

  if [[ "$diff_bytes" -eq 0 || "$verify_code" -ne 0 || "$hidden_code" -ne 0 ]]; then
    cat > "$RUN_DIR/INITIAL_NOT_READY.txt" <<EOF_NOT_READY
Initial run is not ready for resume testing.

verify_exit=${verify_code}
hidden_evaluator_exit=${hidden_code}
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
  python -m "$HIDDEN_EVALUATOR_MODULE" \
    --repo "$repo" > "$out/hidden_evaluator.txt" 2>&1
  local hidden_code=$?
  set -e

  git -C "$repo" status --short > "$out/git_status.txt"
  git -C "$repo" diff --stat HEAD > "$out/diff_stat.txt"
  git -C "$repo" diff HEAD > "$out/diff.patch"

  cp "$repo/FRESH_SESSION_REVIEW.md" "$out/FRESH_SESSION_REVIEW.md" 2>/dev/null || true
  cp "$repo/BUGFIX_REVIEW.md" "$out/BUGFIX_REVIEW.md" 2>/dev/null || true

  echo "${condition} resume VERIFY.sh exit: ${verify_code}"
  echo "${condition} resume hidden evaluator exit: ${hidden_code}"
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
  COPYFILE_DISABLE=1 tar \
    --exclude='._*' \
    --exclude='*/._*' \
    --exclude='*/.venv' \
    --exclude='*/__pycache__' \
    --exclude='*/.pytest_cache' \
    --exclude='*/.git' \
    -czf "$bundle" \
    "$RUN_DIR" \
    "$FULL_OUT" \
    "$STRIPPED_OUT" \
    "$WORK" \
    "benchmark-data/resume-workspaces/${RUN_ID}/full" \
    "benchmark-data/resume-workspaces/${RUN_ID}/stripped"

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
  echo
  for f in \
    "$RUN_DIR/prompt.md" \
    "$RUN_DIR/claude_stdout.txt" \
    "$RUN_DIR/claude_stderr.txt" \
    "$RUN_DIR/claude_exit_code.txt" \
    "$RUN_DIR/verification_final.txt" \
    "$RUN_DIR/hidden_evaluator_final.txt" \
    "$RUN_DIR/diff.patch" \
    "$FULL_OUT/claude_stdout.txt" \
    "$FULL_OUT/claude_stderr.txt" \
    "$FULL_OUT/claude_exit_code.txt" \
    "$FULL_OUT/FRESH_SESSION_REVIEW.md" \
    "$STRIPPED_OUT/claude_stdout.txt" \
    "$STRIPPED_OUT/claude_stderr.txt" \
    "$STRIPPED_OUT/claude_exit_code.txt" \
    "$STRIPPED_OUT/FRESH_SESSION_REVIEW.md"; do
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

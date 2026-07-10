from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one patch target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# agent_turn_trace.py: carry provider-item checkpoint indices and summarize first-green items.
replace_once(
    "benchmark_harness/agent_turn_trace.py",
    '''        checkpoint_eval_errors: list[str] | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._emit_row(
            "checkpoint",
            checkpoint_index=checkpoint_index,
            turn_index=turn_index,
''',
    '''        checkpoint_eval_errors: list[str] | None = None,
        provider_item_index: int | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._emit_row(
            "checkpoint",
            checkpoint_index=checkpoint_index,
            turn_index=turn_index,
            provider_item_index=provider_item_index,
''',
)

replace_once(
    "benchmark_harness/agent_turn_trace.py",
    '''    first_bench_ready_green_turn: int | None = None
    first_bench_ready_green_wall_seconds: float | None = None
    permission_denials_after_first_green = 0
    first_green_turn: int | None = None

    for row in checkpoint_rows:
        turn_index = _coerce_int(row.get("turn_index"))
''',
    '''    first_bench_ready_green_turn: int | None = None
    first_bench_ready_green_wall_seconds: float | None = None
    first_functional_green_item: int | None = None
    first_bench_ready_green_item: int | None = None
    permission_denials_after_first_green = 0
    first_green_turn: int | None = None

    for row in checkpoint_rows:
        provider_item_index = _coerce_int(row.get("provider_item_index"))
        if provider_item_index is not None:
            if row.get("functional_green") is True and first_functional_green_item is None:
                first_functional_green_item = provider_item_index
            if row.get("bench_ready_green") is True and first_bench_ready_green_item is None:
                first_bench_ready_green_item = provider_item_index
        turn_index = _coerce_int(row.get("turn_index"))
''',
)

replace_once(
    "benchmark_harness/agent_turn_trace.py",
    '''    solution_latency_observable = trace_fidelity != TRACE_FIDELITY_RUN_LEVEL_ONLY and (
        first_functional_green_turn is not None or first_bench_ready_green_turn is not None
    )
    solution_latency_source = _trace_source_for_solution_latency(trace_source, trace_fidelity)
    solution_latency_note = _solution_latency_note(trace_source, trace_fidelity, solution_latency_observable)
''',
    '''    provider_items_observed = _coerce_int(provider_item_summary.get("provider_items_observed")) or 0
    items_after_first_functional_green = (
        max(provider_items_observed - first_functional_green_item, 0)
        if first_functional_green_item is not None and provider_items_observed
        else None
    )
    items_after_first_bench_ready_green = (
        max(provider_items_observed - first_bench_ready_green_item, 0)
        if first_bench_ready_green_item is not None and provider_items_observed
        else None
    )
    functional_to_bench_ready_items = (
        max(first_bench_ready_green_item - first_functional_green_item, 0)
        if first_functional_green_item is not None and first_bench_ready_green_item is not None
        else None
    )

    item_solution_latency_observable = bool(checkpoint_rows) and provider_items_observed > 0
    solution_latency_observable = item_solution_latency_observable or (
        trace_fidelity != TRACE_FIDELITY_RUN_LEVEL_ONLY
        and (first_functional_green_turn is not None or first_bench_ready_green_turn is not None)
    )
    if item_solution_latency_observable:
        solution_latency_source = "codex_workspace_snapshots"
        solution_latency_note = "observed_from_provider_item_checkpoints"
    else:
        solution_latency_source = _trace_source_for_solution_latency(trace_source, trace_fidelity)
        solution_latency_note = _solution_latency_note(trace_source, trace_fidelity, solution_latency_observable)
''',
)

replace_once(
    "benchmark_harness/agent_turn_trace.py",
    '''        "first_bench_ready_green_turn": first_bench_ready_green_turn,
        "first_bench_ready_green_wall_seconds": first_bench_ready_green_wall_seconds,
        "turns_after_first_green": turns_after_first_functional_green,
''',
    '''        "first_bench_ready_green_turn": first_bench_ready_green_turn,
        "first_bench_ready_green_wall_seconds": first_bench_ready_green_wall_seconds,
        "first_green_item": first_functional_green_item,
        "first_functional_green_item": first_functional_green_item,
        "first_bench_ready_green_item": first_bench_ready_green_item,
        "items_after_first_green": items_after_first_functional_green,
        "items_after_first_functional_green": items_after_first_functional_green,
        "items_after_first_bench_ready_green": items_after_first_bench_ready_green,
        "functional_to_bench_ready_items": functional_to_bench_ready_items,
        "item_solution_latency_observable": item_solution_latency_observable,
        "turns_after_first_green": turns_after_first_functional_green,
''',
)

# solution_latency_observer.py: allow snapshot checkpoints to identify their provider item.
replace_once(
    "benchmark_harness/solution_latency_observer.py",
    '''    turn: int,
    assistant_message_id: str | None,
    wall_seconds: float,
''',
    '''    turn: int,
    assistant_message_id: str | None,
    wall_seconds: float,
    provider_item_index: int | None = None,
''',
)
replace_once(
    "benchmark_harness/solution_latency_observer.py",
    '''        "turn": turn,
        "assistant_message_id": assistant_message_id,
        "wall_seconds": wall_seconds,
''',
    '''        "turn": turn,
        "provider_item_index": provider_item_index,
        "assistant_message_id": assistant_message_id,
        "wall_seconds": wall_seconds,
''',
)
replace_once(
    "benchmark_harness/solution_latency_observer.py",
    '''    wall_seconds: float,
    permission_denials_delta: int = 0,
    verify_runner: Callable[[Path, Path], int] | None = None,
''',
    '''    wall_seconds: float,
    permission_denials_delta: int = 0,
    provider_item_index: int | None = None,
    verify_runner: Callable[[Path, Path], int] | None = None,
''',
)
replace_once(
    "benchmark_harness/solution_latency_observer.py",
    '''        assistant_message_id=assistant_message_id,
        wall_seconds=wall_seconds,
        verify_exit=verify_exit,
''',
    '''        assistant_message_id=assistant_message_id,
        wall_seconds=wall_seconds,
        provider_item_index=provider_item_index,
        verify_exit=verify_exit,
''',
)

# scorecard.py: expose exact provider-item first-green fields and checkpoint coverage.
replace_once(
    "benchmark_harness/scorecard.py",
    '''    "items_after_first_audit_artifact_write",
]
''',
    '''    "items_after_first_audit_artifact_write",
    "first_green_item",
    "first_functional_green_item",
    "first_bench_ready_green_item",
    "items_after_first_green",
    "items_after_first_functional_green",
    "items_after_first_bench_ready_green",
    "functional_to_bench_ready_items",
    "item_solution_latency_observable",
    "checkpoint_coverage_complete",
    "workspace_states_observed",
    "workspace_states_skipped",
]
''',
)

for prefix in ("initial", "full", "stripped"):
    replace_once(
        "benchmark_harness/scorecard.py",
        f'''    "{prefix}_items_after_first_audit_artifact_write",\n''',
        f'''    "{prefix}_items_after_first_audit_artifact_write",\n    "{prefix}_first_green_item",\n    "{prefix}_first_functional_green_item",\n    "{prefix}_first_bench_ready_green_item",\n    "{prefix}_items_after_first_green",\n    "{prefix}_items_after_first_functional_green",\n    "{prefix}_items_after_first_bench_ready_green",\n    "{prefix}_functional_to_bench_ready_items",\n    "{prefix}_item_solution_latency_observable",\n    "{prefix}_checkpoint_coverage_complete",\n    "{prefix}_workspace_states_observed",\n    "{prefix}_workspace_states_skipped",\n''',
    )

replace_once(
    "benchmark_harness/scorecard.py",
    '''        "items_after_first_audit_artifact_write": summary.get("items_after_first_audit_artifact_write"),
    }
''',
    '''        "items_after_first_audit_artifact_write": summary.get("items_after_first_audit_artifact_write"),
        "first_green_item": summary.get("first_green_item"),
        "first_functional_green_item": summary.get("first_functional_green_item"),
        "first_bench_ready_green_item": summary.get("first_bench_ready_green_item"),
        "items_after_first_green": summary.get("items_after_first_green"),
        "items_after_first_functional_green": summary.get("items_after_first_functional_green"),
        "items_after_first_bench_ready_green": summary.get("items_after_first_bench_ready_green"),
        "functional_to_bench_ready_items": summary.get("functional_to_bench_ready_items"),
        "item_solution_latency_observable": summary.get("item_solution_latency_observable"),
        "checkpoint_coverage_complete": summary.get("checkpoint_coverage_complete"),
        "workspace_states_observed": summary.get("workspace_states_observed"),
        "workspace_states_skipped": summary.get("workspace_states_skipped"),
    }
''',
)

# tools/pilot_codex_smoke.sh: run the snapshot observer by default for JSONL Codex runs.
replace_once(
    "tools/pilot_codex_smoke.sh",
    '''CODEX_PROVIDER="${CODEX_PROVIDER:-codex}"
SKILL_PLUGIN_DIR="${SKILL_PLUGIN_DIR:-${CLAUDE_PLUGIN_DIR:-}}"
''',
    '''CODEX_PROVIDER="${CODEX_PROVIDER:-codex}"
ENABLE_CODEX_SOLUTION_CHECKPOINTS="${ENABLE_CODEX_SOLUTION_CHECKPOINTS:-1}"
CODEX_MAX_CHECKPOINTS="${CODEX_MAX_CHECKPOINTS:-32}"
SKILL_PLUGIN_DIR="${SKILL_PLUGIN_DIR:-${CLAUDE_PLUGIN_DIR:-}}"
''',
)

replace_once(
    "tools/pilot_codex_smoke.sh",
    '''warn_if_json_metrics_lack_json_stdout() {
''',
    '''codex_solution_checkpoints_enabled() {
  local value
  value="$(lowercase "$ENABLE_CODEX_SOLUTION_CHECKPOINTS")"
  [[ "$value" == "1" || "$value" == "true" || "$value" == "yes" || "$value" == "on" ]] || return 1
  command_parts_include_json_flag
}

warn_if_json_metrics_lack_json_stdout() {
''',
)

replace_once(
    "tools/pilot_codex_smoke.sh",
    '''  local root_dir prompt_abs stdout_abs stderr_abs exit_abs
''',
    '''  local root_dir prompt_abs stdout_abs stderr_abs exit_abs command_json_abs timing_abs observer_ran
''',
)
replace_once(
    "tools/pilot_codex_smoke.sh",
    '''  exit_abs="${root_dir}/${out_dir}/codex_exit_code.txt"
''',
    '''  exit_abs="${root_dir}/${out_dir}/codex_exit_code.txt"
  command_json_abs="${root_dir}/${out_dir}/codex_command.json"
  timing_abs="${root_dir}/${out_dir}/codex_checkpoint_timing.json"
  observer_ran=false
''',
)

replace_once(
    "tools/pilot_codex_smoke.sh",
    '''  set +e
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
''',
    '''  set +e
  if codex_solution_checkpoints_enabled; then
    python - "$command_json_abs" "${CODEX_COMMAND_PARTS[@]}" <<'PY'
import json
import pathlib
import sys
pathlib.Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]) + "\\n", encoding="utf-8")
PY
    python -m benchmark_harness.codex_solution_latency_observer run \\
      --repo-root "$repo" \\
      --run-dir "${root_dir}/${out_dir}" \\
      --run-id "$RUN_ID" \\
      --task-slug "$TASK_SLUG" \\
      --arm-slug "$ARM_SLUG" \\
      --phase "$label" \\
      --prompt-file "$prompt_abs" \\
      --prompt-mode "$CODEX_PROMPT_MODE" \\
      --command-json "$command_json_abs" \\
      --hidden-evaluator-module "$HIDDEN_EVALUATOR_MODULE" \\
      --max-checkpoints "$CODEX_MAX_CHECKPOINTS"
    exit_code=$?
    observer_ran=true
  else
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
  fi
  set -e

  end_ns="$(python - <<'PY'
import time
print(time.time_ns())
PY
)"
  if [[ "$observer_ran" == "true" && -f "$timing_abs" ]]; then
    read -r start_ns end_ns < <(python - "$timing_abs" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data["process_start_ns"], data["process_end_ns"])
PY
)
  fi
  rm -f "$command_json_abs"
''',
)

replace_once(
    "tools/pilot_codex_smoke.sh",
    '''  if ! python -m benchmark_harness.agent_turn_trace summarize-codex \\
''',
    '''  if [[ ! -f "${root_dir}/${out_dir}/agent_turn_trace_summary.json" ]] && ! python -m benchmark_harness.agent_turn_trace summarize-codex \\
''',
)

# Documentation: explain the stronger claim and its limits.
docs = Path("docs/solution-latency.md")
text = docs.read_text(encoding="utf-8")
anchor = '''These fields sharpen ceremony and audit-tail analysis for Codex runs, but they do not
make functional first-green observable. A first source edit or first test is not proof
that the task was correct at that item. Continue to leave `first_functional_green_turn`
and related fields empty unless evaluator checkpoints were actually observed.
'''
replacement = '''These fields sharpen ceremony and audit-tail analysis for Codex runs. With Codex
workspace checkpoints enabled, the runner now captures every distinct workspace state
at completed provider-item boundaries, evaluates those snapshots after the agent exits,
and reports:

- `first_functional_green_item` and `items_after_first_functional_green`;
- `first_bench_ready_green_item` and `items_after_first_bench_ready_green`;
- `functional_to_bench_ready_items`, which separates useful artifact completion from the
  broader post-functional tail;
- `checkpoint_coverage_complete`, which must be true before claiming the first green
  item was observed exactly.

Snapshot evaluation happens after Codex exits so hidden checks do not steer the agent or
consume its context. The runner briefly pauses the Codex process group only while copying
a stable workspace snapshot and records that pause separately from evaluator time.

Do not call all work after functional green "waste" automatically. For E arms, work
between functional green and bench-ready green may be required verification or proof.
Use the two tails separately and treat incomplete checkpoint coverage as non-conclusive.
'''
if text.count(anchor) != 1:
    raise RuntimeError("docs/solution-latency.md: expected claim-boundary anchor")
docs.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")

score_docs = Path("docs/scorecard.md")
score_text = score_docs.read_text(encoding="utf-8")
score_text += '''\n## Codex first-green item fields\n\nWhen JSONL checkpoint observation is enabled, phase-prefixed scorecard columns include\n`first_functional_green_item`, `first_bench_ready_green_item`, both post-green item tails,\n`functional_to_bench_ready_items`, and checkpoint coverage. Only interpret an exact first\ngreen item when the corresponding `checkpoint_coverage_complete` field is true.\n'''
score_docs.write_text(score_text, encoding="utf-8")

from __future__ import annotations

from pathlib import Path

path = Path("benchmark_harness/agent_turn_trace.py")
text = path.read_text(encoding="utf-8")

old_inspection = '''    if any(
        marker in lowered
        for marker in (
            " sed ",
            " cat ",
            " head ",
            " tail ",
            " rg ",
            " grep ",
            " find ",
            " ls ",
            "pwd",
        )
    ):
        return "inspection"
'''
new_inspection = '''    stripped = lowered.lstrip()
    if stripped.startswith(("sed ", "cat ", "head ", "tail ", "rg ", "grep ", "find ", "ls ", "pwd")):
        return "inspection"
    if any(marker in lowered for marker in (" | sed ", " | cat ", " | head ", " | tail ", " | rg ", " | grep ")):
        return "inspection"
'''
if text.count(old_inspection) != 1:
    raise RuntimeError("inspection classifier patch target not found exactly once")
text = text.replace(old_inspection, new_inspection, 1)

old_provider_item = '''            recorder.record_provider_item(
                provider_event_type=provider_event_type,
                provider_item_type=item_type or "unknown",
                provider_item_lifecycle=lifecycle,
                provider_item_status=_codex_item_status(item),
                item_id=item_id,
                turn_index=item_turn_index,
                wall_seconds=wall_seconds,
                command_category=command_category,
                file_change_categories=file_categories,
                audit_artifacts_changed=audit_artifacts,
                paths_changed_count=path_count,
                notes=notes,
            )

            if item_type == "command_execution":
'''
new_provider_item = '''            if item_type in {"agent_message", "command_execution", "file_change", "todo_list"}:
                recorder.record_provider_item(
                    provider_event_type=provider_event_type,
                    provider_item_type=item_type,
                    provider_item_lifecycle=lifecycle,
                    provider_item_status=_codex_item_status(item),
                    item_id=item_id,
                    turn_index=item_turn_index,
                    wall_seconds=wall_seconds,
                    command_category=command_category,
                    file_change_categories=file_categories,
                    audit_artifacts_changed=audit_artifacts,
                    paths_changed_count=path_count,
                    notes=notes,
                )

            if item_type == "command_execution":
'''
if text.count(old_provider_item) != 1:
    raise RuntimeError("provider item filter patch target not found exactly once")
text = text.replace(old_provider_item, new_provider_item, 1)

path.write_text(text, encoding="utf-8")

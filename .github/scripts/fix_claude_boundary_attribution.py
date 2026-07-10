from __future__ import annotations

from pathlib import Path

path = Path("benchmark_harness/claude_solution_latency_observer.py")
text = path.read_text(encoding="utf-8")

old = '''    tool_use_to_name: dict[str, str] = {}
    tool_use_to_file_change: dict[str, bool] = {}
    permission_denials_total = 0
'''
new = '''    tool_use_to_name: dict[str, str] = {}
    tool_use_to_file_change: dict[str, bool] = {}
    unresolved_file_change_tool_uses: set[str] = set()
    permission_denials_total = 0
'''
if text.count(old) != 1:
    raise RuntimeError("tool-use state anchor not found exactly once")
text = text.replace(old, new, 1)

old = '''            if message_id and message_id != current_message_id:
                capture_current_state("assistant_boundary")
                complete_current_turn("assistant_boundary")
'''
new = '''            if message_id and message_id != current_message_id:
                # Do not snapshot at the next assistant boundary. By the time the
                # observer consumes that event, the next tool may already be running,
                # which can misattribute the next turn's workspace to the prior turn.
                # Completed file-changing tool results are the exact stream boundary.
                complete_current_turn("assistant_boundary")
'''
if text.count(old) != 1:
    raise RuntimeError("assistant boundary anchor not found exactly once")
text = text.replace(old, new, 1)

old = '''                    tool_use_to_name[tool_use_id] = tool_name
                    tool_use_to_file_change[tool_use_id] = shared._is_file_changing_tool(tool_name)
                    recorder.record_tool_use(
'''
new = '''                    tool_use_to_name[tool_use_id] = tool_name
                    tool_use_to_file_change[tool_use_id] = shared._is_file_changing_tool(tool_name)
                    if tool_use_to_file_change[tool_use_id]:
                        unresolved_file_change_tool_uses.add(tool_use_id)
                    recorder.record_tool_use(
'''
if text.count(old) != 1:
    raise RuntimeError("file-changing tool registration anchor not found exactly once")
text = text.replace(old, new, 1)

old = '''            for tool_use_id in shared._event_tool_result_ids(event):
                is_file_change = bool(tool_use_to_file_change.get(tool_use_id))
                file_change_detected = file_change_detected or is_file_change
'''
new = '''            for tool_use_id in shared._event_tool_result_ids(event):
                is_file_change = bool(tool_use_to_file_change.get(tool_use_id))
                if is_file_change:
                    unresolved_file_change_tool_uses.discard(tool_use_id)
                file_change_detected = file_change_detected or is_file_change
'''
if text.count(old) != 1:
    raise RuntimeError("tool-result anchor not found exactly once")
text = text.replace(old, new, 1)

old = '''        distinct_states_skipped=distinct_states_skipped,
        complete_boundary_stream=True,
    )
'''
new = '''        distinct_states_skipped=distinct_states_skipped,
        complete_boundary_stream=not unresolved_file_change_tool_uses,
    )
'''
if text.count(old) != 1:
    raise RuntimeError("coverage call anchor not found exactly once")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

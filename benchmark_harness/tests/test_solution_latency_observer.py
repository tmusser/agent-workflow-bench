from __future__ import annotations

import io
import json
import sys
import textwrap
from pathlib import Path

import pytest

from benchmark_harness.solution_latency_observer import (
    BenchmarkPythonEnvironment,
    evaluate_checkpoint_snapshot,
    is_bench_ready_green,
    resolve_benchmark_python,
    validate_benchmark_python,
)
import benchmark_harness.solution_latency_observer as solution_latency_observer


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _valid_skill_runtime_proof(run_id: str) -> str:
    return textwrap.dedent(
        f"""\
        # Skill Runtime Proof

        ## Run
        - Run ID: {run_id}
        - Arm: E-ai-engineering-skills
        - Task: 03-refund-grain
        - Repeat: 1

        ## Skill source
        - Repo URL: https://example.com/skills.git
        - Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567
        - Local path: /tmp/skills/ai-engineering-skills
        - Install command: cp -R /tmp/skills/ai-engineering-skills ~/.claude/skills/ai-engineering-skills
        - Install stdout/stderr path: benchmark-data/runs/{run_id}/install.txt

        ## Activation
        - Agent CLI: claude
        - Activation mechanism: plugin dir mounted before run
        - Prompt wrapper path: arms/E-ai-engineering-skills.md
        - Agent-visible skill files: ~/.claude/skills/ai-engineering-skills/README.md
        - Environment variables relevant to skill loading: CLAUDE_PLUGIN_DIR=/tmp/plugins

        ## Pre-run availability check
        - Command run: test -f ~/.claude/skills/ai-engineering-skills/README.md
        - Result: pass
        - Evidence path: benchmark-data/runs/{run_id}/skill_available.txt

        ## During-run evidence
        - Invocation evidence level: agent_declared
        - Did the agent mention or invoke the skill? yes
        - Evidence: benchmark-data/runs/{run_id}/stdout.txt
        - Notes: none

        ## Post-run caveat
        - Could a bad result be due to the skill not being loaded? no
        - Reviewer notes: validated locally
        """
    )


def test_e_arm_bench_ready_requires_skill_runtime_proof(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write(repo_root / "VERIFY.md", "Run VERIFY.sh and record the result.\n")

    ready, issues = is_bench_ready_green("E-ai-engineering-skills", repo_root, True)
    assert ready is False
    assert "missing SKILL_RUNTIME_PROOF.md" in issues

    proof = _valid_skill_runtime_proof("run-1")
    _write(repo_root / "SKILL_RUNTIME_PROOF.md", proof)

    ready, issues = is_bench_ready_green("E-ai-engineering-skills", repo_root, True)
    assert ready is True
    assert issues == []


def test_checkpoint_outputs_stay_outside_agent_repo(tmp_path: Path):
    repo_root = tmp_path / "repo"
    run_dir = tmp_path / "run"
    repo_root.mkdir()
    _write(repo_root / "VERIFY.md", "Run VERIFY.sh and record the result.\n")

    def verify_runner(snapshot_root: Path, output_path: Path) -> int:
        assert snapshot_root != repo_root
        _write(output_path, "verify ok\n")
        return 0

    def hidden_runner(snapshot_root: Path, output_path: Path) -> int:
        assert snapshot_root != repo_root
        _write(output_path, "hidden ok\n")
        return 0

    record = evaluate_checkpoint_snapshot(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id="run-1",
        task_slug="03-refund-grain",
        arm_slug="A-baseline",
        phase="initial",
        source="stream_json",
        checkpoint_index=1,
        turn=4,
        assistant_message_id="msg-1",
        hidden_evaluator_module="benchmark_harness.evaluators.task3_hidden_evaluator",
        wall_seconds=12.5,
        verify_runner=verify_runner,
        hidden_runner=hidden_runner,
    )

    assert record["functional_green"] is True
    assert record["bench_ready_green"] is True
    assert record["source"] == "stream_json"
    assert (run_dir / "solution_latency_checkpoints" / "checkpoint_0001" / "hidden_evaluator.txt").exists()
    assert not (repo_root / "hidden_evaluator.txt").exists()


def test_checkpoint_evaluators_use_configured_benchmark_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = tmp_path / "repo"
    run_dir = tmp_path / "run"
    python_dir = tmp_path / "benchmark-python" / "bin"
    python_dir.mkdir(parents=True)
    repo_root.mkdir()
    _write(repo_root / "state.txt", "green\n")
    _write(
        repo_root / "VERIFY.sh",
        "#!/usr/bin/env bash\nset -eu\nprintf '%s\\n' \"$(command -v python)\"\n",
    )
    (repo_root / "VERIFY.sh").chmod(0o755)
    configured = python_dir / "python"
    configured.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$0 $*\" >> \"$BENCHMARK_TEST_LOG\"\n"
        f"exec {sys.executable!s} \"$@\"\n",
        encoding="utf-8",
    )
    configured.chmod(0o755)
    log_path = tmp_path / "interpreter.log"
    monkeypatch.setenv("BENCHMARK_TEST_LOG", str(log_path))

    selected = resolve_benchmark_python(str(configured), environ={})
    record = evaluate_checkpoint_snapshot(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id="run-python-contract",
        task_slug="03-refund-grain",
        arm_slug="A-baseline",
        phase="initial",
        source="stream_json",
        checkpoint_index=1,
        turn=1,
        assistant_message_id="msg-1",
        hidden_evaluator_module="benchmark_harness.tests.fake_hidden_evaluator",
        wall_seconds=1.0,
        benchmark_python=selected,
    )

    assert record["functional_green"] is True
    assert record["evaluation_environment_valid"] is True
    assert record["benchmark_python"] == str(configured.resolve())
    assert str(configured.resolve()) in log_path.read_text(encoding="utf-8")
    assert str(configured.resolve()) == (run_dir / "solution_latency_checkpoints" / "checkpoint_0001" / "verification.txt").read_text(encoding="utf-8").strip()


def test_symlinked_configured_interpreter_path_is_preserved_for_execution(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write(repo_root / "VERIFY.sh", "#!/usr/bin/env bash\ncommand -v python\n")
    (repo_root / "VERIFY.sh").chmod(0o755)
    configured = tmp_path / "venv path" / "bin" / "python"
    configured.parent.mkdir(parents=True)
    configured.symlink_to(Path(sys.executable))

    selected = resolve_benchmark_python(configured)
    record = evaluate_checkpoint_snapshot(
        repo_root=repo_root,
        run_dir=tmp_path / "run",
        run_id="run-symlinked-python",
        task_slug="03-refund-grain",
        arm_slug="A-baseline",
        phase="initial",
        source="stream_json",
        checkpoint_index=1,
        turn=1,
        assistant_message_id=None,
        hidden_evaluator_module="benchmark_harness.tests.fake_hidden_evaluator",
        wall_seconds=1.0,
        benchmark_python=selected,
    )

    assert selected == configured.absolute()
    assert record["benchmark_python"] == str(configured.absolute())
    assert record["benchmark_python_realpath"] == str(Path(sys.executable).resolve())
    assert str(configured.absolute()) == (tmp_path / "run" / "solution_latency_checkpoints" / "checkpoint_0001" / "verification.txt").read_text(encoding="utf-8").strip()


def test_phase_environment_is_validated_once_and_reused_for_checkpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    environment = validate_benchmark_python(sys.executable)
    calls = 0

    def fail_if_revalidated(_: object) -> BenchmarkPythonEnvironment:
        nonlocal calls
        calls += 1
        raise AssertionError("checkpoint validation must reuse the phase environment")

    monkeypatch.setattr(solution_latency_observer, "validate_benchmark_python", fail_if_revalidated)
    for index in (1, 2, 3):
        record = evaluate_checkpoint_snapshot(
            repo_root=repo_root,
            run_dir=tmp_path / "run",
            run_id="run-one-validation",
            task_slug="03-refund-grain",
            arm_slug="A-baseline",
            phase="initial",
            source="stream_json",
            checkpoint_index=index,
            turn=index,
            assistant_message_id=None,
            hidden_evaluator_module="benchmark_harness.tests.fake_hidden_evaluator",
            wall_seconds=float(index),
            benchmark_python=environment.configured_path,
            environment=environment,
        )
        assert record["evaluation_environment_valid"] is True
    assert calls == 0


def test_invalid_benchmark_python_is_evaluation_environment_error(tmp_path: Path):
    invalid = tmp_path / "python-without-pytest"
    invalid.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$*\" == *\"import pytest\"* ]]; then exit 1; fi\n"
        f"exec {sys.executable!s} \"$@\"\n",
        encoding="utf-8",
    )
    invalid.chmod(0o755)

    metadata = validate_benchmark_python(invalid)

    assert metadata["evaluation_environment_valid"] is False
    assert any("pytest" in error for error in metadata["evaluation_environment_errors"])

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    record = evaluate_checkpoint_snapshot(
        repo_root=repo_root,
        run_dir=tmp_path / "run",
        run_id="run-invalid-environment",
        task_slug="03-refund-grain",
        arm_slug="A-baseline",
        phase="initial",
        source="stream_json",
        checkpoint_index=1,
        turn=1,
        assistant_message_id="msg-1",
        hidden_evaluator_module="benchmark_harness.tests.fake_hidden_evaluator",
        wall_seconds=1.0,
        benchmark_python=invalid,
    )
    assert record["functional_green"] is False
    assert record["verify_exit"] is None
    assert record["hidden_evaluator_exit"] is None
    assert record["evaluation_environment_valid"] is False
    assert any("evaluation_environment" in error for error in record["checkpoint_eval_errors"])

    rows = [json.loads(line) for line in (tmp_path / "run" / "turn_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["evaluation_environment_valid"] is False
    assert rows[0].get("first_functional_green_item") is None


def test_observer_error_does_not_relaunch_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = tmp_path / "repo"
    run_dir = tmp_path / "run"
    repo_root.mkdir()
    run_dir.mkdir()
    _write(repo_root / "prompt.md", "prompt\n")
    _write(repo_root / "VERIFY.md", "Run VERIFY.sh and record the result.\n")
    _write(run_dir / "claude_stdout.txt", "preserve stdout\n")
    _write(run_dir / "claude_stderr.txt", "preserve stderr\n")
    _write(run_dir / "claude_exit_code.txt", "7\n")

    calls = {"fallback": 0}

    def fake_stream_json_observer(**_: object) -> int:
        _write(run_dir / "claude_stdout.txt", "preserve stdout\n")
        _write(run_dir / "claude_stderr.txt", "preserve stderr\n")
        _write(run_dir / "claude_exit_code.txt", "7\n")
        raise RuntimeError("observer boom")

    def fake_subprocess_run(*_: object, **__: object) -> object:
        calls["fallback"] += 1
        raise AssertionError("fallback Claude run must not be invoked")

    monkeypatch.setattr(solution_latency_observer, "_run_stream_json_observer", fake_stream_json_observer)
    monkeypatch.setattr(
        solution_latency_observer,
        "validate_benchmark_python",
        lambda _: BenchmarkPythonEnvironment(
            configured_path=sys.executable,
            realpath=sys.executable,
            version="Python test",
            prefix=None,
            base_prefix=None,
            valid=True,
        ),
    )
    monkeypatch.setattr(solution_latency_observer.subprocess, "run", fake_subprocess_run)

    exit_code = solution_latency_observer.run(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id="run-1",
        task_slug="03-refund-grain",
        arm_slug="A-baseline",
        phase="initial",
        prompt_file=repo_root / "prompt.md",
        claude_cmd="claude",
        model="sonnet",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir=None,
        hidden_evaluator_module="benchmark_harness.evaluators.task3_hidden_evaluator",
        mode="stream_json",
    )

    assert exit_code == 1
    assert calls["fallback"] == 0
    assert (run_dir / "solution_latency_observer_error.txt").read_text(encoding="utf-8") == "RuntimeError: observer boom\n"
    assert (run_dir / "claude_stdout.txt").read_text(encoding="utf-8") == "preserve stdout\n"
    assert (run_dir / "claude_stderr.txt").read_text(encoding="utf-8") == "preserve stderr\n"
    assert (run_dir / "claude_exit_code.txt").read_text(encoding="utf-8") == "7\n"


def test_stream_json_observer_writes_normalized_trace_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = tmp_path / "repo"
    run_dir = tmp_path / "run"
    repo_root.mkdir()
    run_dir.mkdir()
    _write(repo_root / "VERIFY.md", "Run VERIFY.sh and record the result.\n")

    stdout_lines = [
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "id": "msg-1",
                    "content": [
                        {"type": "tool_use", "id": "toolu-1", "name": "Edit"},
                    ],
                },
            }
        )
        + "\n",
        json.dumps(
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "tool_use_id": "toolu-1"},
                    ]
                },
            }
        )
        + "\n",
        json.dumps({"type": "result", "num_turns": 1}) + "\n",
    ]

    class FakeProc:
        def __init__(self) -> None:
            self.stdout = io.StringIO("".join(stdout_lines))
            self.stderr = io.StringIO("observer stderr\n")
            self.returncode = 0

        def wait(self) -> int:
            return self.returncode

    def fake_popen(*_: object, **__: object) -> FakeProc:
        return FakeProc()

    def fake_checkpoint_current_turn(**_: object) -> dict[str, object]:
        return {
            "run_id": "run-1",
            "task_slug": "03-refund-grain",
            "arm_slug": "A-baseline",
            "phase": "initial",
            "source": "stream_json",
            "checkpoint_index": 1,
            "turn": 1,
            "assistant_message_id": "msg-1",
            "wall_seconds": 4.0,
            "verify_exit": 0,
            "hidden_evaluator_exit": 0,
                "functional_green": True,
                "bench_ready_green": True,
                "evaluation_environment_valid": True,
                "evaluation_environment_errors": [],
                "permission_denials_delta": 0,
            "checkpoint_eval_errors": [],
        }

    monkeypatch.setattr(solution_latency_observer.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(solution_latency_observer, "_checkpoint_current_turn", fake_checkpoint_current_turn)

    exit_code = solution_latency_observer._run_stream_json_observer(
        repo_root=repo_root,
        run_dir=run_dir,
        run_id="run-1",
        task_slug="03-refund-grain",
        arm_slug="A-baseline",
        phase="initial",
        prompt_text="prompt\n",
        claude_cmd="claude",
        model="sonnet",
        effort="low",
        max_turns=20,
        permission_mode="acceptEdits",
        plugin_dir=None,
        hidden_evaluator_module="benchmark_harness.evaluators.task3_hidden_evaluator",
    )

    rows = [json.loads(line) for line in (run_dir / "agent_turn_trace.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = json.loads((run_dir / "agent_turn_trace_summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert [row["event_kind"] for row in rows] == [
        "turn_started",
        "assistant_message",
        "tool_use",
        "file_change_observed",
        "tool_result",
        "turn_completed",
        "checkpoint",
        "run_result",
    ]
    assert rows[2]["tool_name"] == "Edit"
    assert rows[2]["file_changing_tool"] is True
    assert summary["trace_source"] == "claude_stream_json"
    assert summary["trace_fidelity"] == "turn_event"
    assert summary["turns_observed"] == 1
    assert summary["assistant_messages_observed"] == 1
    assert summary["tool_uses_observed"] == 1
    assert summary["file_changing_tool_uses_observed"] == 1
    assert summary["checkpoints_observed"] == 1
    assert summary["solution_latency_observable"] is True

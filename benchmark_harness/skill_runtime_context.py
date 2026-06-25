from __future__ import annotations

import argparse
import re
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
METADATA_FIELDS = ("Repo URL", "Pinned commit SHA", "Local path", "Install command")


def _parse_pinned_skill_repo(metadata_path: Path) -> dict[str, str]:
    text = metadata_path.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for line in text.splitlines():
        for field in METADATA_FIELDS:
            prefix = f"- {field}:"
            if line.startswith(prefix):
                values[field] = line[len(prefix):].strip()

    missing = [field for field in METADATA_FIELDS if not values.get(field)]
    if missing:
        raise ValueError(f"missing required pinned skill metadata fields: {', '.join(missing)}")

    sha = values["Pinned commit SHA"]
    if not SHA_RE.fullmatch(sha):
        raise ValueError("Pinned commit SHA in PINNED_SKILL_REPO.md must be a 40-character lowercase hex SHA")

    return values


def build_skill_runtime_context(
    *,
    workspace_root: Path,
    plugin_dir: str,
    task_slug: str,
    arm_slug: str,
    run_id: str,
) -> Path:
    workspace_root = workspace_root.resolve()
    plugin_dir_path = Path(plugin_dir).expanduser().resolve()
    metadata_path = plugin_dir_path / "PINNED_SKILL_REPO.md"
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"missing pinned skill metadata: {metadata_path}. "
            "Run ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins first."
        )

    metadata = _parse_pinned_skill_repo(metadata_path)
    context_path = workspace_root / ".benchmark" / "SKILL_RUNTIME_CONTEXT.md"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(
        "\n".join(
            [
                "# Skill Runtime Context",
                "",
                f"- Repo URL: {metadata['Repo URL']}",
                f"- Pinned commit SHA: {metadata['Pinned commit SHA']}",
                f"- Local plugin path: {metadata['Local path']}",
                f"- Agent-visible plugin path: {plugin_dir}",
                "- Pin command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins",
                f"- Pre-run availability check command: test -f {metadata_path}",
                "- Pre-run availability check result: available",
                f"- Pre-run availability evidence path: {context_path}",
                f"- Task slug: {task_slug}",
                f"- Arm slug: {arm_slug}",
                f"- Run ID: {run_id}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return context_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write .benchmark/SKILL_RUNTIME_CONTEXT.md for an E-arm run.")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--plugin-dir", required=True)
    parser.add_argument("--task-slug", required=True)
    parser.add_argument("--arm-slug", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)

    try:
        path = build_skill_runtime_context(
            workspace_root=Path(args.workspace_root),
            plugin_dir=args.plugin_dir,
            task_slug=args.task_slug,
            arm_slug=args.arm_slug,
            run_id=args.run_id,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

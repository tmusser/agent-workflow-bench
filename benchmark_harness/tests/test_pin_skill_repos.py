from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def _write_fake_git(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

repo_dir=""
if [[ "${1:-}" == "-C" ]]; then
  repo_dir="$2"
  shift 2
fi

cmd="${1:-}"
case "$cmd" in
  clone)
    url="${2:-}"
    dest="${3:-}"
    mkdir -p "$dest/.git"
    printf '%s\n' "$url" > "$dest/.git/url"
    ;;
  fetch|checkout|pull)
    exit 0
    ;;
  rev-parse)
    case "$(basename "$repo_dir")" in
      matt-pocock-skills) printf '%s\n' '1111111111111111111111111111111111111111' ;;
      addyosmani-agent-skills) printf '%s\n' '2222222222222222222222222222222222222222' ;;
      ponytail) printf '%s\n' '3333333333333333333333333333333333333333' ;;
      ai-engineering-skills) printf '%s\n' '0123456789abcdef0123456789abcdef01234567' ;;
      *) printf '%s\n' '4444444444444444444444444444444444444444' ;;
    esac
    ;;
  *)
    printf 'fake git: unsupported command %s\\n' "$cmd" >&2
    exit 1
    ;;
esac
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_pin_skill_repos_writes_pinned_skill_metadata(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_git(fake_bin / "git")

    script = Path(__file__).resolve().parents[1] / "scripts" / "pin_skill_repos.sh"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["AI_ENGINEERING_SKILLS_REPO_URL"] = "https://example.com/ai-engineering-skills.git"

    subprocess.run(
        ["bash", str(script), "local_plugins"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    metadata = tmp_path / "local_plugins" / "ai-engineering-skills" / "PINNED_SKILL_REPO.md"

    assert metadata.exists()
    text = metadata.read_text(encoding="utf-8")
    assert "- Repo URL: https://example.com/ai-engineering-skills.git" in text
    assert "- Pinned commit SHA: 0123456789abcdef0123456789abcdef01234567" in text
    assert "- Local path: local_plugins/ai-engineering-skills" in text
    assert "- Install command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins" in text
    assert re.search(r"(?m)^- Pinned commit SHA: [0-9a-f]{40}$", text)

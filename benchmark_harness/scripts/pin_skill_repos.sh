#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-benchmark-data/skill-repos}"
mkdir -p "$OUT_DIR"
DEFAULT_AI_ENGINEERING_SKILLS_OWNER="$(printf '%s%s' tm usser)"
AI_ENGINEERING_SKILLS_REPO_URL="${AI_ENGINEERING_SKILLS_REPO_URL:-https://github.com/${DEFAULT_AI_ENGINEERING_SKILLS_OWNER}/ai-engineering-skills.git}"

clone_or_update() {
  local name="$1"
  local url="$2"
  local dest="$OUT_DIR/$name"
  if [ ! -d "$dest/.git" ]; then
    git clone "$url" "$dest"
  else
    git -C "$dest" fetch --all --prune
    git -C "$dest" checkout main || git -C "$dest" checkout master
    git -C "$dest" pull --ff-only || true
  fi
  local sha
  sha="$(git -C "$dest" rev-parse HEAD)"
  if [ "$name" = "ai-engineering-skills" ]; then
    cat > "$dest/PINNED_SKILL_REPO.md" <<EOF
# Pinned Skill Repo

- Repo URL: $url
- Pinned commit SHA: $sha
- Local path: $dest
- Install command: ./benchmark_harness/scripts/pin_skill_repos.sh local_plugins
EOF
  fi
  echo "$name,$url,$sha,$dest"
}

{
  echo "name,url,commit_sha,local_path"
  clone_or_update "matt-pocock-skills" "https://github.com/mattpocock/skills.git"
  clone_or_update "addyosmani-agent-skills" "https://github.com/addyosmani/agent-skills.git"
  clone_or_update "ponytail" "https://github.com/DietrichGebert/ponytail.git"
  clone_or_update "ai-engineering-skills" "$AI_ENGINEERING_SKILLS_REPO_URL"
} > "$OUT_DIR/pinned_skill_repos.csv"

echo "Wrote $OUT_DIR/pinned_skill_repos.csv"

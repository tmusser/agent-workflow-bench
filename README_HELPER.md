# benchmark-v04.2-helper-v6

Drop this into `benchmark-v04.2-pilot` after unzipping the v0.4.2 pilot package.

This version fixes the Claude write doctor false-negative by running the write smoke test inside a git-initialized temporary repo, matching the real benchmark workspaces.

```bash
unzip -o ~/Downloads/benchmark-v04.2-helper-v6.zip
chmod +x tools/pilot_smoke.sh
./tools/pilot_smoke.sh doctor
CLAUDE_MAX_TURNS=30 ./tools/pilot_smoke.sh auto-a-r1
```

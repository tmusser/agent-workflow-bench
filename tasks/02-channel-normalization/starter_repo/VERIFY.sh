#!/usr/bin/env bash
set -euo pipefail

python scripts/reproduce_channel_bug.py
pytest -q

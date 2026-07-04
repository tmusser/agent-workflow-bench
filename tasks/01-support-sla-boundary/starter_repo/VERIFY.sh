#!/usr/bin/env bash
set -euo pipefail

python scripts/reproduce_sla_bug.py
pytest -q

#!/usr/bin/env bash
set -euo pipefail

python scripts/reproduce_churn_bug.py
pytest -q

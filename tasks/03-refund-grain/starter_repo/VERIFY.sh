#!/usr/bin/env bash
set -euo pipefail

python scripts/reproduce_refund_bug.py
pytest -q

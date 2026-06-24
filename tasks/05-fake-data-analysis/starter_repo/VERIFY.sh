#!/usr/bin/env bash
set -euo pipefail

python scripts/reproduce_fake_lift.py
pytest -q

#!/usr/bin/env bash
set -euo pipefail

python scripts/generate_fake_activation_data.py --seed 42 --out fixtures
python -m pytest -q
python scripts/run_activation_report.py \
  --data-dir fixtures \
  --definition v2 \
  --month 2026-01 \
  --out outputs/activation_v2_public.csv

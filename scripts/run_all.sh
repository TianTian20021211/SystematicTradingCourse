#!/usr/bin/env bash
# Reproduce the data layer and the A/B baselines from the raw Bloomberg CSV.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
RAW="data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv"

if [[ ! -f "$RAW" ]]; then
  echo "Missing raw CSV: $RAW"
  echo "See data/raw/README.md for the checksum and placement instructions."
  exit 1
fi

echo "== Install dependencies =="
"$PYTHON" -m pip install -r requirements.txt

echo "== Run tests (synthetic fixtures; no raw data needed) =="
"$PYTHON" -m pytest -q

echo "== Execute notebooks =="
jupyter nbconvert --execute --to notebook --inplace notebooks/00_data_audit.ipynb
jupyter nbconvert --execute --to notebook --inplace notebooks/01_panel_build.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/02_carry.ipynb
# 03 is reserved for idea C (mean reversion); that branch is not merged yet.
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/04_a_diagnose.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/05_b_pretest.ipynb

echo "== Remove volatile notebook execution timestamps =="
"$PYTHON" scripts/clean_notebook_metadata.py \
  notebooks/00_data_audit.ipynb notebooks/01_panel_build.ipynb \
  notebooks/02_carry.ipynb notebooks/04_a_diagnose.ipynb \
  notebooks/05_b_pretest.ipynb

echo "== Processed panels =="
ls -lh data/processed/*.parquet
echo "Done."

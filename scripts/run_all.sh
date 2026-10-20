#!/usr/bin/env bash
# Reproduce the data layer and the four per-idea notebooks from the raw CSV.
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
  --ExecutePreprocessor.timeout=900 notebooks/10_idea_a_carry.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/11_idea_b_adjacent_carry.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=1800 notebooks/12_idea_c_mean_reversion.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/13_idea_d_curve_momentum.ipynb

echo "== Cross-strategy comparison table (optional utility) =="
"$PYTHON" scripts/run_v2_rerun.py \
  --strategies a,d,c,c_ols,c_kalman,b --force

echo "== Remove volatile notebook execution timestamps =="
"$PYTHON" scripts/clean_notebook_metadata.py \
  notebooks/00_data_audit.ipynb notebooks/01_panel_build.ipynb \
  notebooks/10_idea_a_carry.ipynb notebooks/11_idea_b_adjacent_carry.ipynb \
  notebooks/12_idea_c_mean_reversion.ipynb notebooks/13_idea_d_curve_momentum.ipynb

echo "== Processed panels =="
ls -lh data/processed/*.parquet
echo "Done."

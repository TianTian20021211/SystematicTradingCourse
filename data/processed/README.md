# Generated panels (local only)

This directory holds the parquet panels produced by
`notebooks/01_panel_build.ipynb`. They are **gitignored**; only this README and
`.gitkeep` are tracked.

## Files and shapes

| File | Rows | Columns | Content |
|---|---:|---:|---|
| `rank.parquet` | 1,013,664 | 23 | date × commodity × rank, contract identity + flags |
| `contract.parquet` | 950,626 | 29 | date × real contract, full life + expiry proxy |
| `returns.parquet` | 1,013,664 | 24 | contract returns mapped to rank slots |
| `pairs.parquet` | 236,186 | 29 | main pair (nearest two eligible adjacent contracts) |
| `spread.parquet` | 236,186 | 30 | main pair dollar/log/pct spreads |
| `universe.parquet` | 236,186 | 56 | trailing liquidity + threshold booleans |
| `episodes.parquet` | 6,664 | 17 | fixed-contract pair episodes |
| `adjacent_pairs.parquet` | 610,801 | 29 | all eligible adjacent pairs (robustness) |
| `adjacent_spread.parquet` | 610,801 | 30 | all adjacent pair spreads |
| `backtest_pairs.parquet` | 236,385 | 29 | K=5 ex-ante main pair for the backtest |
| `backtest_spread.parquet` | 236,385 | 30 | K=5 main pair dollar/log/pct spreads |

Schemas are documented in `docs/data_dictionary.md`.

## How to regenerate

From the repo root, with the raw CSV at
`data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv`:

```bash
bash scripts/run_all.sh
```

or:

```bash
jupyter nbconvert --execute --to notebook --inplace notebooks/01_panel_build.ipynb
```

## Notes

- Do not commit these files: the repo is public and the panels are derived from
  licensed Bloomberg data.
- The executed notebook is the reproducible record; the parquet files are a
  local cache.
- If a file is missing, rerun `01_panel_build.ipynb`; do not hand-edit parquet.

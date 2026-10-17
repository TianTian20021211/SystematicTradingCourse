# Raw Data (local only)

This directory is intentionally **gitignored**. The repository is public and
the Bloomberg extract is licensed; do not commit it.

## Files

| File | Size | SHA-256 |
|---|---|---|
| `bloomberg_commodity_bulk_tickers_1986_2026.csv` | 20,361,776 bytes | `045293fed420a82a3f85e592835eac6dba70fce0898b0fe8ddf40561e3f37771` |
| `bloomberg_commodity_bulk_tickers_1986_2026.xlsx` | 26,361,400 bytes | `de9b7a73577c8f52096eac80aec3f0b0427a7343a7368669c921ae9a392d5b42` |

The CSV is the primary analysis source. The XLSX is the original Bloomberg
workbook and the source of `Universe_Details`; it is not needed to run the
notebooks because `data/metadata/commodities.csv` is committed.

## How to obtain

Ask the repo owner (Tian) for the CSV through a private channel. Place it at:

```text
data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv
```

Verify:

```bash
shasum -a 256 data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv
```

Expected value is in the table above.

## Provenance

- Bloomberg Terminal bulk download: 24 commodity markets × 4 nearby generic
  ranks (M1–M4) × 4 fields, daily 1986-01-01 to 2026-10-13.
- Fields: `PX_SETTLE`, `PX_VOLUME`, `OPEN_INT`, `FUT_CUR_GEN_TICKER`.
- The data is not covered by any code license in this repository.

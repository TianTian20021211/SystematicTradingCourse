"""Project-wide constants and paths.

All paths are resolved from the repository root, independent of the current
working directory. Importing this module does not create directories.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
METADATA_DIR = ROOT / "data" / "metadata"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "output"

RAW_CSV = Path(
    os.environ.get(
        "BLOOMBERG_CSV",
        RAW_DIR / "bloomberg_commodity_bulk_tickers_1986_2026.csv",
    )
)
RAW_XLSX = RAW_DIR / "bloomberg_commodity_bulk_tickers_1986_2026.xlsx"
COMMODITIES_CSV = METADATA_DIR / "commodities.csv"

START_DATE = "1986-01-01"
END_DATE = "2026-10-13"

# Pair eligibility (locked; see docs/decisions.md D-002)
D = 10
DELIVERY_BUFFER_K = 5
D_ROBUSTNESS = (5, 20)

# Liquidity diagnostics (threshold not chosen yet; see D-004)
LIQUIDITY_THRESHOLDS = (1_000, 5_000, 10_000, 20_000)
LIQUIDITY_WINDOW = 252
LIQUIDITY_MIN_OBS = 60

# Contract-code parsing
MONTH_CODES = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}
MONTH_NAMES = {v: k for k, v in MONTH_CODES.items()}

FIELDS = ("PX_SETTLE", "PX_VOLUME", "OPEN_INT", "FUT_CUR_GEN_TICKER")
N_HEADER_ROWS = 6
N_TICKERS = 96
N_COLUMNS = 385  # date + 96 * 4

NEGATIVE_PRICE_EVENT = {"root": "CL", "date": "2020-04-20", "settle": -37.63}

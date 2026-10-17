"""Generate a tiny synthetic Bloomberg-wide CSV for tests.

This is NOT Bloomberg data. It mimics the six-header-row layout, includes a
simultaneous four-rank roll, missing values, a `.NA.` contract code, a negative
settlement, and an all-blank holiday row.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).with_name("synthetic_wide.csv")

TICKERS = [
    "CL1 Comdty", "CL2 Comdty", "CL3 Comdty", "CL4 Comdty",
    "C 1 Comdty", "C 2 Comdty", "C 3 Comdty", "C 4 Comdty",
]

DATES = [
    date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 6),
    date(2020, 1, 7), date(2020, 1, 8), date(2020, 1, 9),
    date(2020, 1, 10), date(2020, 1, 13), date(2020, 1, 14),
    date(2020, 1, 15), date(2020, 1, 16), date(2020, 1, 17),
    date(2020, 1, 20),  # all-blank holiday row
]

# Roll at row index 5 (2020-01-09): all four ranks shift by one contract.
CL_CONTRACTS = [
    ["CLG20"] * 5 + ["CLH20"] * 8,
    ["CLH20"] * 5 + ["CLJ20"] * 8,
    ["CLJ20"] * 5 + ["CLK20"] * 8,
    ["CLK20"] * 5 + ["CLM20"] * 8,
]
C_CONTRACTS = [
    ["C H20"] * 5 + ["C K20"] * 8,
    ["C K20"] * 5 + ["C N20"] * 8,
    ["C N20"] * 5 + ["C U20"] * 8,
    ["C U20"] * 5 + ["C Z20"] * 8,
]
CONTRACTS = CL_CONTRACTS + C_CONTRACTS

CL_START = [60.0, 61.0, 62.0, 63.0]
CL_AFTER = [61.5, 62.5, 63.5, 64.5]
C_START = [3.80, 3.90, 4.00, 4.10]
C_AFTER = [3.95, 4.05, 4.15, 4.25]


def main() -> None:
    rows: list[list[str]] = []
    ncols = 1 + 4 * len(TICKERS)

    rows.append(["Start Date", "1/1/2020"] + [""] * (ncols - 2))
    rows.append(["End Date"] + [""] * (ncols - 1))
    rows.append([""] * ncols)

    ticker_row = [""] * ncols
    for index, ticker in enumerate(TICKERS):
        ticker_row[1 + 4 * index] = ticker
    rows.append(ticker_row)

    field_row = [""] * ncols
    for index in range(len(TICKERS)):
        field_row[1 + 4 * index : 1 + 4 * index + 4] = [
            "Settlement Price", "Volume", "Open Interest",
            "Current Generic Futures Ticker",
        ]
    rows.append(field_row)

    rows.append(["Dates"] + ["PX_SETTLE", "PX_VOLUME", "OPEN_INT", "FUT_CUR_GEN_TICKER"] * len(TICKERS))

    for day_index, day in enumerate(DATES):
        row = [day.strftime("%m/%d/%Y")] + [""] * (ncols - 1)
        if day == date(2020, 1, 20):
            rows.append(row)
            continue

        for ticker_index, contracts in enumerate(CONTRACTS):
            offset = 1 + 4 * ticker_index
            is_cl = ticker_index < 4
            rank = ticker_index % 4
            if is_cl:
                base = CL_START[rank] if day_index < 5 else CL_AFTER[rank]
                settle = base + 0.10 * day_index
            else:
                base = C_START[rank] if day_index < 5 else C_AFTER[rank]
                settle = base + 0.01 * day_index

            contract = contracts[day_index]
            volume = 1000 + 100 * rank + day_index
            oi = 5000 + 100 * rank + day_index

            # Missing settle/volume/OI for CL2 on 2020-01-10.
            if ticker_index == 1 and day_index == 6:
                settle = None
                volume = None
                oi = None
            # Negative settlement for CL1 on 2020-01-14.
            if ticker_index == 0 and day_index == 8:
                settle = -1.0
            # Settle present but contract code missing for C1 on 2020-01-15.
            if ticker_index == 4 and day_index == 9:
                contract = ".NA."

            row[offset] = "" if settle is None else f"{settle:.2f}"
            row[offset + 1] = "" if volume is None else str(volume)
            row[offset + 2] = "" if oi is None else str(oi)
            row[offset + 3] = contract

        rows.append(row)

    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


if __name__ == "__main__":
    main()

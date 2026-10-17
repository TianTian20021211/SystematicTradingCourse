"""Load and normalize the Bloomberg bulk CSV.

The raw file is wide: 96 generic tickers, each with four columns
(settle, volume, open interest, contract code). This module turns it into a
long rank panel while preserving enough raw information for auditing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
import re
from typing import Iterable

import numpy as np
import pandas as pd

from . import config


@dataclass(frozen=True)
class ContractId:
    """Parsed delivery month of a futures contract."""

    year: int
    month: int

    @property
    def expiry_id(self) -> int:
        return self.year * 12 + self.month - 1


@dataclass
class RawWide:
    """Raw wide CSV plus its header metadata."""

    data: pd.DataFrame
    tickers: list[str]
    fields: list[str]
    path: Path


_TICKER_RE = re.compile(r"^([A-Z]+)\s*(\d)\s+Comdty$")
_CONTRACT_RE = re.compile(r"^([FGHJKMNQUVXZ])(\d{1,2})$")


def parse_ticker(ticker: str) -> tuple[str, int]:
    """Return (root, rank) from a Bloomberg generic ticker.

    Examples: ``CL1 Comdty`` -> (``CL``, 1); ``C 1 Comdty`` -> (``C``, 1).
    """

    match = _TICKER_RE.match(str(ticker).strip())
    if not match:
        raise ValueError(f"Unrecognized generic ticker: {ticker!r}")
    return match.group(1), int(match.group(2))


def normalize_contract_code(code: object) -> str | None:
    """Normalize a raw contract code; return None for missing sentinels."""

    if not isinstance(code, str):
        return None
    value = code.strip().replace(" ", "").upper()
    if value in {"", ".NA.", "NAN", "NONE", "NULL"}:
        return None
    return value


def _resolve_year(token: str, as_of: date | pd.Timestamp | None = None) -> int:
    """Resolve a 1- or 2-digit contract year.

    Two-digit years use the 1986–2026 sample convention: >=50 -> 1900s,
    otherwise 2000s. One-digit years appear from 2022-09 onward; use the
    observation date to choose the nearest plausible future delivery year.
    """

    if len(token) == 2:
        value = int(token)
        return 1900 + value if value >= 50 else 2000 + value

    digit = int(token)
    if as_of is None:
        return 2020 + digit

    as_of_year = int(as_of.year)
    candidates = [year for year in range(2000, 2040) if year % 10 == digit]
    future = [year for year in candidates if year >= as_of_year]
    return min(future) if future else max(candidates)


def parse_contract_code(
    code: object,
    root: str,
    as_of: date | pd.Timestamp | None = None,
) -> ContractId | None:
    """Parse ``<root><month><year>`` into a ContractId.

    Returns None for missing/malformed codes or a root mismatch.
    """

    normalized = normalize_contract_code(code)
    if normalized is None or not normalized.startswith(root):
        return None

    rest = normalized[len(root) :]
    match = _CONTRACT_RE.match(rest)
    if not match:
        return None

    month_code, year_token = match.groups()
    month = config.MONTH_CODES[month_code]
    year = _resolve_year(year_token, as_of)
    return ContractId(year=year, month=month)


@lru_cache(maxsize=None)
def _parse_cached(code: str, root: str, as_of_year: int) -> ContractId | None:
    return parse_contract_code(code, root, date(as_of_year, 1, 1))


def read_raw_wide(
    path: str | Path | None = None,
    expected_tickers: int | None = config.N_TICKERS,
) -> RawWide:
    """Read the six-header-row Bloomberg CSV into a RawWide object.

    ``expected_tickers`` defaults to the 96-series production file. Tests may
    pass a smaller number for synthetic fixtures.
    """

    path = Path(path or config.RAW_CSV)
    if not path.exists():
        raise FileNotFoundError(
            f"Raw file not found: {path}. "
            "Place the Bloomberg CSV in data/raw/ or set BLOOMBERG_CSV."
        )

    header = pd.read_csv(
        path, header=None, nrows=config.N_HEADER_ROWS, dtype=str,
        keep_default_na=False,
    )
    if header.shape[0] != config.N_HEADER_ROWS:
        raise ValueError(f"Expected {config.N_HEADER_ROWS} header rows, got {header.shape[0]}")

    tickers = [str(value).strip() for value in header.iloc[3, 1::4].tolist()]
    fields = [str(value).strip() for value in header.iloc[5, 1:].tolist()]

    if expected_tickers is not None and len(tickers) != expected_tickers:
        raise ValueError(f"Expected {expected_tickers} tickers, got {len(tickers)}")
    expected_fields = list(config.FIELDS) * len(tickers)
    if fields != expected_fields:
        raise ValueError("Unexpected field layout in row 6 of the raw CSV")

    data = pd.read_csv(
        path, header=None, skiprows=config.N_HEADER_ROWS, dtype=str,
        keep_default_na=False,
    )
    expected_columns = 1 + 4 * len(tickers)
    if data.shape[1] != expected_columns:
        raise ValueError(f"Expected {expected_columns} columns, got {data.shape[1]}")

    dates = pd.to_datetime(data.iloc[:, 0].str.strip(), format="%m/%d/%Y", errors="coerce")
    if dates.isna().any():
        bad = int(dates.isna().sum())
        raise ValueError(f"Could not parse {bad} dates in the raw CSV")
    if dates.duplicated().any():
        raise ValueError("Raw CSV contains duplicate dates")

    return RawWide(data=data, tickers=tickers, fields=fields, path=path)


def read_commodity_metadata(path: str | Path | None = None) -> pd.DataFrame:
    """Read the committed 24-row commodity metadata table."""

    path = Path(path or config.COMMODITIES_CSV)
    metadata = pd.read_csv(path, dtype=str).fillna("")
    required = {"root", "commodity", "sector", "exchange"}
    missing = required.difference(metadata.columns)
    if missing:
        raise ValueError(f"Commodity metadata missing columns: {sorted(missing)}")

    for column in ["root", "commodity", "sector", "exchange"]:
        metadata[column] = metadata[column].str.strip()
    if metadata["root"].duplicated().any():
        raise ValueError("Commodity metadata has duplicate roots")
    if len(metadata) != 24:
        raise ValueError(f"Expected 24 commodities, got {len(metadata)}")
    return metadata


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.str.strip().replace("", np.nan), errors="coerce")


def _consecutive_true(series: pd.Series) -> pd.Series:
    """Length of the current run of True values, reset on False."""

    return series.groupby((~series).cumsum()).cumsum()


def build_rank_panel(
    raw: RawWide,
    metadata: pd.DataFrame,
) -> pd.DataFrame:
    """Build the long ``date × commodity × rank`` panel with audit flags."""

    dates = pd.to_datetime(raw.data.iloc[:, 0].str.strip(), format="%m/%d/%Y", errors="coerce")
    meta = metadata.set_index("root")[["commodity", "sector", "exchange"]]

    frames: list[pd.DataFrame] = []
    for index, ticker in enumerate(raw.tickers):
        base = 1 + 4 * index
        frame = raw.data.iloc[:, [0, base, base + 1, base + 2, base + 3]].copy()
        frame.columns = ["date", "settle", "volume", "open_interest", "contract_code_raw"]
        frame["date"] = dates.to_numpy()
        frame["ticker"] = ticker
        frame["root"], frame["rank"] = parse_ticker(ticker)

        for column in ["settle", "volume", "open_interest"]:
            frame[column] = _numeric(frame[column])
        frame["contract_code"] = frame["contract_code_raw"].map(normalize_contract_code)

        root = frame["root"].iloc[0]
        parsed = [
            _parse_cached(code, root, int(day.year)) if isinstance(code, str) else None
            for code, day in zip(frame["contract_code"], frame["date"])
        ]
        frame["delivery_year"] = [item.year if item else np.nan for item in parsed]
        frame["delivery_month"] = [item.month if item else np.nan for item in parsed]
        frame["expiry_id"] = [item.expiry_id if item else np.nan for item in parsed]
        frames.append(frame)

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.join(meta, on="root", rsuffix="_meta")
    if panel["commodity"].isna().any():
        missing = sorted(panel.loc[panel["commodity"].isna(), "root"].unique())
        raise ValueError(f"Missing commodity metadata for roots: {missing}")

    panel["parse_failed"] = panel["contract_code"].notna() & panel["expiry_id"].isna()
    panel["code_missing"] = panel["settle"].notna() & panel["contract_code"].isna()
    panel["volume_missing"] = panel["volume"].isna()
    panel["oi_missing"] = panel["open_interest"].isna()
    panel["negative_price"] = panel["settle"].lt(0).fillna(False)

    panel = panel.sort_values(["root", "rank", "date"]).reset_index(drop=True)
    previous_code = panel.groupby(["root", "rank"], sort=False)["contract_code"].shift()
    previous_settle = panel.groupby(["root", "rank"], sort=False)["settle"].shift()

    panel["is_roll"] = (
        panel["contract_code"].notna()
        & previous_code.notna()
        & panel["contract_code"].ne(previous_code)
    )
    panel["stale"] = (
        panel["settle"].notna()
        & previous_settle.notna()
        & panel["settle"].eq(previous_settle)
    )
    panel["stale_run"] = (
        panel.groupby(["root", "rank"], sort=False)["stale"]
        .transform(_consecutive_true)
        .astype("int64")
    )

    valid = (
        panel["settle"].notna()
        | panel["volume"].notna()
        | panel["open_interest"].notna()
        | panel["contract_code"].notna()
    )
    dates_with_data = panel.loc[valid, "date"].unique()
    panel = panel.loc[panel["date"].isin(dates_with_data)].copy()

    panel = panel.sort_values(["date", "root", "rank"]).reset_index(drop=True)

    columns = [
        "date", "root", "commodity", "sector", "exchange", "rank", "ticker",
        "contract_code", "contract_code_raw", "delivery_year", "delivery_month",
        "expiry_id", "settle", "volume", "open_interest", "is_roll", "stale",
        "stale_run", "code_missing", "parse_failed", "volume_missing",
        "oi_missing", "negative_price",
    ]
    return panel[columns]


def load_rank_panel(
    raw_csv: str | Path | None = None,
    metadata_csv: str | Path | None = None,
) -> pd.DataFrame:
    """Convenience wrapper: read raw + metadata and build the rank panel."""

    raw = read_raw_wide(raw_csv)
    metadata = read_commodity_metadata(metadata_csv)
    return build_rank_panel(raw, metadata)

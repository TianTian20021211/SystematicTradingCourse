"""Panel construction: contract, return, spread, and universe layers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config, curve


CONTRACT_CALENDAR_COLUMNS = [
    "first_date",
    "last_date",
    "last_trade_proxy",
    "delivery_month_start",
    "delivery_month_end",
    "days_to_last_trading",
    "days_to_delivery_start",
    "in_delivery_month",
    "is_censored",
]


def build_contract_panel(rank_panel: pd.DataFrame) -> pd.DataFrame:
    """Build one row per date × real contract, with contract-calendar fields."""

    panel = rank_panel.loc[rank_panel["contract_code"].notna()].copy()
    panel["contract_key"] = panel["root"] + "_" + panel["contract_code"]

    duplicates = panel.duplicated(["date", "root", "contract_code"])
    if duplicates.any():
        raise ValueError(f"Duplicate contract-date rows: {int(duplicates.sum())}")

    panel = curve.add_contract_calendar(panel)

    columns = [
        "date", "root", "commodity", "sector", "exchange", "contract_key",
        "contract_code", "contract_code_raw", "delivery_year", "delivery_month",
        "expiry_id", "rank", "settle", "volume", "open_interest",
        "first_date", "last_date", "last_trade_proxy", "days_to_last_trading",
        "delivery_month_start", "delivery_month_end", "days_to_delivery_start",
        "in_delivery_month", "is_censored", "negative_price",
        "volume_missing", "oi_missing", "stale", "stale_run",
    ]
    panel = panel[[column for column in columns if column in panel.columns]]
    return panel.sort_values(["date", "root", "contract_code"]).reset_index(drop=True)


def enrich_rank_panel(
    rank_panel: pd.DataFrame,
    contract_panel: pd.DataFrame,
) -> pd.DataFrame:
    """Merge contract-calendar fields onto the rank panel."""

    calendar = contract_panel[
        ["date", "root", "contract_code", *CONTRACT_CALENDAR_COLUMNS]
    ].drop_duplicates(["date", "root", "contract_code"])

    panel = rank_panel.merge(
        calendar,
        on=["date", "root", "contract_code"],
        how="left",
        validate="many_to_one",
    )
    return panel.sort_values(["date", "root", "rank"]).reset_index(drop=True)


def _contract_returns(contract_panel: pd.DataFrame) -> pd.DataFrame:
    panel = contract_panel.sort_values(["root", "contract_code", "date"]).copy()
    grouped = panel.groupby(["root", "contract_code"], sort=False)
    previous_settle = grouped["settle"].shift()
    previous_date = grouped["date"].shift()

    with np.errstate(divide="ignore", invalid="ignore"):
        returns = panel["settle"].div(previous_settle).sub(1)
    panel["ret_contract"] = returns.where(previous_settle.ne(0))
    panel["prev_settle"] = previous_settle
    panel["prev_date"] = previous_date
    panel["return_gap_days"] = (panel["date"] - previous_date).dt.days
    return panel


def build_return_panel(
    rank_panel: pd.DataFrame,
    contract_panel: pd.DataFrame,
) -> pd.DataFrame:
    """Build contract-level returns and map them back to rank slots.

    On a roll date the rank's return is the new contract's return, whose
    previous observation is the old next rank. ``ret_naive`` is a diagnostic
    that differences generic rank prices across the roll and is not tradable.
    """

    contract_returns = _contract_returns(contract_panel)
    rank = rank_panel.sort_values(["date", "root", "rank"]).copy()

    rank["prev_contract_code"] = rank.groupby(["root", "rank"], sort=False)["contract_code"].shift()
    previous_rank_settle = rank.groupby(["root", "rank"], sort=False)["settle"].shift()
    with np.errstate(divide="ignore", invalid="ignore"):
        rank["ret_naive"] = rank["settle"].div(previous_rank_settle).sub(1)
    rank["ret_naive"] = rank["ret_naive"].where(previous_rank_settle.ne(0))

    mapping = contract_returns[
        ["date", "root", "contract_code", "ret_contract", "return_gap_days"]
    ]
    rank = rank.merge(
        mapping,
        on=["date", "root", "contract_code"],
        how="left",
        validate="many_to_one",
    )
    rank["ret_rank"] = rank["ret_contract"]

    columns = [
        "date", "root", "commodity", "sector", "exchange", "rank", "ticker",
        "contract_code", "delivery_year", "delivery_month", "expiry_id",
        "settle", "volume", "open_interest", "is_roll",
        "prev_contract_code", "ret_contract", "ret_rank", "ret_naive",
        "return_gap_days", "negative_price", "stale", "volume_missing",
        "oi_missing",
    ]
    rank = rank[[column for column in columns if column in rank.columns]]
    return rank.sort_values(["date", "root", "rank"]).reset_index(drop=True)


def build_spread_panel(pair_panel: pd.DataFrame) -> pd.DataFrame:
    """Add dollar/log/percentage spreads and expiry distance to a pair panel."""

    panel = curve.add_spreads(pair_panel)
    columns = [
        "date", "root", "commodity", "sector", "exchange",
        "rank_near", "rank_far", "contract_near", "contract_far",
        "settle_near", "settle_far", "spread_dollar", "spread_log",
        "spread_pct", "months_between",
        "delivery_year_near", "delivery_month_near", "delivery_year_far",
        "delivery_month_far", "days_to_last_trading_near",
        "days_to_last_trading_far", "days_to_delivery_start_near",
        "days_to_delivery_start_far", "pair_rank_mix", "is_main_pair",
        "negative_price",
    ]
    panel = panel[[column for column in columns if column in panel.columns]]
    return panel.sort_values(["date", "root"]).reset_index(drop=True)


def save_panel(
    frame: pd.DataFrame,
    name: str,
    directory: str | Path | None = None,
) -> Path:
    """Write a processed panel to parquet and return its path."""

    directory = Path(directory or config.PROCESSED_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.parquet"
    frame.to_parquet(path, index=False)
    return path

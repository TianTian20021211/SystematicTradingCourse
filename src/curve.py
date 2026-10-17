"""Contract calendar, roll logic, eligibility, and pair episodes."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def trading_calendar(panel: pd.DataFrame, date_col: str = "date") -> pd.DatetimeIndex:
    """Sorted union of dates with any data."""

    return pd.DatetimeIndex(sorted(pd.to_datetime(panel[date_col]).unique()))


def add_contract_calendar(
    contract_panel: pd.DataFrame,
    trading_days: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    """Attach per-contract life, expiry proxy, and delivery-month distances.

    ``last_trade_proxy`` is the last date the contract appears in the extract,
    not an exchange last-trading-day calendar. ``days_to_last_trading`` and
    ``days_to_delivery_start`` are measured in trading sessions.
    """

    panel = contract_panel.copy()
    if trading_days is None:
        trading_days = trading_calendar(panel)
    if len(trading_days) == 0:
        raise ValueError("Empty trading calendar")

    grouped = panel.groupby(["root", "contract_code"], sort=False)["date"]
    panel["first_date"] = grouped.transform("min")
    panel["last_date"] = grouped.transform("max")
    panel["last_trade_proxy"] = panel["last_date"]

    date_idx = trading_days.get_indexer(panel["date"])
    last_idx = trading_days.get_indexer(panel["last_trade_proxy"])
    panel["days_to_last_trading"] = last_idx - date_idx

    delivery_start = pd.to_datetime(
        {
            "year": panel["delivery_year"].astype("Int64"),
            "month": panel["delivery_month"].astype("Int64"),
            "day": 1,
        }
    )
    panel["delivery_month_start"] = delivery_start
    panel["delivery_month_end"] = delivery_start + pd.offsets.MonthBegin(1)

    start_idx = trading_days.searchsorted(delivery_start, side="left")
    panel["days_to_delivery_start"] = start_idx - date_idx
    panel["in_delivery_month"] = (
        panel["date"].ge(delivery_start)
        & panel["date"].lt(panel["delivery_month_end"])
    )

    panel["is_censored"] = panel["last_date"].eq(trading_days[-1])
    return panel


def detect_rolls(rank_panel: pd.DataFrame) -> pd.DataFrame:
    """Summarize rank changes per date/commodity."""

    summary = (
        rank_panel.groupby(["date", "root"], sort=True)
        .agg(
            n_present=("contract_code", "count"),
            n_changed=("is_roll", "sum"),
        )
        .reset_index()
    )
    summary["n_changed"] = summary["n_changed"].astype("int64")
    return summary


def validate_roll_queue(rank_panel: pd.DataFrame) -> dict[str, object]:
    """Check that the four-rank queue shifts together.

    Returns a summary dict. Full-coverage dates (all four ranks present on both
    the current and previous trading date) must have either 0 or 4 changes and
    satisfy new M1=old M2, new M2=old M3, new M3=old M4.
    """

    summary = detect_rolls(rank_panel)
    partial = summary[(summary["n_changed"].gt(0)) & (summary["n_changed"].lt(summary["n_present"]))]

    pv = (
        rank_panel.pivot_table(
            index=["root", "date"], columns="rank", values="contract_code",
            aggfunc="first",
        )
        .sort_index()
    )
    previous = pv.groupby(level="root").shift(1)
    full = pv.notna().all(axis=1) & previous.notna().all(axis=1)

    shift_ok = pd.Series(False, index=pv.index)
    if 1 in pv.columns and 2 in previous.columns:
        shift_ok = shift_ok | (
            pv[1].eq(previous[2])
            & pv[2].eq(previous[3])
            & pv[3].eq(previous[4])
        )
    # Non-roll full-coverage days are also valid.
    no_change = pv.eq(previous).all(axis=1)
    valid_full = full & (no_change | shift_ok)

    return {
        "n_date_root": int(len(summary)),
        "n_full_roll_dates": int((summary["n_changed"].eq(4)).sum()),
        "n_partial_rolls": int(len(partial)),
        "n_full_days_checked": int(full.sum()),
        "n_full_day_violations": int((full & ~valid_full).sum()),
        "partial_examples": partial.head(10).to_dict("records"),
    }


def add_eligibility(
    panel: pd.DataFrame,
    d: int = config.D,
    k: int = config.DELIVERY_BUFFER_K,
) -> pd.DataFrame:
    """Flag contracts that are safe to hold for a calendar spread.

    Eligible requires: a priced contract code, no delivery-month exposure,
    at least ``k`` trading sessions before the delivery month starts, and more
    than ``d`` sessions before the contract's last observed date.
    """

    result = panel.copy()
    missing_calendar = result["days_to_delivery_start"].isna() | result["days_to_last_trading"].isna()
    too_close_expiry = result["days_to_last_trading"].le(d)
    too_close_delivery = result["days_to_delivery_start"].lt(k)
    missing_price = result["settle"].isna()
    missing_code = result["contract_code"].isna()

    reason = np.select(
        [
            missing_code,
            missing_price,
            missing_calendar,
            too_close_delivery,
            too_close_expiry,
        ],
        [
            "missing_code",
            "missing_price",
            "missing_calendar",
            "delivery_buffer",
            "expiry_buffer",
        ],
        default="eligible",
    )
    result["eligibility_reason"] = reason
    result["eligible"] = result["eligibility_reason"].eq("eligible")
    return result


def select_pairs(
    panel: pd.DataFrame,
    d: int = config.D,
    k: int = config.DELIVERY_BUFFER_K,
    max_rank: int = 3,
) -> pd.DataFrame:
    """Choose the two nearest eligible contracts on each date/commodity.

    ``max_rank=3`` is a guard: if the first two eligible contracts would be
    M3–M4, the new far leg at the next roll may be outside the four-rank panel.
    Such dates are skipped and counted in QA.
    """

    enriched = add_eligibility(panel, d=d, k=k)
    candidates = enriched.loc[
        enriched["eligible"] & enriched["rank"].le(max_rank)
    ].sort_values(["date", "root", "rank"]).copy()
    candidates["pair_position"] = candidates.groupby(["date", "root"], sort=False).cumcount()
    candidates = candidates.loc[candidates["pair_position"].lt(2)]

    near = candidates.loc[candidates["pair_position"].eq(0)].set_index(["date", "root"])
    far = candidates.loc[candidates["pair_position"].eq(1)].set_index(["date", "root"])
    pairs = near.join(far, how="inner", lsuffix="_near", rsuffix="_far").reset_index()

    pairs["contract_near"] = pairs["contract_code_near"]
    pairs["contract_far"] = pairs["contract_code_far"]
    pairs["commodity"] = pairs["commodity_near"]
    pairs["sector"] = pairs["sector_near"]
    pairs["exchange"] = pairs["exchange_near"]
    pairs["pair_rank_mix"] = (
        "M" + pairs["rank_near"].astype(int).astype(str)
        + "-M" + pairs["rank_far"].astype(int).astype(str)
    )
    # Main pair must be two adjacent listed contracts. If a middle rank is
    # missing/unpriced, skip the date rather than silently creating M1-M3.
    pairs = pairs.loc[pairs["rank_far"].eq(pairs["rank_near"] + 1)].copy()
    pairs["is_main_pair"] = True

    columns = [
        "date", "root", "commodity", "sector", "exchange",
        "rank_near", "rank_far", "contract_near", "contract_far",
        "settle_near", "settle_far",
        "volume_near", "volume_far",
        "open_interest_near", "open_interest_far",
        "delivery_year_near", "delivery_month_near", "expiry_id_near",
        "delivery_year_far", "delivery_month_far", "expiry_id_far",
        "days_to_last_trading_near", "days_to_last_trading_far",
        "days_to_delivery_start_near", "days_to_delivery_start_far",
        "eligibility_reason_near", "eligibility_reason_far",
        "pair_rank_mix", "is_main_pair",
    ]
    pairs = pairs[[column for column in columns if column in pairs.columns]]
    return pairs.sort_values(["date", "root"]).reset_index(drop=True)


def add_spreads(pair_panel: pd.DataFrame) -> pd.DataFrame:
    """Add dollar, log, and percentage spreads to a pair panel."""

    result = pair_panel.copy()
    near = result["settle_near"]
    far = result["settle_far"]
    result["spread_dollar"] = near - far
    result["spread_pct"] = np.where(near.gt(0), result["spread_dollar"] / near, np.nan)
    result["spread_log"] = np.where(
        near.gt(0) & far.gt(0),
        np.log(near.where(near.gt(0))) - np.log(far.where(far.gt(0))),
        np.nan,
    )
    if {"expiry_id_near", "expiry_id_far"}.issubset(result.columns):
        result["months_between"] = result["expiry_id_far"] - result["expiry_id_near"]
    result["negative_price"] = near.le(0) | far.le(0)
    return result


def build_pair_episodes(pair_panel: pd.DataFrame) -> pd.DataFrame:
    """Collapse consecutive dates with the same fixed contract pair."""

    panel = pair_panel.sort_values(["root", "date"]).copy()
    if "spread_dollar" not in panel.columns:
        panel = add_spreads(panel)

    changed = (
        panel["contract_near"].ne(panel.groupby("root")["contract_near"].shift())
        | panel["contract_far"].ne(panel.groupby("root")["contract_far"].shift())
    )
    panel["episode_num"] = changed.groupby(panel["root"]).cumsum()
    panel["episode_id"] = (
        panel["root"] + "_" + panel["episode_num"].astype(int).astype(str).str.zfill(4)
    )

    episodes = (
        panel.groupby(["root", "episode_id"], sort=False)
        .agg(
            contract_near=("contract_near", "first"),
            contract_far=("contract_far", "first"),
            pair_rank_mix=("pair_rank_mix", "first"),
            entry_date=("date", "min"),
            exit_date=("date", "max"),
            holding_days=("date", "nunique"),
            n_obs=("settle_near", "count"),
            entry_spread=("spread_dollar", "first"),
            exit_spread=("spread_dollar", "last"),
            mean_spread=("spread_dollar", "mean"),
        )
        .reset_index()
    )
    episodes["spread_change"] = episodes["exit_spread"] - episodes["entry_spread"]
    return episodes.sort_values(["root", "entry_date"]).reset_index(drop=True)

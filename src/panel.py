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
        "settle_near", "settle_far", "volume_near", "volume_far",
        "open_interest_near", "open_interest_far",
        "spread_dollar", "spread_log",
        "spread_pct", "months_between",
        "delivery_year_near", "delivery_month_near", "delivery_year_far",
        "delivery_month_far", "days_to_last_trading_near",
        "days_to_last_trading_far", "days_to_delivery_start_near",
        "days_to_delivery_start_far", "pair_rank_mix", "is_main_pair",
        "negative_price",
    ]
    panel = panel[[column for column in columns if column in panel.columns]]
    return panel.sort_values(["date", "root"]).reset_index(drop=True)


def _threshold_slug(value: int) -> str:
    if value % 1_000 == 0:
        return f"{value // 1_000}k"
    return str(value)


def _contract_liquidity(
    contract_panel: pd.DataFrame,
    window: int,
    min_obs: int,
) -> pd.DataFrame:
    panel = contract_panel.sort_values(["root", "contract_code", "date"]).copy()
    grouped = panel.groupby(["root", "contract_code"], sort=False)
    panel["liq_volume_contract"] = (
        grouped["volume"]
        .rolling(window, min_periods=min_obs)
        .median()
        .reset_index(level=[0, 1], drop=True)
    )
    panel["liq_oi_contract"] = (
        grouped["open_interest"]
        .rolling(window, min_periods=min_obs)
        .median()
        .reset_index(level=[0, 1], drop=True)
    )
    return panel[
        ["date", "root", "contract_code", "liq_volume_contract", "liq_oi_contract"]
    ]


def _rank_liquidity(
    rank_panel: pd.DataFrame,
    window: int,
    min_obs: int,
) -> pd.DataFrame:
    panel = rank_panel.sort_values(["root", "rank", "date"]).copy()
    grouped = panel.groupby(["root", "rank"], sort=False)
    panel["liq_volume_rank"] = (
        grouped["volume"]
        .rolling(window, min_periods=min_obs)
        .median()
        .reset_index(level=[0, 1], drop=True)
    )
    panel["liq_oi_rank"] = (
        grouped["open_interest"]
        .rolling(window, min_periods=min_obs)
        .median()
        .reset_index(level=[0, 1], drop=True)
    )
    return panel[["date", "root", "rank", "liq_volume_rank", "liq_oi_rank"]]


def build_universe(
    spread_panel: pd.DataFrame,
    contract_panel: pd.DataFrame,
    rank_panel: pd.DataFrame,
    thresholds: tuple[int, ...] = config.LIQUIDITY_THRESHOLDS,
    window: int = config.LIQUIDITY_WINDOW,
    min_obs: int = config.LIQUIDITY_MIN_OBS,
) -> pd.DataFrame:
    """Attach trailing leg/pair liquidity and threshold booleans.

    Contract-level trailing medians are preferred. If a contract has fewer than
    ``min_obs`` observations, fall back to the rank-level trailing median and
    flag ``liq_proxy``. No threshold is applied.
    """

    panel = spread_panel.copy()
    contract_liq = _contract_liquidity(contract_panel, window, min_obs)
    rank_liq = _rank_liquidity(rank_panel, window, min_obs)

    near_contract = contract_liq.rename(
        columns={
            "contract_code": "contract_near",
            "liq_volume_contract": "liq_volume_near_contract",
            "liq_oi_contract": "liq_oi_near_contract",
        }
    )
    far_contract = contract_liq.rename(
        columns={
            "contract_code": "contract_far",
            "liq_volume_contract": "liq_volume_far_contract",
            "liq_oi_contract": "liq_oi_far_contract",
        }
    )
    near_rank = rank_liq.rename(
        columns={
            "rank": "rank_near",
            "liq_volume_rank": "liq_volume_near_rank",
            "liq_oi_rank": "liq_oi_near_rank",
        }
    )
    far_rank = rank_liq.rename(
        columns={
            "rank": "rank_far",
            "liq_volume_rank": "liq_volume_far_rank",
            "liq_oi_rank": "liq_oi_far_rank",
        }
    )

    panel = panel.merge(
        near_contract, on=["date", "root", "contract_near"], how="left",
        validate="many_to_one",
    )
    panel = panel.merge(
        far_contract, on=["date", "root", "contract_far"], how="left",
        validate="many_to_one",
    )
    panel = panel.merge(
        near_rank, on=["date", "root", "rank_near"], how="left",
        validate="many_to_one",
    )
    panel = panel.merge(
        far_rank, on=["date", "root", "rank_far"], how="left",
        validate="many_to_one",
    )

    panel["liq_proxy_near"] = (
        panel["liq_volume_near_contract"].isna()
        & panel["liq_volume_near_rank"].notna()
    )
    panel["liq_proxy_far"] = (
        panel["liq_volume_far_contract"].isna()
        & panel["liq_volume_far_rank"].notna()
    )
    panel["liq_volume_near"] = panel["liq_volume_near_contract"].fillna(
        panel["liq_volume_near_rank"]
    )
    panel["liq_volume_far"] = panel["liq_volume_far_contract"].fillna(
        panel["liq_volume_far_rank"]
    )
    panel["liq_oi_near"] = panel["liq_oi_near_contract"].fillna(
        panel["liq_oi_near_rank"]
    )
    panel["liq_oi_far"] = panel["liq_oi_far_contract"].fillna(
        panel["liq_oi_far_rank"]
    )
    panel["liq_volume_pair"] = np.minimum(panel["liq_volume_near"], panel["liq_volume_far"])
    panel["liq_oi_pair"] = np.minimum(panel["liq_oi_near"], panel["liq_oi_far"])
    panel["liq_proxy"] = panel["liq_proxy_near"] | panel["liq_proxy_far"]
    panel["pair"] = panel["pair_rank_mix"]

    for threshold in thresholds:
        slug = _threshold_slug(threshold)
        panel[f"pass_vol_{slug}"] = panel["liq_volume_pair"].ge(threshold)
        panel[f"pass_oi_{slug}"] = panel["liq_oi_pair"].ge(threshold)

    return panel.sort_values(["date", "root"]).reset_index(drop=True)


def liquidity_summary(
    universe: pd.DataFrame,
    thresholds: tuple[int, ...] = config.LIQUIDITY_THRESHOLDS,
) -> pd.DataFrame:
    rows = []
    for threshold in thresholds:
        slug = _threshold_slug(threshold)
        volume_pass = universe[f"pass_vol_{slug}"]
        oi_pass = universe[f"pass_oi_{slug}"]
        rows.append(
            {
                "threshold": threshold,
                "pair_days": len(universe),
                "pass_volume_days": int(volume_pass.sum()),
                "pass_oi_days": int(oi_pass.sum()),
                "roots_pass_volume": int(universe.loc[volume_pass, "root"].nunique()),
                "roots_pass_oi": int(universe.loc[oi_pass, "root"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def build_adjacent_pairs(
    enriched_rank_panel: pd.DataFrame,
    d: int = config.D,
    k: int = config.DELIVERY_BUFFER_K,
) -> pd.DataFrame:
    """Build all eligible adjacent pairs, flagging the main selected pair.

    ``enriched_rank_panel`` must already contain contract-calendar columns
    (use ``enrich_rank_panel`` or ``build_all``).
    """

    enriched = curve.add_eligibility(enriched_rank_panel, d=d, k=k)
    selected = curve.select_pairs(enriched, d=d, k=k)
    selected_index = pd.MultiIndex.from_frame(
        selected[["date", "root", "contract_near", "contract_far"]]
    )

    parts: list[pd.DataFrame] = []
    for near_rank in (1, 2, 3):
        near = enriched.loc[
            enriched["rank"].eq(near_rank) & enriched["eligible"]
        ]
        far = enriched.loc[
            enriched["rank"].eq(near_rank + 1) & enriched["eligible"]
        ]
        merged = near.merge(
            far, on=["date", "root"], suffixes=("_near", "_far"),
            how="inner", validate="many_to_one",
        )
        if merged.empty:
            continue

        merged["rank_near"] = near_rank
        merged["rank_far"] = near_rank + 1
        merged["contract_near"] = merged["contract_code_near"]
        merged["contract_far"] = merged["contract_code_far"]
        merged["commodity"] = merged["commodity_near"]
        merged["sector"] = merged["sector_near"]
        merged["exchange"] = merged["exchange_near"]
        merged["pair_rank_mix"] = f"M{near_rank}-M{near_rank + 1}"
        parts.append(merged)

    if not parts:
        return pd.DataFrame()

    adjacent = pd.concat(parts, ignore_index=True)
    adjacent["is_main_pair"] = pd.MultiIndex.from_frame(
        adjacent[["date", "root", "contract_near", "contract_far"]]
    ).isin(selected_index)

    columns = [
        "date", "root", "commodity", "sector", "exchange",
        "rank_near", "rank_far", "contract_near", "contract_far",
        "settle_near", "settle_far", "volume_near", "volume_far",
        "open_interest_near", "open_interest_far",
        "delivery_year_near", "delivery_month_near", "expiry_id_near",
        "delivery_year_far", "delivery_month_far", "expiry_id_far",
        "days_to_last_trading_near", "days_to_last_trading_far",
        "days_to_delivery_start_near", "days_to_delivery_start_far",
        "eligibility_reason_near", "eligibility_reason_far",
        "pair_rank_mix", "is_main_pair",
    ]
    adjacent = adjacent[[column for column in columns if column in adjacent.columns]]
    return adjacent.sort_values(["date", "root", "rank_near"]).reset_index(drop=True)


def build_all(
    rank_panel: pd.DataFrame,
    d: int = config.D,
    k: int = config.DELIVERY_BUFFER_K,
) -> dict[str, pd.DataFrame]:
    """Build the full analysis stack from a rank panel."""

    contract = build_contract_panel(rank_panel)
    returns = build_return_panel(rank_panel, contract)
    enriched = enrich_rank_panel(rank_panel, contract)
    pairs = curve.select_pairs(enriched, d=d, k=k)
    spread = build_spread_panel(pairs)
    universe = build_universe(spread, contract, rank_panel)
    episodes = curve.build_pair_episodes(universe)
    adjacent_pairs = build_adjacent_pairs(enriched, d=d, k=k)
    adjacent_spread = build_spread_panel(adjacent_pairs)
    return {
        "rank": rank_panel,
        "contract": contract,
        "returns": returns,
        "pairs": pairs,
        "spread": spread,
        "universe": universe,
        "episodes": episodes,
        "adjacent_pairs": adjacent_pairs,
        "adjacent_spread": adjacent_spread,
    }


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

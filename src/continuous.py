"""Roll-chained continuous price indices for calendar spreads.

The generic M1-M4 ranks are slots, not contracts. A fixed contract pair also
changes over time as eligibility rolls. To build a signal history for idea C,
this module chains *contract-level price changes* for the near and far legs:

    near_index[t] = near_index[t-1] + delta_near[t]
    far_index[t]  = far_index[t-1]  + delta_far[t]
    spread_index[t] = near_index[t] - far_index[t]

On a roll date the new pair's contracts supply their own price changes, so the
index does not jump by the level difference between the old and new spreads.
The index is a synthetic signal series; the backtest still trades the raw
dollar spread through the engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_PAIR_COLUMNS = ["date", "root", "contract_near", "contract_far"]
REQUIRED_CONTRACT_COLUMNS = ["date", "root", "contract_code", "settle"]


def _validate_inputs(pairs: pd.DataFrame, contract_panel: pd.DataFrame) -> None:
    missing_pairs = [c for c in REQUIRED_PAIR_COLUMNS if c not in pairs.columns]
    if missing_pairs:
        raise ValueError(f"pairs missing columns: {missing_pairs}")
    missing_contracts = [
        c for c in REQUIRED_CONTRACT_COLUMNS if c not in contract_panel.columns
    ]
    if missing_contracts:
        raise ValueError(f"contract_panel missing columns: {missing_contracts}")

    pair_duplicates = pairs.duplicated(["date", "root"])
    if pair_duplicates.any():
        raise ValueError(
            f"Duplicate (date, root) in pairs: {int(pair_duplicates.sum())}"
        )
    contract_duplicates = contract_panel.duplicated(
        ["date", "root", "contract_code"]
    )
    if contract_duplicates.any():
        raise ValueError(
            "Duplicate (date, root, contract_code) in contract_panel: "
            f"{int(contract_duplicates.sum())}"
        )


def _contract_price_changes(contract_panel: pd.DataFrame) -> pd.DataFrame:
    """Contract-level price changes, computed within each contract.

    ``prev_settle`` is the previous observed settle for the same contract, so a
    date gap is reflected in the next change. A zero previous settle makes the
    change unusable (return undefined); it is flagged and set to NaN.
    """

    panel = contract_panel[REQUIRED_CONTRACT_COLUMNS].copy()
    panel = panel.sort_values(["root", "contract_code", "date"])
    grouped = panel.groupby(["root", "contract_code"], sort=False)["settle"]
    panel["prev_settle"] = grouped.shift()
    panel["delta_settle"] = panel["settle"] - panel["prev_settle"]
    panel["zero_prev_settle"] = panel["prev_settle"].eq(0)
    panel.loc[panel["zero_prev_settle"], "delta_settle"] = np.nan
    return panel


def _pair_change_flags(pairs: pd.DataFrame) -> pd.Series:
    """True when the fixed contract pair changes for a root."""

    ordered = pairs.sort_values(["root", "date"])
    previous_near = ordered.groupby("root", sort=False)["contract_near"].shift()
    previous_far = ordered.groupby("root", sort=False)["contract_far"].shift()
    changed = (
        ordered["contract_near"].ne(previous_near)
        | ordered["contract_far"].ne(previous_far)
    ) & previous_near.notna() & previous_far.notna()
    return changed.reindex(pairs.index).fillna(False).astype(bool)


def build_continuous_leg_prices(
    pairs: pd.DataFrame,
    contract_panel: pd.DataFrame,
) -> pd.DataFrame:
    """Build roll-chained near/far price indices and the dollar spread index.

    The first date with both settles present initializes each index at the
    observed settle. Subsequent dates add each contract's own price change.
    Missing changes hold the corresponding index; the spread index is NaN on
    those dates. No raw price is forward-filled.
    """

    _validate_inputs(pairs, contract_panel)

    changes = _contract_price_changes(contract_panel)

    near = changes.rename(
        columns={
            "contract_code": "contract_near",
            "settle": "settle_near",
            "prev_settle": "prev_settle_near",
            "delta_settle": "delta_near",
            "zero_prev_settle": "zero_prev_settle_near",
        }
    )
    far = changes.rename(
        columns={
            "contract_code": "contract_far",
            "settle": "settle_far",
            "prev_settle": "prev_settle_far",
            "delta_settle": "delta_far",
            "zero_prev_settle": "zero_prev_settle_far",
        }
    )

    label_columns = [
        c for c in ("commodity", "sector") if c in pairs.columns
    ]
    base = pairs[
        ["date", "root", *label_columns, "contract_near", "contract_far"]
    ].copy()
    base["is_pair_change"] = _pair_change_flags(base)

    out = base.merge(
        near,
        on=["date", "root", "contract_near"],
        how="left",
        validate="many_to_one",
    ).merge(
        far,
        on=["date", "root", "contract_far"],
        how="left",
        validate="many_to_one",
    )

    out["raw_spread"] = out["settle_near"] - out["settle_far"]
    out["near_index"] = np.nan
    out["far_index"] = np.nan
    out["spread_index"] = np.nan
    out["near_price_change_missing"] = False
    out["far_price_change_missing"] = False

    ordered = out.sort_values(["root", "date"])
    for root, group in ordered.groupby("root", sort=False):
        valid = group["settle_near"].notna() & group["settle_far"].notna()
        if not valid.any():
            continue

        first_position = group.index[valid.to_numpy()][0]
        first_index = group.index.get_loc(first_position)
        after = group.iloc[first_index + 1:]
        near_level = float(group.loc[first_position, "settle_near"])
        far_level = float(group.loc[first_position, "settle_far"])
        out.loc[first_position, "near_index"] = near_level
        out.loc[first_position, "far_index"] = far_level
        out.loc[first_position, "spread_index"] = near_level - far_level

        if after.empty:
            continue

        near_missing = after["delta_near"].isna()
        far_missing = after["delta_far"].isna()
        near_levels = near_level + after["delta_near"].fillna(0.0).cumsum()
        far_levels = far_level + after["delta_far"].fillna(0.0).cumsum()
        spread_levels = (near_levels - far_levels).where(
            ~near_missing & ~far_missing
        )

        out.loc[after.index, "near_index"] = near_levels.to_numpy()
        out.loc[after.index, "far_index"] = far_levels.to_numpy()
        out.loc[after.index, "spread_index"] = spread_levels.to_numpy()
        out.loc[after.index, "near_price_change_missing"] = near_missing.to_numpy()
        out.loc[after.index, "far_price_change_missing"] = far_missing.to_numpy()

    output_columns = [
        "date", "root", *label_columns, "contract_near", "contract_far",
        "settle_near", "settle_far", "raw_spread",
        "near_index", "far_index", "spread_index",
        "delta_near", "delta_far",
        "prev_settle_near", "prev_settle_far",
        "is_pair_change",
        "near_price_change_missing", "far_price_change_missing",
        "zero_prev_settle_near", "zero_prev_settle_far",
    ]
    return out[output_columns].sort_values(["date", "root"]).reset_index(drop=True)


def build_spread_index(leg_prices: pd.DataFrame) -> pd.DataFrame:
    """Return the continuous spread index and its diagnostic columns.

    Kept as a separate, thin layer so a log-spread or hedge-ratio variant can
    be added later without changing the leg-price construction.
    """

    required = {"date", "root", "spread_index"}
    missing = required.difference(leg_prices.columns)
    if missing:
        raise ValueError(f"leg_prices missing columns: {sorted(missing)}")

    columns = [
        c for c in (
            "date", "root", "commodity", "sector",
            "contract_near", "contract_far",
            "raw_spread", "near_index", "far_index", "spread_index",
            "is_pair_change",
            "near_price_change_missing", "far_price_change_missing",
        )
        if c in leg_prices.columns
    ]
    return leg_prices[columns].sort_values(["date", "root"]).reset_index(drop=True)


def roll_diagnostics(leg_prices: pd.DataFrame) -> pd.DataFrame:
    """Compare raw spread changes with continuous index changes around rolls.

    On a roll date the continuous change should equal
    ``delta_near - delta_far``; the raw spread change can be much larger.
    """

    required = {"date", "root", "raw_spread", "spread_index"}
    missing = required.difference(leg_prices.columns)
    if missing:
        raise ValueError(f"leg_prices missing columns: {sorted(missing)}")

    diag = leg_prices.sort_values(["root", "date"]).copy()
    diag["raw_spread_change"] = diag.groupby("root", sort=False)["raw_spread"].diff()
    diag["spread_index_change"] = (
        diag.groupby("root", sort=False)["spread_index"].diff()
    )
    if {"delta_near", "delta_far"}.issubset(diag.columns):
        diag["expected_change"] = diag["delta_near"] - diag["delta_far"]
    else:
        diag["expected_change"] = np.nan

    columns = [
        "date", "root", "raw_spread", "raw_spread_change",
        "spread_index", "spread_index_change", "expected_change",
        "is_pair_change",
        "near_price_change_missing", "far_price_change_missing",
    ]
    columns = [c for c in columns if c in diag.columns]
    return diag[columns].sort_values(["date", "root"]).reset_index(drop=True)

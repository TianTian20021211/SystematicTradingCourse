"""Adapters from the v1 signal functions to the v2 holdings simulator.

Each adapter returns ``sizing.LEG_COLUMNS``. The v2 simulator treats a
missing leg row as "keep holdings" and a row with ``group_id="flat"`` as an
exit, so adapters add explicit flat rows for target-zero, no-pair and
non-positive-price dates.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import b_pre_test, continuous, curve, kalman, marks, panel, signals, sizing, specs


@dataclass(frozen=True)
class V2Inputs:
    """Shared panels for one v2 run."""

    bt: dict[str, pd.DataFrame]
    marks: pd.DataFrame
    pairs: pd.DataFrame


def load_v2_inputs(
    rank: pd.DataFrame,
    d: int | None = 5,
    k: int = 5,
    min_adv: float | None = 100.0,
) -> V2Inputs:
    """Build the v2 panels and the ex-ante liquidity flag."""

    bt = panel.build_backtest_panel(rank, d=d, k=k)
    mk = marks.build_marks(bt["contract"], specs.load_contract_specs())
    pairs = sizing.attach_leg_liquidity(bt["spread"], mk)
    if min_adv is not None:
        pairs = sizing.filter_liquid(pairs, min_adv)
    return V2Inputs(bt=bt, marks=mk, pairs=pairs)


def _flats_for_signal(signal: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    """Date/root keys that should be explicit flats.

    Includes target-zero rows (the signal's own exit state), no-pair rows
    when the signal reports ``has_pair``, and pair-dates with a non-positive
    leg price (v2 refuses to trade those).
    """

    flat = signal.loc[
        signal["target"].fillna(0.0).eq(0), ["date", "root"]
    ].drop_duplicates()
    if "has_pair" in signal.columns:
        flat = pd.concat([
            flat,
            signal.loc[~signal["has_pair"].fillna(False).astype(bool), ["date", "root"]],
        ])
    bad = pairs.loc[
        pairs["settle_near"].le(0) | pairs["settle_far"].le(0),
        ["date", "root"],
    ]
    flat = pd.concat([flat, bad], ignore_index=True).drop_duplicates()
    return flat.reset_index(drop=True)


def _append_flats(legs: pd.DataFrame, flat: pd.DataFrame) -> pd.DataFrame:
    """Append flat rows for keys that do not already have a leg row."""

    if flat.empty:
        return legs
    existing = set(zip(legs["date"], legs["root"]))
    keep = np.array([(d, r) not in existing for d, r in zip(flat["date"], flat["root"])])
    flat = flat.loc[keep]
    if flat.empty:
        return legs
    flat = flat.assign(
        group_id="flat", contract=np.nan, units=0.0,
        budget=0.0, target=0.0, resize_key="",
    )
    out = pd.concat([legs, flat[sizing.LEG_COLUMNS]], ignore_index=True)
    return out.sort_values(["date", "root", "contract"]).reset_index(drop=True)


def _weekly_snap(signal: pd.DataFrame, leg_prices: pd.DataFrame) -> pd.Series:
    """Use daily h on weekly/pair-change dates and forward-fill otherwise."""

    h = pd.to_numeric(signal["hedge_ratio"], errors="coerce")
    evaluation = signal["is_evaluation"].fillna(False).astype(bool)
    pair_change = pd.Series(False, index=signal.index)
    if "is_pair_change" in leg_prices.columns:
        changed = leg_prices.loc[
            leg_prices["is_pair_change"].fillna(False).astype(bool), ["date", "root"]
        ]
        pair_change = pd.MultiIndex.from_frame(
            signal[["date", "root"]]
        ).isin(pd.MultiIndex.from_frame(changed))
    snapped = h.where(evaluation | pair_change)
    return snapped.groupby(signal["root"]).ffill()


def _pair_change_dates(pairs: pd.DataFrame) -> set[pd.Timestamp]:
    """Dates on which any root's main pair changes."""

    p = pairs.sort_values(["root", "date"])
    prev_near = p.groupby("root")["contract_near"].shift()
    prev_far = p.groupby("root")["contract_far"].shift()
    changed = (
        p["contract_near"].ne(prev_near)
        | p["contract_far"].ne(prev_far)
    )
    return set(pd.to_datetime(p.loc[changed, "date"]).unique())


def a_legs(inputs: V2Inputs) -> pd.DataFrame:
    """Idea A carry, v2-native (daily on_change, equal-notional)."""

    sig = signals.carry_signal(inputs.pairs)
    legs = sizing.legs_from_signal(
        sig, inputs.pairs, scheme="equal", n_mode="active"
    )
    return _append_flats(legs, _flats_for_signal(sig, inputs.pairs))


def d_legs(inputs: V2Inputs) -> pd.DataFrame:
    """Idea D curve momentum, monthly target path executed by v2 on_change."""

    returns = panel.build_return_panel(inputs.bt["rank"], inputs.bt["contract"])
    # The return panel and the pair panel can have slightly different date
    # unions; let the signal derive the union (as the v1 notebook does).
    sig = signals.curve_momentum_signal(inputs.bt["spread"], returns)
    legs = sizing.legs_from_signal(
        sig, inputs.pairs, scheme="equal", n_mode="active"
    )
    return _append_flats(legs, _flats_for_signal(sig, inputs.pairs))


def c_legs(inputs: V2Inputs, method: str = "1:1") -> pd.DataFrame:
    """Idea C mean reversion: 1:1, rolling-OLS hedge or Kalman hedge."""

    if method not in {"1:1", "ols", "kalman"}:
        raise ValueError(f"method must be '1:1', 'ols' or 'kalman', got {method!r}")
    trading_days = curve.trading_calendar(inputs.bt["contract"])
    leg_prices = continuous.build_continuous_leg_prices(
        inputs.bt["pairs"], inputs.bt["contract"]
    )
    hedge = None
    if method == "1:1":
        spread_index = continuous.build_spread_index(leg_prices)
    elif method == "ols":
        hedge = continuous.rolling_ols_hedge_ratio(leg_prices)
        spread_index = hedge[["date", "root", "commodity", "sector", "spread_index"]]
    else:
        hedge = kalman.kalman_hedge_ratio(leg_prices)
        spread_index = hedge[["date", "root", "commodity", "sector", "spread_index"]]

    sig = signals.mean_reversion_signal(
        spread_index,
        signals.MeanReversionParams(),
        trading_days=trading_days,
        pair_grid=inputs.bt["pairs"][["date", "root"]],
    )
    if hedge is not None:
        sig = sig.merge(
            hedge[["date", "root", "hedge_ratio", "hedge_ratio_valid"]],
            on=["date", "root"],
            how="left",
            validate="one_to_one",
        )
        sig["hedge_ratio"] = _weekly_snap(sig, leg_prices)
        valid = (
            sig["hedge_ratio_valid"].fillna(False).astype(bool)
            & np.isfinite(sig["hedge_ratio"])
            & sig["hedge_ratio"].gt(0)
        )
        sig.loc[~valid, "target"] = 0.0

    legs = sizing.legs_from_signal(
        sig, inputs.pairs, scheme="equal", n_mode="active"
    )
    return _append_flats(legs, _flats_for_signal(sig, inputs.pairs))


def b_legs(inputs: V2Inputs, rank: pd.DataFrame) -> pd.DataFrame:
    """Idea B adjacent-carry pre-test, explicit multi-leg rows.

    Keeps the v1 B universe (raw-rank adjacent carries, ``d=None`` main-pair
    validation) and samples the daily targets to v1's weekly rebalance dates
    plus main-pair change dates.
    """

    bt_b = panel.build_backtest_panel(rank, d=None, k=5)
    targets = b_pre_test.build_b_targets(rank, bt_b["spread"])
    if targets.empty:
        return pd.DataFrame(columns=sizing.LEG_COLUMNS)

    trading_days = curve.trading_calendar(inputs.bt["contract"])
    event_dates = curve.weekly_rebalance_dates(trading_days) | _pair_change_dates(
        bt_b["spread"]
    )
    universe_dates = set(pd.DatetimeIndex(bt_b["spread"]["date"]).unique())
    event_dates = {
        pd.Timestamp(d) for d in event_dates if pd.Timestamp(d) in universe_dates
    }
    b = targets.loc[
        targets["units"].ne(0) & targets["date"].isin(event_dates)
    ].copy()
    if b.empty:
        return pd.DataFrame(columns=sizing.LEG_COLUMNS)

    active = b.groupby("date")["root"].nunique()
    stable = active.rolling(5, min_periods=1).max()
    b["budget"] = 1.0 / b["date"].map(stable)
    budget = b[["date", "root", "budget"]].drop_duplicates()
    legs = sizing.legs_from_rows(
        b[["date", "root", "contract", "units", "target"]], budget=budget
    )

    roots = sorted(pd.unique(bt_b["spread"]["root"]))
    grid = pd.MultiIndex.from_product(
        [sorted(event_dates), roots], names=["date", "root"]
    ).to_frame(index=False)
    existing = set(zip(legs["date"], legs["root"]))
    grid = grid.loc[
        np.array([(d, r) not in existing for d, r in zip(grid["date"], grid["root"])])
    ]
    return _append_flats(legs, grid)

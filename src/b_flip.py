"""B-flip signal research helpers.

The original B (long high adjacent carry, short low) is a pre-registered
negative. This module studies the reverse hypothesis — long the lowest-carry
adjacent spread, short the highest — as a gross signal for later
combination. It is not an official strategy result and is never added to the
cross-idea comparison.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import b_pre_test, costs, curve, horizon, report, simulate, v2_signals


@dataclass(frozen=True)
class BFlipData:
    """Prepared eligible adjacent-carry panel for the research diagnostics."""

    bt_b: dict[str, pd.DataFrame]
    adjacent: pd.DataFrame
    event_dates: set[pd.Timestamp]


def prepare(
    inputs: v2_signals.V2Inputs,
    rank: pd.DataFrame,
    d: int | None = 10,
    min_adv: float | None = 100.0,
) -> BFlipData:
    """Build the D=10 eligible adjacent-carry panel and event dates."""

    bt_b, adjacent = v2_signals.load_b_adjacent(
        inputs, rank, d=d, min_adv=min_adv
    )
    trading_days = curve.trading_calendar(inputs.bt["contract"])
    event_dates = curve.weekly_rebalance_dates(trading_days) | v2_signals._pair_change_dates(
        bt_b["spread"]
    )
    universe_dates = set(pd.DatetimeIndex(bt_b["spread"]["date"]).unique())
    event_dates = {
        pd.Timestamp(date)
        for date in event_dates
        if pd.Timestamp(date) in universe_dates
    }
    return BFlipData(bt_b=bt_b, adjacent=adjacent, event_dates=event_dates)


def _performance_all(res: simulate.SimResult) -> pd.DataFrame:
    return pd.concat(
        {
            "full": report.performance_table(res),
            "train 1986-2015": report.performance_table(res, end="2015-12-31"),
            "test 2016-2026": report.performance_table(res, start="2016-01-01"),
        },
        names=["period"],
    )


def _config(
    capital: float,
    cost: costs.CostParams | None,
    round_lots: bool,
) -> simulate.SimConfig:
    return simulate.SimConfig(
        capital=capital,
        resize="on_change",
        rebalance_band=1e9,
        round_lots=round_lots,
        cost=cost or costs.CostParams(execution="legs"),
    )


def run_b_flip(
    inputs: v2_signals.V2Inputs,
    rank: pd.DataFrame,
    capital: float = 10_000_000.0,
    cost: costs.CostParams | None = None,
    round_lots: bool = False,
    d: int | None = 10,
    min_adv: float | None = 100.0,
) -> dict:
    """Run the B-flip v2 portfolio (default D=10, min_adv=100, USD 10m)."""

    legs = v2_signals.b_flip_legs(inputs, rank, d=d, min_adv=min_adv)
    res = simulate.simulate(legs, inputs.marks, _config(capital, cost, round_lots))
    return {
        "legs": legs,
        "result": res,
        "performance": _performance_all(res),
    }


def run_b_static(
    inputs: v2_signals.V2Inputs,
    rank: pd.DataFrame,
    capital: float = 10_000_000.0,
    cost: costs.CostParams | None = None,
    round_lots: bool = False,
    d: int | None = 10,
    min_adv: float | None = 100.0,
) -> dict:
    """Run the static long-front / short-back maturity control."""

    legs = v2_signals.b_static_legs(inputs, rank, d=d, min_adv=min_adv)
    res = simulate.simulate(legs, inputs.marks, _config(capital, cost, round_lots))
    return {
        "legs": legs,
        "result": res,
        "performance": _performance_all(res),
    }


def run_raw_flip(
    inputs: v2_signals.V2Inputs,
    original_legs: pd.DataFrame,
    capital: float = 10_000_000.0,
    cost: costs.CostParams | None = None,
    round_lots: bool = False,
) -> dict:
    """Exact sign reversal of the original raw-rank B legs."""

    legs = v2_signals.flip_legs(original_legs)
    res = simulate.simulate(legs, inputs.marks, _config(capital, cost, round_lots))
    return {
        "legs": legs,
        "result": res,
        "performance": _performance_all(res),
    }


def _selected_forward(
    adjacent: pd.DataFrame,
    marks: pd.DataFrame,
    selection: pd.DataFrame,
    horizons: list[tuple[int, int]],
) -> pd.DataFrame:
    """Attach fixed-pair forward returns to the selected long/short pairs."""

    fwd = horizon.forward_returns(adjacent, marks, horizons)
    f = adjacent.reset_index(drop=True).copy()
    for col in fwd.columns:
        if col.startswith("fwd_"):
            f[col] = fwd[col].to_numpy()
    fwd_cols = [col for col in f.columns if col.startswith("fwd_")]

    long = selection[["date", "root", "rank_long"]].merge(
        f[["date", "root", "rank_near", *fwd_cols]].rename(
            columns={"rank_near": "rank_long"}
        ),
        on=["date", "root", "rank_long"],
        how="left",
    )
    short = selection[["date", "root", "rank_short"]].merge(
        f[["date", "root", "rank_near", *fwd_cols]].rename(
            columns={"rank_near": "rank_short"}
        ),
        on=["date", "root", "rank_short"],
        how="left",
    )
    out = selection[["date", "root", "rank_long", "rank_short"]].copy()
    for col in fwd_cols:
        out[col.replace("fwd_", "flip_")] = (
            long[col].to_numpy() - short[col].to_numpy()
        )
    return out


def _profile(selected: pd.DataFrame, windows: list[tuple[int, int]]) -> pd.DataFrame:
    rows = []
    for a, b in windows:
        col = f"flip_{a}_{b}"
        series = selected.groupby("date")[col].mean().dropna()
        rows.append(
            dict(
                horizon=f"t+{a}->t+{b}",
                days=b - a,
                mean_bps=series.mean() * 1e4,
                bps_per_day=series.mean() * 1e4 / (b - a),
                t_nw=horizon.newey_west_t(series, b - a),
                hit_rate=(series > 0).mean(),
                n_dates=len(series),
            )
        )
    return pd.DataFrame(rows)


def horizon_profiles(
    inputs: v2_signals.V2Inputs,
    rank: pd.DataFrame,
    d: int | None = 10,
    min_adv: float | None = 100.0,
    marginal: list[tuple[int, int]] | None = None,
    cumulative: list[tuple[int, int]] | None = None,
    timing: list[tuple[int, int]] | None = None,
    long_rule: str = "carry_low",
    short_rule: str = "carry_high",
) -> dict:
    """Signal-level timing and horizon diagnostics for B-flip."""

    data = prepare(inputs, rank, d=d, min_adv=min_adv)
    selection = b_pre_test.select_adjacent(
        data.adjacent, long_rule, short_rule
    )
    if selection.empty:
        raise ValueError("No B-flip selections in the eligible universe")
    windows = sorted(set(marginal or []) | set(cumulative or []) | set(timing or []))
    selected = _selected_forward(data.adjacent, inputs.marks, selection, windows)
    return {
        "selection": selection,
        "selected": selected,
        "marginal": _profile(selected, marginal) if marginal else pd.DataFrame(),
        "cumulative": _profile(selected, cumulative) if cumulative else pd.DataFrame(),
        "timing": _profile(selected, timing) if timing else pd.DataFrame(),
    }


def bootstrap_selected(
    selected: pd.DataFrame,
    window: tuple[int, int] = (1, 6),
    block: int = 21,
    n_boot: int = 2000,
    seed: int = 0,
    min_obs: int = 252,
) -> tuple[pd.DataFrame, dict]:
    """Per-root block bootstrap of the signal-level long-short return."""

    a, b = window
    col = f"flip_{a}_{b}"
    values = selected[["date", "root", col]].rename(columns={col: "ret"})
    summary, draws = horizon.block_bootstrap_mean(
        values, "ret", block=block, n_boot=n_boot, seed=seed, min_obs=min_obs
    )
    summary["mean_bps"] = summary["mean"] * 1e4
    summary["ci_lo_bps"] = summary["ci_lo"] * 1e4
    summary["ci_hi_bps"] = summary["ci_hi"] * 1e4
    summary["ci_lo"] = summary["ci_lo_bps"]
    summary["ci_hi"] = summary["ci_hi_bps"]
    draws = {root: values * 1e4 for root, values in draws.items()}
    return summary, draws


def rank_placebo(
    inputs: v2_signals.V2Inputs,
    rank: pd.DataFrame,
    d: int | None = 10,
    min_adv: float | None = 100.0,
    window: tuple[int, int] = (1, 6),
    n_boot: int = 2000,
    seed: int = 0,
) -> dict:
    """Permute carry ranks within each root-date and recompute the flip mean.

    The placebo preserves the pair set, the number of pairs, the leg count and
    the forward window; it only destroys the ranking information. The test is
    at the signal level, so it is fast and does not run the v2 simulator.
    """

    data = prepare(inputs, rank, d=d, min_adv=min_adv)
    adj = (
        data.adjacent.loc[data.adjacent["carry_ann"].notna()]
        .sort_values(["date", "root", "rank_near"])
        .reset_index(drop=True)
        .copy()
    )
    fwd = horizon.forward_returns(adj, inputs.marks, [window])
    col = f"fwd_{window[0]}_{window[1]}"
    adj[col] = fwd[col].to_numpy()
    adj = adj.loc[adj[col].notna()].reset_index(drop=True)

    keys = pd.MultiIndex.from_frame(adj[["date", "root"]])
    group_id, _ = pd.factorize(keys)
    counts = np.bincount(group_id)
    keep = counts[group_id] >= 2
    adj = adj.loc[keep].reset_index(drop=True)
    keys = pd.MultiIndex.from_frame(adj[["date", "root"]])
    group_id, _ = pd.factorize(keys)
    n_groups = int(group_id.max()) + 1
    counts = np.bincount(group_id, minlength=n_groups)
    pos = adj.groupby(group_id).cumcount().to_numpy()

    carry = np.full((n_groups, 3), np.nan)
    forward = np.full((n_groups, 3), np.nan)
    carry[group_id, pos] = adj["carry_ann"].to_numpy()
    forward[group_id, pos] = adj[col].to_numpy()
    n_pairs = counts.copy()
    if (n_pairs < 2).any() or (n_pairs > 3).any():
        raise ValueError("rank_placebo expects 2 or 3 valid adjacent pairs")

    # All ordered (low, high) pairs. For two-pair groups only the first two
    # columns are used; for three-pair groups all six are equally likely under
    # a random permutation of the three carries.
    outcomes = np.full((n_groups, 6), np.nan)
    two = n_pairs == 2
    three = n_pairs == 3
    outcomes[two, 0] = forward[two, 0] - forward[two, 1]
    outcomes[two, 1] = forward[two, 1] - forward[two, 0]
    ordered = ((0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1))
    for j, (i, k) in enumerate(ordered):
        outcomes[three, j] = forward[three, i] - forward[three, k]
    n_perms = np.where(two, 2, 6)

    group_dates = adj.groupby(group_id)["date"].first().to_numpy()
    date_codes, _ = pd.factorize(group_dates)
    n_dates = int(date_codes.max()) + 1
    date_counts = np.bincount(date_codes, minlength=n_dates)

    rows = np.arange(n_groups)
    actual_group = forward[rows, np.nanargmin(carry, axis=1)] - forward[
        rows, np.nanargmax(carry, axis=1)
    ]
    actual_daily = np.bincount(date_codes, weights=actual_group, minlength=n_dates)
    actual = (actual_daily / date_counts).mean()

    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    chunk = max(1, min(50, n_boot))
    for start in range(0, n_boot, chunk):
        size = min(chunk, n_boot - start)
        chooser = rng.random((size, n_groups))
        idx = np.floor(chooser * n_perms[None, :]).astype(int)
        values = outcomes[rows[None, :], idx]
        daily = np.zeros((size, n_dates))
        np.add.at(daily, (np.arange(size)[:, None], date_codes[None, :]), values)
        daily /= date_counts
        draws[start : start + size] = daily.mean(axis=1)

    p_one = float((draws >= actual).mean())
    p_two = float(min(1.0, 2 * min(p_one, (draws <= actual).mean())))
    return {
        "actual": actual * 1e4,
        "draws": draws * 1e4,
        "p_one_sided": p_one,
        "p_two_sided": p_two,
        "percentile": float((draws < actual).mean() * 100),
        "n_boot": n_boot,
        "n_groups": n_groups,
        "n_dates": n_dates,
    }


def bootstrap_roots(
    res: simulate.SimResult,
    capital: float,
    block: int = 21,
    n_boot: int = 2000,
    seed: int = 0,
    min_obs: int = 252,
) -> tuple[pd.DataFrame, dict]:
    """Per-root moving-block bootstrap of the daily gross contribution."""

    values = res.by_root[["date", "root", "pnl_gross"]].copy()
    values["ret_gross"] = values["pnl_gross"] / capital
    summary, draws = horizon.block_bootstrap_mean(
        values, "ret_gross", block=block, n_boot=n_boot, seed=seed,
        min_obs=min_obs,
    )
    summary["mean_bps"] = summary["mean"] * 1e4
    summary["ci_lo_bps"] = summary["ci_lo"] * 1e4
    summary["ci_hi_bps"] = summary["ci_hi"] * 1e4
    summary["ci_lo"] = summary["ci_lo_bps"]
    summary["ci_hi"] = summary["ci_hi_bps"]
    draws = {root: values * 1e4 for root, values in draws.items()}
    return summary, draws


def root_jackknife(
    res: simulate.SimResult,
    capital: float,
) -> pd.DataFrame:
    """Drop one root at a time and recompute gross ann return / Sharpe / t."""

    values = res.by_root[["date", "root", "pnl_gross"]].copy()
    values["ret_gross"] = values["pnl_gross"] / capital
    daily = values.groupby("date")["ret_gross"].sum().sort_index()

    def stats(series: pd.Series) -> dict:
        sd = series.std()
        return dict(
            ann_ret_pct=series.mean() * 252 * 100,
            sharpe=series.mean() / sd * np.sqrt(252) if sd > 0 else np.nan,
            t_nw=horizon.newey_west_t(series, 5),
        )

    rows = [dict(root="ALL", **stats(daily))]
    for root in sorted(values["root"].unique()):
        excluded = (
            values.loc[values["root"].ne(root)]
            .groupby("date")["ret_gross"]
            .sum()
            .reindex(daily.index)
            .fillna(0.0)
        )
        rows.append(dict(root=root, **stats(excluded)))
    return pd.DataFrame(rows)

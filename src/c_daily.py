"""Daily C mean-reversion audit runners.

The official weekly C results stay in ``src/v2_signals.py`` and
``src/v2_rerun.py``. This module builds the daily version used by the D-025
information audit: the z-score and hedge ratio update every trading day, the
signal is dated at t and filled at t+1, and costs are switched off because the
audit is gross-only.

The three variants match the weekly ones:

- ``"1:1"``: C1, equal-notional legs;
- ``"ols"``: C2, 60-day rolling-OLS hedge ratio;
- ``"kalman"``: C3, rolling-likelihood Kalman hedge ratio.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import (
    continuous,
    costs,
    curve,
    horizon,
    kalman,
    report,
    signals,
    simulate,
    sizing,
    v2_signals,
)

METHODS = ("1:1", "ols", "kalman")

TRAIN_PERIOD = (None, "2005-12-31")
VALIDATION_PERIOD = ("2006-01-01", "2015-12-31")
TEST_PERIOD = ("2016-01-01", None)

STAGE1_PERIODS = {
    "train 1986-2005": TRAIN_PERIOD,
    "validation 2006-2015": VALIDATION_PERIOD,
    "train+validation 1986-2015": (None, "2015-12-31"),
}

PERIODS = {
    "full": (None, None),
    **STAGE1_PERIODS,
    "test 2016-2026": TEST_PERIOD,
}


@dataclass(frozen=True)
class DailyCSettings:
    """Execution and decision conventions for the daily audit (gross-only)."""

    capital: float = 10_000_000.0
    resize: str = "on_change"
    rebalance_band: float = 1e9
    zero_cost: bool = True
    block: int = 21
    n_boot: int = 2_000
    seed: int = 0
    min_root_active_days: int = 252
    sr_gain: float = 0.05
    breadth_threshold: float = 0.60
    gate_sr: float = 0.40


def _sim_config(settings: DailyCSettings) -> simulate.SimConfig:
    """SimConfig with zero costs for the gross-only audit."""

    if settings.zero_cost:
        cost = costs.CostParams(
            half_spread_ticks=0.0,
            liquidity_elasticity=0.0,
            fee_per_contract=0.0,
            impact_y=0.0,
            proportional_bps=0.0,
        )
    else:
        cost = costs.CostParams()
    return simulate.SimConfig(
        capital=settings.capital,
        resize=settings.resize,
        rebalance_band=settings.rebalance_band,
        cost=cost,
    )


def daily_signal(inputs: v2_signals.V2Inputs, method: str = "1:1") -> pd.DataFrame:
    """Build the daily C target path for one hedge variant.

    C2/C3 use the daily hedge ratio (no weekly snap); invalid or non-positive
    ``h`` forces the target to zero. The state machine is evaluated every
    trading day; the engine fills the target at t+1.
    """

    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, got {method!r}")

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
        signals.MeanReversionParams(evaluation="daily"),
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
        valid = (
            sig["hedge_ratio_valid"].fillna(False).astype(bool)
            & np.isfinite(sig["hedge_ratio"])
            & sig["hedge_ratio"].gt(0)
        )
        sig.loc[~valid, "target"] = 0.0

    return sig


def daily_legs(inputs: v2_signals.V2Inputs, method: str = "1:1") -> pd.DataFrame:
    """Daily C target path mapped to ``sizing.LEG_COLUMNS`` via the v2 adapter."""

    sig = daily_signal(inputs, method)
    legs = sizing.legs_from_signal(
        sig, inputs.pairs, scheme="equal", n_mode="active"
    )
    return v2_signals._append_flats(
        legs, v2_signals._flats_for_signal(sig, inputs.pairs)
    )


def truncate_marks(marks: pd.DataFrame, end: str = "2015-12-31") -> pd.DataFrame:
    """Marks truncated at ``end``; used to stop the stage-1 simulation."""

    out = marks.copy()
    out["date"] = pd.to_datetime(out["date"])
    return out.loc[out["date"] <= pd.Timestamp(end)].reset_index(drop=True)


def assert_stage1_only(frame: pd.DataFrame, end: str = "2015-12-31") -> None:
    """Raise if a frame contains a date after ``end``.

    Accepts a ``date`` column or a DatetimeIndex. Used on every stage-1
    artifact so the test sample cannot leak into selection.
    """

    if "date" in frame.columns:
        dates = pd.to_datetime(frame["date"])
    else:
        dates = pd.to_datetime(frame.index)
    if (dates > pd.Timestamp(end)).any():
        raise ValueError(f"stage-1 artifact contains a date after {end}")


def run_variant(
    inputs: v2_signals.V2Inputs,
    method: str = "1:1",
    settings: DailyCSettings | None = None,
    marks: pd.DataFrame | None = None,
    periods: dict[str, tuple[str | None, str | None]] | None = None,
) -> dict:
    """Run one daily variant and return its legs, result and summary tables.

    ``marks`` lets stage 1 pass a panel truncated at 2015-12-31, so no test
    P&L is computed. The signal path is built from the full causal inputs;
    only the simulation calendar and marks are truncated.
    """

    settings = settings or DailyCSettings()
    periods = periods or PERIODS
    legs = daily_legs(inputs, method)
    result = simulate.simulate(
        legs, marks if marks is not None else inputs.marks, _sim_config(settings)
    )
    performance = pd.concat(
        {
            period: report.performance_table(result, start, end)
            for period, (start, end) in periods.items()
        },
        names=["period"],
    )
    return {
        "method": method,
        "legs": legs,
        "result": result,
        "performance": performance,
        "root": report.root_table(result),
    }


def run_stage1(
    inputs: v2_signals.V2Inputs,
    methods: tuple[str, ...] = METHODS,
    settings: DailyCSettings | None = None,
) -> dict[str, dict]:
    """Run all daily variants with marks truncated at 2015-12-31."""

    settings = settings or DailyCSettings()
    marks = truncate_marks(inputs.marks)
    return {
        method: run_variant(
            inputs, method, settings, marks=marks, periods=STAGE1_PERIODS
        )
        for method in methods
    }


def forward_panel(
    inputs: v2_signals.V2Inputs,
    horizons: list[tuple[int, int]],
    marks: pd.DataFrame | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Forward spread returns on the chosen marks panel (stage-aware).

    ``end`` drops signal dates after the stage cutoff, so a truncated-marks
    stage-1 panel cannot carry future-dated rows into an artifact.
    """

    out = horizon.forward_returns(
        inputs.bt["spread"],
        marks if marks is not None else inputs.marks,
        horizons=horizons,
    )
    if end is not None:
        out = out.loc[pd.to_datetime(out["date"]) <= pd.Timestamp(end)]
    return out


def per_root_period_table(
    result: simulate.SimResult,
    capital: float,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Per-root annualised gross return, vol, Sharpe and NW t for one period.

    Zero-P&L days are included; this is the contribution of each root to the
    equal-weight portfolio, not an active-day-only Sharpe.
    """

    calendar = pd.DatetimeIndex(result.calendar)
    pnl = (
        result.by_root.pivot_table(
            index="date", columns="root", values="pnl_gross", aggfunc="sum"
        )
        .reindex(calendar)
        .fillna(0.0)
    )
    held = (
        result.by_root.pivot_table(
            index="date", columns="root", values="gross_notional", aggfunc="sum"
        )
        .reindex(calendar)
        .fillna(0.0)
    )
    pnl = pnl.loc[start:end] / capital
    active_days = (held.loc[start:end] > 0).sum()
    out = pd.DataFrame(
        {
            "ann_pct": pnl.mean() * 252 * 100,
            "vol_pct": pnl.std() * np.sqrt(252) * 100,
            "sharpe": pnl.mean() / pnl.std() * np.sqrt(252),
            "t_nw": [horizon.newey_west_t(pnl[c], 5) for c in pnl.columns],
            "active_days": active_days,
            "n_days": len(pnl),
        }
    )
    return out.sort_values("sharpe", ascending=False)


def gross_series(
    result: simulate.SimResult,
    start: str | None = None,
    end: str | None = None,
) -> pd.Series:
    """Daily gross portfolio return on the simulation calendar, sliced.

    Unlike ``report.performance_table``, this returns the raw daily series, so
    the selection and gate rules can use unrounded statistics.
    """

    return result.daily.set_index("date")["ret_gross"].loc[start:end]


def sharpe(series: pd.Series) -> float:
    """Annualised Sharpe (rf=0, 252 days); NaN when the series is constant."""

    sd = series.std()
    return float(series.mean() / sd * np.sqrt(252)) if np.isfinite(sd) and sd > 0 else float("nan")


def gross_summary(
    result: simulate.SimResult,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Validation/full gross summary used by the selection and gate rules.

    Uses the raw daily return series (not the rounded performance table) so the
    0.4 gate and the +0.05 SR-gain rule are evaluated exactly.
    """

    r = gross_series(result, start, end)
    d = result.daily.set_index("date").loc[start:end]
    return {
        "ann_ret_pct": float(r.mean() * 252 * 100),
        "ann_vol_pct": float(r.std() * np.sqrt(252) * 100),
        "sharpe": sharpe(r),
        "t_nw": float(horizon.newey_west_t(r, 5)),
        "turnover_x": float(d["turnover"].mean() * 252),
        "n_days": int(len(r)),
    }


def paired_daily_bootstrap(
    new_result: simulate.SimResult,
    current_result: simulate.SimResult,
    period: tuple[str | None, str | None] = VALIDATION_PERIOD,
    settings: DailyCSettings | None = None,
) -> dict:
    """Moving-block bootstrap of the paired daily gross-return difference.

    Both variants are simulated on the same calendar; the function raises if
    the date indexes differ rather than silently dropping dates.
    """

    settings = settings or DailyCSettings()
    new = gross_series(new_result, *period)
    current = gross_series(current_result, *period)
    if not new.index.equals(current.index):
        raise ValueError("paired bootstrap requires identical daily calendars")
    diff = (new - current).rename("diff").reset_index()
    diff["root"] = "ALL"
    summary, _draws = horizon.block_bootstrap_mean(
        diff,
        "diff",
        block=settings.block,
        n_boot=settings.n_boot,
        min_obs=252,
        seed=settings.seed,
        null=0.0,
        stat="mean",
    )
    row = summary.iloc[0]
    return {
        "mean": float(row["mean"]),
        "mean_bps": float(row["mean"]) * 1e4,
        "ci_lo": float(row["ci_lo"]),
        "ci_hi": float(row["ci_hi"]),
        "ci_lo_bps": float(row["ci_lo"]) * 1e4,
        "ci_hi_bps": float(row["ci_hi"]) * 1e4,
        "p_value": float(row["p_value"]),
        "n": int(row["n"]),
    }


def _eligible_roots(
    result: simulate.SimResult,
    settings: DailyCSettings,
    period: tuple[str | None, str | None],
) -> tuple[pd.DataFrame, pd.Series]:
    """Per-root table plus the breadth eligibility mask."""

    table = per_root_period_table(
        result, settings.capital, period[0], period[1]
    )
    eligible = (
        table["active_days"].ge(settings.min_root_active_days)
        & np.isfinite(table["sharpe"])
    )
    return table, eligible


def adoption_decision(
    sr_gain: float,
    ci_lo: float,
    breadth: float,
    settings: DailyCSettings | None = None,
) -> dict:
    """Pure three-criterion adoption rule, separated for unit testing."""

    settings = settings or DailyCSettings()
    pass_sr = bool(np.isfinite(sr_gain) and sr_gain >= settings.sr_gain)
    pass_bootstrap = bool(np.isfinite(ci_lo) and ci_lo > 0)
    pass_breadth = bool(
        np.isfinite(breadth) and breadth >= settings.breadth_threshold
    )
    return {
        "pass_sr": pass_sr,
        "pass_bootstrap": pass_bootstrap,
        "pass_breadth": pass_breadth,
        "passed": bool(pass_sr and pass_bootstrap and pass_breadth),
    }


def selection_step(
    results: dict[str, dict],
    current: str,
    new: str,
    settings: DailyCSettings | None = None,
) -> dict:
    """Apply the three sequential adoption criteria for one variant pair."""

    settings = settings or DailyCSettings()
    cur = results[current]
    new_item = results[new]
    sr_current = sharpe(gross_series(cur["result"], *VALIDATION_PERIOD))
    sr_new = sharpe(gross_series(new_item["result"], *VALIDATION_PERIOD))
    boot = paired_daily_bootstrap(
        new_item["result"], cur["result"], VALIDATION_PERIOD, settings
    )
    cur_roots, eligible = _eligible_roots(
        cur["result"], settings, VALIDATION_PERIOD
    )
    new_roots, _ = _eligible_roots(new_item["result"], settings, VALIDATION_PERIOD)
    common = cur_roots.index.intersection(new_roots.index)
    eligible = eligible.reindex(common).fillna(False).astype(bool)
    new_sr = new_roots["sharpe"].reindex(common)
    cur_sr = cur_roots["sharpe"].reindex(common)
    breadth = (
        float((new_sr.loc[eligible] > cur_sr.loc[eligible]).mean())
        if eligible.any()
        else float("nan")
    )
    decision = adoption_decision(
        sr_new - sr_current, boot["ci_lo"], breadth, settings
    )
    return {
        "current": current,
        "new": new,
        "sr_current": sr_current,
        "sr_new": sr_new,
        "sr_gain": sr_new - sr_current,
        "diff_mean_bps": boot["mean_bps"],
        "ci_lo_bps": boot["ci_lo_bps"],
        "ci_hi_bps": boot["ci_hi_bps"],
        "p_value": boot["p_value"],
        "breadth": breadth,
        "n_roots": int(eligible.sum()),
        **decision,
    }


def selection_steps(
    results: dict[str, dict],
    settings: DailyCSettings | None = None,
) -> tuple[pd.DataFrame, str]:
    """Sequential C1 -> C2 -> C3 selection; stop at the first passing variant.

    If C2 passes, C2 is selected and the C3-vs-C2 row is diagnostic only.
    If C2 fails, C3 is compared directly with C1.
    """

    settings = settings or DailyCSettings()
    step1 = selection_step(results, "1:1", "ols", settings)
    rows = [dict(step="C2 vs C1", binding=True, **step1)]
    if step1["passed"]:
        selected = "ols"
        step2 = selection_step(results, "ols", "kalman", settings)
        rows.append(dict(step="C3 vs C2", binding=False, **step2))
    else:
        step2 = selection_step(results, "1:1", "kalman", settings)
        rows.append(dict(step="C3 vs C1", binding=True, **step2))
        selected = "kalman" if step2["passed"] else "1:1"
    table = pd.DataFrame(rows)
    table["selected_after"] = selected
    return table, selected


def validation_gate(
    results: dict[str, dict],
    selected: str,
    settings: DailyCSettings | None = None,
) -> dict:
    """Validation gross-SR and breadth gate for the selected daily variant."""

    settings = settings or DailyCSettings()
    result = results[selected]["result"]
    sr = sharpe(gross_series(result, *VALIDATION_PERIOD))
    table, eligible = _eligible_roots(result, settings, VALIDATION_PERIOD)
    breadth = (
        float((table.loc[eligible, "sharpe"] > 0).mean())
        if eligible.any()
        else float("nan")
    )
    passed = bool(
        np.isfinite(sr)
        and sr >= settings.gate_sr
        and np.isfinite(breadth)
        and breadth >= settings.breadth_threshold
    )
    return {
        "selected": selected,
        "validation_sr": sr,
        "validation_breadth": breadth,
        "n_positive_roots": int((table.loc[eligible, "sharpe"] > 0).sum()),
        "n_eligible_roots": int(eligible.sum()),
        "pass_validation": passed,
        "test_read": False,
    }


def test_gate(
    result: simulate.SimResult,
    settings: DailyCSettings | None = None,
) -> dict:
    """Test direction gate for the selected variant (stage 2 only)."""

    sr = sharpe(gross_series(result, *TEST_PERIOD))
    return {"test_sr": sr, "pass_test": bool(np.isfinite(sr) and sr > 0)}



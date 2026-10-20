"""Period-sliced signal-information diagnostics for idea A.

The functions wrap ``src.horizon`` so the idea notebook can show the same
statistics for the full, train and test samples without reimplementing the
statistics.  Nothing here changes the official v2 backtest: all returns are
gross and execution-free unless a function says otherwise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import horizon

PERIODS: dict[str, tuple[str | None, str | None]] = {
    "full": (None, None),
    "train 1986-2015": (None, "2015-12-31"),
    "test 2016-2026": ("2016-01-01", None),
}


def _clean_fwd(fwd: pd.DataFrame) -> pd.DataFrame:
    """Keep only the date/root keys and forward-return columns.

    This prevents a score column such as ``target`` or ``carry_ann`` from
    colliding with the signal table when the caller passes a combined frame.
    """

    keep = ["date", "root"] + [c for c in fwd.columns if c.startswith("fwd_")]
    return fwd[keep].copy()


def slice_period(
    frame: pd.DataFrame,
    start: str | None,
    end: str | None,
) -> pd.DataFrame:
    """Rows whose ``date`` lies inside ``[start, end]`` (inclusive)."""

    dates = pd.to_datetime(frame["date"])
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= dates >= pd.Timestamp(start)
    if end is not None:
        mask &= dates <= pd.Timestamp(end)
    return frame.loc[mask].copy()


def horizon_profile_by_period(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    score_col: str = "target",
    periods: dict[str, tuple[str | None, str | None]] = PERIODS,
) -> pd.DataFrame:
    """``horizon.horizon_profile`` for each sample period.

    ``mean_bps`` is the raw signed spread return (1x, no equal-notional 0.5
    factor).  The sign and t-stat are the same as the traded equal-notional
    return; only the scale differs by two.
    """

    fwd = _clean_fwd(fwd)
    frames = []
    for label, (start, end) in periods.items():
        profile = horizon.horizon_profile(
            slice_period(fwd, start, end),
            slice_period(signal, start, end),
            score_col=score_col,
        )
        frames.append(profile.assign(period=label))
    return pd.concat(frames, ignore_index=True)


def ic_by_period(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    score_col: str = "carry_ann",
    col: str = "fwd_1_6",
    min_obs: int = 252,
    periods: dict[str, tuple[str | None, str | None]] = PERIODS,
) -> pd.DataFrame:
    """``horizon.ts_ic`` for each sample period (per-root IC plus ``ALL``)."""

    fwd = _clean_fwd(fwd)
    frames = []
    for label, (start, end) in periods.items():
        table = horizon.ts_ic(
            slice_period(fwd, start, end),
            slice_period(signal, start, end),
            col=col,
            score_col=score_col,
            min_obs=min_obs,
        )
        frames.append(table.assign(period=label))
    return pd.concat(frames, ignore_index=True)


def bins_by_period(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    score_col: str = "carry_ann",
    col: str = "fwd_1_6",
    n_bins: int = 5,
    min_history: int = 252,
    periods: dict[str, tuple[str | None, str | None]] = PERIODS,
) -> pd.DataFrame:
    """``horizon.bin_returns`` for each sample period.

    Note: the expanding percentile resets at the start of each slice, so the
    test-period bins use the test sample's own history, not the train history.
    Use the full-sample row when the bins must be strictly ex ante from 1986.
    """

    fwd = _clean_fwd(fwd)
    frames = []
    for label, (start, end) in periods.items():
        table = horizon.bin_returns(
            slice_period(fwd, start, end),
            slice_period(signal, start, end),
            col=col,
            score_col=score_col,
            n_bins=n_bins,
            min_history=min_history,
        )
        frames.append(table.assign(period=label))
    return pd.concat(frames, ignore_index=True)


def bootstrap_ic_by_period(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    score_col: str = "carry_ann",
    col: str = "fwd_1_6",
    block: int = 21,
    n_boot: int = 2000,
    min_obs: int = 252,
    seed: int = 0,
    periods: dict[str, tuple[str | None, str | None]] = PERIODS,
) -> tuple[pd.DataFrame, dict[str, dict[str, np.ndarray]]]:
    """Per-root moving-block bootstrap IC for each period.

    Returns the stacked summary table and a ``period -> root -> draws`` dict.
    """

    fwd = _clean_fwd(fwd)
    summaries = []
    draws: dict[str, dict[str, np.ndarray]] = {}
    for i, (label, (start, end)) in enumerate(periods.items()):
        summary, period_draws = horizon.block_bootstrap_ic(
            slice_period(fwd, start, end),
            slice_period(signal, start, end),
            col=col,
            score_col=score_col,
            block=block,
            n_boot=n_boot,
            min_obs=min_obs,
            seed=seed + i,
        )
        summaries.append(summary.assign(period=label))
        draws[label] = period_draws
    return pd.concat(summaries, ignore_index=True), draws


def signed_returns(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    col: str = "fwd_1_6",
) -> pd.DataFrame:
    """Per-root signed spread return in bp for the sign rule.

    Equal-notional legs give ``0.5 * target * fwd_col``.  Use ``fwd_1_2`` for a
    non-overlapping daily series (Sharpe/MDE) and ``fwd_1_6`` for the
    five-day information test.
    """

    f = fwd[["date", "root", col]].merge(
        signal[["date", "root", "target"]], on=["date", "root"], how="inner"
    )
    f = f.loc[f["target"].ne(0) & f[col].notna()].copy()
    f["signed_bps"] = 0.5 * f["target"] * f[col] * 1e4
    return f[["date", "root", "signed_bps"]]


def per_root_signed_bootstrap(
    signed: pd.DataFrame,
    block: int = 21,
    n_boot: int = 2000,
    min_obs: int = 252,
    seed: int = 0,
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Per-root moving-block bootstrap of the mean signed return (bp)."""

    return horizon.block_bootstrap_mean(
        signed,
        "signed_bps",
        block=block,
        n_boot=n_boot,
        min_obs=min_obs,
        seed=seed,
    )


def per_root_signed_bootstrap_by_period(
    signed: pd.DataFrame,
    block: int = 21,
    n_boot: int = 2000,
    min_obs: int = 252,
    seed: int = 0,
    periods: dict[str, tuple[str | None, str | None]] = PERIODS,
) -> tuple[pd.DataFrame, dict[str, dict[str, np.ndarray]]]:
    """Per-root signed-return bootstrap for each sample period."""

    summaries = []
    draws: dict[str, dict[str, np.ndarray]] = {}
    for i, (label, (start, end)) in enumerate(periods.items()):
        summary, period_draws = per_root_signed_bootstrap(
            slice_period(signed, start, end),
            block=block,
            n_boot=n_boot,
            min_obs=min_obs,
            seed=seed + i,
        )
        summaries.append(summary.assign(period=label))
        draws[label] = period_draws
    return pd.concat(summaries, ignore_index=True), draws


def period_summary(
    signed: pd.DataFrame,
    periods: dict[str, tuple[str | None, str | None]] = PERIODS,
) -> pd.DataFrame:
    """Annualised mean, vol, Sharpe, Newey-West t and days of a signed series.

    Use the non-overlapping ``fwd_1_2`` series; overlapping five-day windows
    would make the ``sqrt(252)`` Sharpe annualisation optimistic.
    """

    rows = []
    for label, (start, end) in periods.items():
        s = slice_period(signed, start, end)
        if s.empty:
            continue
        daily = s.groupby("date")["signed_bps"].mean()
        sd = daily.std()
        rows.append(
            {
                "period": label,
                "ann_ret_pct": daily.mean() * 252 / 1e4 * 100,
                "ann_vol_pct": sd * np.sqrt(252) / 1e4 * 100,
                "sharpe": daily.mean() / sd * np.sqrt(252) if sd > 0 else np.nan,
                "t_nw": horizon.newey_west_t(daily, 5),
                "n_days": len(daily),
            }
        )
    return pd.DataFrame(rows)

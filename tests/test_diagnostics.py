"""Synthetic tests for the period-sliced A information diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import diagnostics as diag


def _frame() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=8)
    rows = []
    for root, sign in (("A", 1.0), ("B", -1.0)):
        for i, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "root": root,
                    "fwd_1_2": sign * 0.001 * (i + 1),
                    "fwd_1_6": sign * 0.002 * (i + 1),
                    "target": sign,
                    "carry_ann": sign * (0.05 + 0.001 * i),
                }
            )
    return pd.DataFrame(rows)


def _periods() -> dict[str, tuple[str | None, str | None]]:
    return {
        "full": (None, None),
        "train": (None, "2020-01-06"),
        "test": ("2020-01-07", None),
    }


def test_slice_period_is_inclusive() -> None:
    frame = _frame()
    out = diag.slice_period(frame, "2020-01-03", "2020-01-07")
    assert out["date"].min() == pd.Timestamp("2020-01-03")
    assert out["date"].max() == pd.Timestamp("2020-01-07")
    assert len(out) == 2 * 3


def test_signed_returns_uses_equal_notional_factor_and_drops_zero() -> None:
    frame = _frame()
    signal = frame[["date", "root", "target"]].copy()
    out = diag.signed_returns(frame, signal, col="fwd_1_2")
    expected = 0.5 * frame["target"] * frame["fwd_1_2"] * 1e4
    assert np.allclose(out["signed_bps"], expected)
    signal.loc[0, "target"] = 0.0
    out2 = diag.signed_returns(frame, signal, col="fwd_1_2")
    assert len(out2) == len(out) - 1


def test_horizon_profile_by_period_has_all_periods_and_horizons() -> None:
    frame = _frame()
    signal = frame[["date", "root", "target", "carry_ann"]]
    out = diag.horizon_profile_by_period(frame, signal, periods=_periods())
    assert set(out["period"]) == {"full", "train", "test"}
    assert set(out["horizon"]) == {"t+1->t+2", "t+1->t+6"}
    assert len(out) == 3 * 2
    assert np.isfinite(out["mean_bps"]).all()


def test_ic_and_bins_by_period() -> None:
    frame = _frame()
    signal = frame[["date", "root", "target", "carry_ann"]]
    ic = diag.ic_by_period(
        frame, signal, score_col="carry_ann", col="fwd_1_6", min_obs=2, periods=_periods()
    )
    assert set(ic["period"]) == {"full", "train", "test"}
    assert set(ic["root"]) == {"A", "B", "ALL"}
    assert len(ic) == 3 * 3
    bins = diag.bins_by_period(
        frame,
        signal,
        score_col="carry_ann",
        col="fwd_1_6",
        n_bins=3,
        min_history=2,
        periods=_periods(),
    )
    assert set(bins["period"]) == {"full", "train", "test"}
    assert bins["bin"].between(1, 3).all()


def test_bootstrap_ic_and_signed_bootstrap_by_period() -> None:
    frame = _frame()
    signal = frame[["date", "root", "target", "carry_ann"]]
    summary, draws = diag.bootstrap_ic_by_period(
        frame,
        signal,
        score_col="carry_ann",
        col="fwd_1_6",
        block=2,
        n_boot=20,
        min_obs=2,
        periods=_periods(),
    )
    assert set(summary["period"]) == {"full", "train", "test"}
    assert set(draws) == {"full", "train", "test"}

    signed = diag.signed_returns(frame, signal, col="fwd_1_6")
    root_summary, root_draws = diag.per_root_signed_bootstrap_by_period(
        signed, block=2, n_boot=20, min_obs=2, periods=_periods()
    )
    assert set(root_summary["period"]) == {"full", "train", "test"}
    assert set(root_draws) == {"full", "train", "test"}


def test_period_summary_columns_and_rows() -> None:
    frame = _frame()
    signal = frame[["date", "root", "target"]]
    signed = diag.signed_returns(frame, signal, col="fwd_1_2")
    out = diag.period_summary(signed, periods=_periods())
    assert set(out["period"]) == {"full", "train", "test"}
    assert {"ann_ret_pct", "ann_vol_pct", "sharpe", "t_nw", "n_days"}.issubset(out.columns)
    assert (out["n_days"] > 0).all()

"""Tests for the Kalman-filter hedge ratio."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import kalman


def _panel(n: int = 120) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=n)
    far = np.linspace(100.0, 220.0, n)
    near = 2.0 * far + 0.05 * np.sin(np.arange(n))
    return pd.DataFrame(
        {"date": dates, "root": "X", "near_index": near, "far_index": far}
    )


def _params() -> kalman.KalmanHedgeParams:
    return kalman.KalmanHedgeParams(
        window=30,
        reestimate_every=10,
        q_grid=(1e-6, 1e-4, 1e-2),
    )


def test_kalman_recovers_known_slope() -> None:
    out = kalman.kalman_hedge_ratio(_panel(), _params())
    valid = out.loc[out["hedge_ratio_valid"]]
    assert not valid.empty
    assert abs(float(valid["hedge_ratio"].median()) - 2.0) < 0.05
    expected = valid["near_index"] - valid["hedge_ratio"] * valid["far_index"]
    assert np.allclose(valid["spread_index"], expected)
    assert out["kalman_is_reestimate"].any()
    assert out["kalman_observation_var"].dropna().gt(0).all()
    assert out["kalman_q"].dropna().isin(_params().q_grid).all()


def test_kalman_no_lookahead() -> None:
    panel = _panel()
    full = kalman.kalman_hedge_ratio(panel, _params())
    truncated = kalman.kalman_hedge_ratio(panel.iloc[:80], _params())
    merged = full.merge(
        truncated, on=["date", "root"], suffixes=("_full", "_truncated")
    )
    common = merged.loc[merged["hedge_ratio_full"].notna()]
    assert not common.empty
    assert np.allclose(
        common["hedge_ratio_full"],
        common["hedge_ratio_truncated"],
        equal_nan=True,
    )


def test_kalman_handles_missing_observations() -> None:
    panel = _panel()
    panel.loc[50, "near_index"] = np.nan
    panel.loc[51, "far_index"] = np.nan
    out = kalman.kalman_hedge_ratio(panel, _params())
    assert len(out) == len(panel)
    assert out.loc[out["date"].isin(panel.loc[[50, 51], "date"]), "spread_index"].isna().all()


def test_kalman_validation() -> None:
    panel = _panel(40)
    with pytest.raises(ValueError):
        kalman.kalman_hedge_ratio(
            panel, kalman.KalmanHedgeParams(window=5)
        )
    with pytest.raises(ValueError):
        kalman.kalman_hedge_ratio(
            panel, kalman.KalmanHedgeParams(reestimate_every=0)
        )
    with pytest.raises(ValueError):
        kalman.kalman_hedge_ratio(
            panel, kalman.KalmanHedgeParams(q_grid=(0.0,))
        )
    with pytest.raises(ValueError, match="duplicate"):
        kalman.kalman_hedge_ratio(
            pd.concat([panel, panel.iloc[[0]]], ignore_index=True),
            _params(),
        )

"""Tests for the A negative-result diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import a_diagnostics as ad
from src.backtest import BacktestConfig, BacktestResult


def _result() -> BacktestResult:
    d1 = pd.Timestamp("2020-01-02")
    d2 = pd.Timestamp("2020-01-03")
    positions = pd.DataFrame(
        [
            dict(date=d1, root="X", commodity="Test", sector="Test",
                 group_id="X_A_B", contract="A", units=1.0),
            dict(date=d1, root="X", commodity="Test", sector="Test",
                 group_id="X_A_B", contract="B", units=-1.0),
            dict(date=d1, root="Y", commodity="Test2", sector="Test2",
                 group_id="Y_C_D", contract="C", units=-1.0),
            dict(date=d1, root="Y", commodity="Test2", sector="Test2",
                 group_id="Y_C_D", contract="D", units=1.0),
        ]
    )
    daily = pd.DataFrame(
        [
            dict(date=d2, root="X", commodity="Test", sector="Test",
                 group_id="X_A_B", return_gross=0.01, return_net=0.01,
                 gross_notional=100.0, cost=0.0, is_cost_row=False),
            dict(date=d2, root="Y", commodity="Test2", sector="Test2",
                 group_id="Y_C_D", return_gross=-0.02, return_net=-0.02,
                 gross_notional=100.0, cost=0.0, is_cost_row=False),
        ]
    )
    portfolio = pd.DataFrame(
        [
            dict(date=d1, return_gross=0.0, return_net=0.0, cost=0.0,
                 N_t=2, net_exposure=0.0),
            dict(date=d2, return_gross=-0.005, return_net=-0.005,
                 cost=0.0005, N_t=2, net_exposure=0.0),
        ]
    )
    return BacktestResult(
        positions=positions,
        daily_returns=daily,
        portfolio_returns=portfolio,
        trades=pd.DataFrame(),
        config=BacktestConfig(),
    )


def test_direction_and_side_table() -> None:
    table = ad.side_sector_era(_result())
    side = table.loc[table["level"] == "side"].set_index("side")
    assert np.isclose(side.loc["long", "raw_mean"], 0.01)
    # Short position return -0.02, direction -1 -> raw spread return +0.02.
    assert np.isclose(side.loc["short", "raw_mean"], 0.02)
    assert np.isclose(side.loc["long", "contribution"], 0.005)
    assert np.isclose(side.loc["short", "contribution"], -0.01)
    assert np.isclose(
        table.loc[table["level"] == "cell", "contribution"].sum(),
        _result().portfolio_returns["return_gross"].sum(),
    )


def test_cost_sensitivity_is_linear() -> None:
    out = ad.cost_sensitivity(_result(), bps_values=(0.0, 5.0, 10.0, 20.0))
    assert list(out["cost_bps_per_leg"]) == [0.0, 5.0, 10.0, 20.0]
    # Higher costs must lower net annualized return; with only two synthetic
    # days the Sharpe can be flat, so only require it not to improve.
    assert out["ann_return_net"].is_monotonic_decreasing
    assert out.loc[0, "sharpe_net"] >= out.loc[3, "sharpe_net"] - 1e-9
    gross = _result().portfolio_returns["return_gross"].to_numpy()
    expected_0 = (1.0 + gross).prod() ** (252.0 / len(gross)) - 1.0
    assert np.isclose(out.loc[0, "ann_return_net"], expected_0)

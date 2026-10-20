"""Tests for the position-panel figures (synthetic results, no raw data)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import figures, plotstyle, simulate


def _positions_frame(dates: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    for date in dates:
        # XZ26 expires in Dec 2026, XF27 in Jan 2027. Lexicographically,
        # XF27 < XZ26, so a naive sort would pick the wrong (short) leg.
        rows.append(dict(
            date=date, root="X", contract="XZ26", n=10.0, mark=100.0,
            point_value=1.0, signed_notional=1000.0, gross_notional=1000.0,
            pnl=0.0,
        ))
        rows.append(dict(
            date=date, root="X", contract="XF27", n=-10.0, mark=100.0,
            point_value=1.0, signed_notional=-1000.0, gross_notional=1000.0,
            pnl=0.0,
        ))
    return pd.DataFrame(rows)


def _result(dates: pd.DatetimeIndex, calendar: pd.DatetimeIndex | None = None) -> simulate.SimResult:
    daily = pd.DataFrame({
        "date": dates,
        "gross_exposure": 0.01,
        "turnover": 0.005,
    })
    return simulate.SimResult(
        holdings=pd.DataFrame(columns=["date", "root", "contract", "n"]),
        trades=pd.DataFrame(),
        by_root=pd.DataFrame(),
        daily=daily,
        config=simulate.SimConfig(capital=1_000_000.0),
        calendar=calendar if calendar is not None else dates,
        positions=_positions_frame(dates),
    )


def setup_module() -> None:
    plotstyle.use(usetex=False)


def test_position_panel_uses_nearest_expiry_direction() -> None:
    dates = pd.DatetimeIndex(["2026-01-30", "2026-02-27"])
    res = _result(dates)
    panel = figures.position_panel(res, root_order=["X"])
    assert list(panel.index) == ["X"]
    # Nearest leg XZ26 is long; total gross is 2000 / 1m = 0.2% of capital.
    assert np.allclose(panel.loc["X"].to_numpy(), 0.2)


def test_position_panel_fills_flat_months_and_root_order() -> None:
    dates = pd.DatetimeIndex(["2026-01-30", "2026-02-27", "2026-03-31"])
    res = _result(dates[[0, 2]], calendar=dates)
    panel = figures.position_panel(res, root_order=["X"])
    assert list(panel.index) == ["X"]
    assert list(panel.columns) == list(dates)
    assert panel.loc["X", dates[0]] == 0.2
    assert panel.loc["X", dates[1]] == 0.0
    assert panel.loc["X", dates[2]] == 0.2


def test_positions_figure_smoke() -> None:
    dates = pd.DatetimeIndex(["2026-01-30", "2026-02-27"])
    fig = figures.positions(_result(dates), "test")
    assert len(fig.axes) >= 2
    plt.close(fig)

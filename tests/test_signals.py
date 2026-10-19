"""Tests for the carry signal."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import curve, signals


def _pair_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]),
            "root": ["X", "X", "X", "X"],
            "commodity": ["Test"] * 4,
            "sector": ["Test"] * 4,
            "settle_near": [102.0, 98.0, 100.0, np.nan],
            "settle_far": [100.0, 100.0, 100.0, 100.0],
            "delivery_year_near": [2020, 2020, 2020, 2020],
            "delivery_month_near": [3, 3, 3, 3],
            "delivery_year_far": [2020, 2020, 2020, 2020],
            "delivery_month_far": [4, 4, 4, 4],
            "months_between": [1.0, 1.0, 1.0, 1.0],
        }
    )


def test_carry_signal_sign_and_annualization() -> None:
    out = signals.carry_signal(_pair_frame())
    assert list(out.columns) == [
        "date", "root", "commodity", "sector",
        "spread_dollar", "carry_ann", "score", "target",
    ]
    assert out.loc[0, "spread_dollar"] == 2.0
    assert out.loc[0, "target"] == 1.0
    assert out.loc[1, "spread_dollar"] == -2.0
    assert out.loc[1, "target"] == -1.0
    expected = (2.0 / 100.0) * 365.0 / 31.0
    assert np.isclose(out.loc[0, "carry_ann"], expected)
    assert out.loc[2, "target"] == 0.0
    assert out.loc[3, "target"] == 0.0
    assert np.isnan(out.loc[3, "carry_ann"])


def test_carry_signal_negative_price_is_nan() -> None:
    frame = _pair_frame().iloc[[0]].copy()
    frame.loc[0, "settle_near"] = -37.63
    frame.loc[0, "settle_far"] = 20.43
    out = signals.carry_signal(frame)
    assert out.loc[0, "spread_dollar"] == -58.06
    assert out.loc[0, "target"] == -1.0
    assert np.isnan(out.loc[0, "carry_ann"])


def test_carry_signal_annualized_mode() -> None:
    out = signals.carry_signal(
        _pair_frame(),
        signals.CarryParams(signal="annualized"),
    )
    assert out.loc[0, "target"] == 1.0
    assert out.loc[1, "target"] == -1.0
    assert out.loc[2, "target"] == 0.0


def _spread_panel(n: int = 30, jump_index: int = 7) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=n)
    values = np.full(n, 0.5)
    values[jump_index] = 10.0
    return pd.DataFrame(
        {"date": dates, "root": "X", "spread_index": values}
    )


def _params(window: int = 10) -> signals.MeanReversionParams:
    return signals.MeanReversionParams(window=window, min_obs_frac=0.8)


def test_state_path_long_short_exit_and_flip() -> None:
    params = signals.MeanReversionParams(window=5)
    mask = np.ones(6, dtype=bool)

    long_then_exit = signals._state_path(
        np.array([0.0, -2.1, -1.0, 0.1, 0.0, 0.0]), mask, params
    )
    assert long_then_exit.tolist() == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0]

    short_then_exit = signals._state_path(
        np.array([0.0, 2.1, 1.0, -0.1, 0.0, 0.0]), mask, params
    )
    assert short_then_exit.tolist() == [0.0, -1.0, -1.0, 0.0, 0.0, 0.0]

    flip = signals._state_path(
        np.array([-2.1, 2.1, 2.5, -2.1]), mask[:4], params
    )
    assert flip.tolist() == [1.0, -1.0, -1.0, 1.0]


def test_state_path_holds_through_nan_and_ignores_non_evaluation() -> None:
    params = signals.MeanReversionParams(window=5)
    z = np.array([-2.1, np.nan, 1.0, 2.5])
    mask = np.array([True, True, False, True])
    out = signals._state_path(z, mask, params)
    assert out.tolist() == [1.0, 1.0, 1.0, -1.0]


def test_mean_reversion_signal_weekly_target_path() -> None:
    panel = _spread_panel()
    params = _params()
    trading_days = pd.DatetimeIndex(panel["date"])
    pair_grid = panel[["date", "root"]]
    signal = signals.mean_reversion_signal(
        panel, params, trading_days=trading_days, pair_grid=pair_grid
    )

    assert list(signal.columns) == [
        "date", "root", "commodity", "sector", "spread_index", "score",
        "target", "state", "evaluation_date", "is_evaluation", "z_valid",
        "window_count", "has_pair",
    ]
    weekly = curve.weekly_rebalance_dates(trading_days)
    assert set(signal.loc[signal["is_evaluation"], "date"]) == weekly

    jump_date = trading_days[7]
    jump_row = signal.loc[signal["date"].eq(jump_date)].iloc[0]
    assert jump_row["target"] == -1.0
    assert jump_row["evaluation_date"] == jump_date
    assert jump_row["z_valid"]

    held = signal.loc[
        signal["date"].between(trading_days[8], trading_days[11])
    ]
    assert held["target"].eq(-1.0).all()
    assert held["evaluation_date"].eq(jump_date).all()

    exit_date = trading_days[12]  # Friday after the jump
    exit_row = signal.loc[signal["date"].eq(exit_date)].iloc[0]
    assert exit_row["is_evaluation"]
    assert exit_row["target"] == 0.0


def test_mean_reversion_signal_no_pair_dates_have_zero_target() -> None:
    panel = _spread_panel()
    params = _params()
    trading_days = pd.DatetimeIndex(panel["date"])
    pair_grid = panel.loc[
        ~panel["date"].isin(trading_days[10:12]), ["date", "root"]
    ]
    signal = signals.mean_reversion_signal(
        panel, params, trading_days=trading_days, pair_grid=pair_grid
    )
    gap = signal.loc[signal["date"].isin(trading_days[10:12])]
    assert gap["target"].eq(0.0).all()
    assert not gap["has_pair"].any()


def test_mean_reversion_signal_truncation_does_not_change_past() -> None:
    panel = _spread_panel()
    params = _params()
    trading_days = pd.DatetimeIndex(panel["date"])
    pair_grid = panel[["date", "root"]]
    full = signals.mean_reversion_signal(
        panel, params, trading_days=trading_days, pair_grid=pair_grid
    )
    cutoff = trading_days[20]
    truncated = signals.mean_reversion_signal(
        panel.loc[panel["date"].le(cutoff)],
        params,
        trading_days=trading_days,
        pair_grid=pair_grid,
    )
    past_full = full.loc[full["date"].le(cutoff), "target"].to_numpy()
    past_truncated = truncated.loc[
        truncated["date"].le(cutoff), "target"
    ].to_numpy()
    np.testing.assert_array_equal(past_full, past_truncated)


def test_signal_weekly_dates_cover_later_start_calendar() -> None:
    panel = _spread_panel(n=60)
    params = _params()
    trading_days = pd.DatetimeIndex(panel["date"])
    signal = signals.mean_reversion_signal(
        panel, params, trading_days=trading_days, pair_grid=panel[["date", "root"]]
    )
    full_weekly = set(signal.loc[signal["is_evaluation"], "date"])
    later_days = trading_days[trading_days >= pd.Timestamp("2020-02-03")]
    later_weekly = curve.weekly_rebalance_dates(later_days)
    assert later_weekly.issubset(full_weekly)


def test_mean_reversion_signal_parameter_guards() -> None:
    panel = _spread_panel()
    trading_days = pd.DatetimeIndex(panel["date"])
    pair_grid = panel[["date", "root"]]

    with pytest.raises(ValueError):
        signals.mean_reversion_signal(
            panel,
            signals.MeanReversionParams(window=1),
            trading_days=trading_days,
            pair_grid=pair_grid,
        )
    with pytest.raises(ValueError):
        signals.mean_reversion_signal(
            panel,
            signals.MeanReversionParams(entry_z=0.0),
            trading_days=trading_days,
            pair_grid=pair_grid,
        )
    with pytest.raises(ValueError):
        signals.mean_reversion_signal(
            panel,
            signals.MeanReversionParams(exit_z=2.0),
            trading_days=trading_days,
            pair_grid=pair_grid,
        )
    with pytest.raises(ValueError):
        signals.mean_reversion_signal(
            panel,
            signals.MeanReversionParams(min_obs_frac=0.0),
            trading_days=trading_days,
            pair_grid=pair_grid,
        )
    with pytest.raises(NotImplementedError):
        signals.mean_reversion_signal(
            panel,
            signals.MeanReversionParams(evaluation="daily"),
            trading_days=trading_days,
            pair_grid=pair_grid,
        )
    with pytest.raises(ValueError):
        signals.mean_reversion_signal(
            panel,
            signals.MeanReversionParams(evaluation="monthly"),
            trading_days=trading_days,
            pair_grid=pair_grid,
        )

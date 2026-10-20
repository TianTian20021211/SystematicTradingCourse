"""Tests for the monthly curve-momentum (basis-momentum) signal."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import signals


def _dates(start: str = "2020-01-01", end: str = "2022-12-30") -> pd.DatetimeIndex:
    return pd.bdate_range(start, end)


def _panels(
    dates: pd.DatetimeIndex,
    roots: tuple[str, ...] = ("X",),
    near_return: float = 0.001,
    far_return: float = 0.0005,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for root in roots:
        for rank, value in ((1, near_return), (2, far_return)):
            for date in dates:
                rows.append(
                    {
                        "date": date,
                        "root": root,
                        "rank": rank,
                        "ret_rank": value,
                        "negative_price": False,
                    }
                )
    pair_rows = []
    for date in dates:
        for root in roots:
            pair_rows.append(
                {
                    "date": date,
                    "root": root,
                    "commodity": "Test",
                    "sector": "Test",
                    "rank_near": 1,
                    "rank_far": 2,
                }
            )
    returns = pd.DataFrame(rows)
    pair = pd.DataFrame(pair_rows)
    return pair, returns


def test_rank_return_index_compounds_without_jumping_on_missing() -> None:
    dates = pd.bdate_range("2020-01-01", periods=4)
    returns = pd.DataFrame(
        {
            "date": dates,
            "root": "X",
            "rank": 1,
            "ret_rank": [0.01, np.nan, -0.02, 0.03],
            "negative_price": [False, False, False, False],
        }
    )
    out = signals._rank_return_index(returns, pd.DatetimeIndex(dates))
    assert out["rank_index"].tolist() == pytest.approx(
        [1.01, 1.01, 0.9898, 1.019494]
    )
    assert out["valid_cum"].tolist() == [1, 1, 2, 3]
    assert out["bad_cum"].tolist() == [0, 0, 0, 0]


def test_signal_builds_daily_forward_filled_target() -> None:
    dates = _dates("2020-01-01", "2022-12-30")
    pair, returns = _panels(dates)
    signal = signals.curve_momentum_signal(pair, returns)

    assert set(signal["target"].unique()) <= {-1.0, 0.0, 1.0}
    assert signal.groupby("root").size().eq(len(dates)).all()
    changes = signal.sort_values("date").groupby("root")["target"].diff().fillna(0)
    assert changes.ne(0).sum() > 0
    assert signal.loc[changes.ne(0), "is_signal_date"].all()

    # The near leg always earns more, so once the 12-month window is valid the
    # target is +1.
    valid = signal.loc[signal["is_signal_date"] & signal["score"].notna()]
    assert valid["target"].eq(1.0).all()


def test_signal_flips_sign_after_formation_window() -> None:
    dates = _dates("2020-01-01", "2020-09-30")
    pair, returns = _panels(dates)
    switch = pd.Timestamp("2020-05-01")
    near = returns["rank"].eq(1)
    returns.loc[near & returns["date"].ge(switch), "ret_rank"] = -0.001

    signal = signals.curve_momentum_signal(
        pair,
        returns,
        signals.CurveMomentumParams(formation_months=2),
    )
    by_date = signal.set_index("date")

    assert by_date.loc[pd.Timestamp("2020-04-30"), "target"] == 1.0
    assert by_date.loc[pd.Timestamp("2020-06-30"), "target"] == -1.0
    assert by_date.loc[pd.Timestamp("2020-04-30"), "score"] > 0
    assert by_date.loc[pd.Timestamp("2020-06-30"), "score"] < 0


def test_signal_requires_minimum_observations() -> None:
    dates = _dates("2020-01-01", "2021-12-31")
    pair, returns = _panels(dates)
    # Drop 30% of returns for both legs: every third observation is missing.
    missing = np.arange(len(dates)) % 3 == 0
    returns = returns.loc[
        ~returns["date"].isin(pd.DatetimeIndex(dates)[missing])
    ].reset_index(drop=True)

    signal = signals.curve_momentum_signal(pair, returns)
    signal_dates = signal.loc[signal["is_signal_date"]]
    assert signal_dates["score"].isna().all()
    assert signal_dates["target"].eq(0.0).all()


def test_signal_negative_price_invalidates_window_then_recovers() -> None:
    dates = _dates("2020-01-01", "2023-12-29")
    pair, returns = _panels(dates)
    bad_date = pd.Timestamp("2021-04-20")
    returns.loc[
        returns["rank"].eq(1) & returns["date"].eq(bad_date), "negative_price"
    ] = True

    signal = signals.curve_momentum_signal(pair, returns)
    signal_dates = signal.loc[signal["is_signal_date"]].set_index("date")

    # Every month-end whose 12-month window contains the bad date is invalid.
    assert pd.isna(signal_dates.loc["2022-03-31", "score"])
    assert pd.isna(signal_dates.loc["2021-04-30", "score"])

    # Once the window has moved past the bad date, the signal recovers.
    assert pd.notna(signal_dates.loc["2022-05-31", "score"])
    assert signal_dates.loc["2022-05-31", "target"] == 1.0


def test_signal_ret_below_minus_one_invalidates_window() -> None:
    dates = _dates("2020-01-01", "2022-12-30")
    pair, returns = _panels(dates)
    bad_date = pd.Timestamp("2021-04-20")
    returns.loc[
        returns["rank"].eq(1) & returns["date"].eq(bad_date), "ret_rank"
    ] = -2.0

    signal = signals.curve_momentum_signal(pair, returns)
    signal_dates = signal.loc[signal["is_signal_date"]].set_index("date")
    assert pd.isna(signal_dates.loc["2021-04-30", "score"])
    assert pd.notna(signal_dates.loc["2022-05-31", "score"])


def test_signal_forward_fill_survives_mid_month_pair_change() -> None:
    dates = _dates("2020-01-01", "2022-12-30")
    pair, returns = _panels(dates)
    # Add a third rank so the pair can move from 1-2 to 2-3.
    extra = returns.loc[returns["rank"].eq(2)].copy()
    extra["rank"] = 3
    extra["ret_rank"] = 0.0003
    returns = pd.concat([returns, extra], ignore_index=True)
    change_date = pd.Timestamp("2021-06-15")
    pair.loc[pair["date"].ge(change_date), "rank_near"] = 2
    pair.loc[pair["date"].ge(change_date), "rank_far"] = 3

    signal = signals.curve_momentum_signal(pair, returns)
    around = signal.loc[
        (signal["date"] >= change_date - pd.Timedelta(days=3))
        & (signal["date"] <= change_date + pd.Timedelta(days=3))
    ]
    assert around["target"].nunique() == 1
    assert around["target"].iloc[0] in {-1.0, 0.0, 1.0}


def test_signal_missing_month_resets_to_zero() -> None:
    dates = _dates("2020-01-01", "2020-06-30")
    pair, returns = _panels(dates)
    march = pair["date"].dt.to_period("M").eq(pd.Period("2020-03", freq="M"))
    pair = pair.loc[~march].reset_index(drop=True)

    signal = signals.curve_momentum_signal(
        pair,
        returns,
        signals.CurveMomentumParams(formation_months=2),
    )
    by_date = signal.set_index("date")

    # March has no pair: the global March month-end is an explicit zero.
    assert by_date.loc[pd.Timestamp("2020-03-31"), "is_signal_date"]
    assert by_date.loc[pd.Timestamp("2020-03-31"), "target"] == 0.0
    assert pd.isna(by_date.loc[pd.Timestamp("2020-03-31"), "score"])
    assert by_date.loc["2020-03-31":"2020-04-29", "target"].eq(0.0).all()

    # April has a pair and the signal resumes normally.
    assert by_date.loc[pd.Timestamp("2020-04-30"), "target"] == 1.0


def test_signal_does_not_look_ahead() -> None:
    dates = _dates("2020-01-01", "2022-12-30")
    pair, returns = _panels(dates)
    cutoff = pd.Timestamp("2021-06-30")
    full = signals.curve_momentum_signal(pair, returns, trading_days=dates)
    truncated = signals.curve_momentum_signal(
        pair.loc[pair["date"].le(cutoff)],
        returns.loc[returns["date"].le(cutoff)],
        trading_days=dates,
    )
    past_full = full.loc[full["date"].le(cutoff), "target"].to_numpy()
    past_truncated = truncated.loc[truncated["date"].le(cutoff), "target"].to_numpy()
    np.testing.assert_array_equal(past_full, past_truncated)


def test_signal_parameter_guards() -> None:
    dates = _dates("2020-01-01", "2020-12-31")
    pair, returns = _panels(dates)
    with pytest.raises(ValueError):
        signals.curve_momentum_signal(
            pair, returns, signals.CurveMomentumParams(formation_months=0)
        )
    with pytest.raises(ValueError):
        signals.curve_momentum_signal(
            pair, returns, signals.CurveMomentumParams(min_obs_frac=0.0)
        )
    with pytest.raises(ValueError):
        signals.curve_momentum_signal(
            pair, returns, signals.CurveMomentumParams(min_obs_frac=1.5)
        )

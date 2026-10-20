"""Unit tests for the daily C audit helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import c_daily


def test_adoption_decision_requires_all_three_criteria() -> None:
    settings = c_daily.DailyCSettings()
    ok = c_daily.adoption_decision(0.10, 0.01, 0.70, settings)
    assert ok["passed"]
    assert ok["pass_sr"] and ok["pass_bootstrap"] and ok["pass_breadth"]

    # Each criterion alone is not enough.
    assert not c_daily.adoption_decision(0.01, 0.01, 0.70, settings)["passed"]
    assert not c_daily.adoption_decision(0.10, -0.01, 0.70, settings)["passed"]
    assert not c_daily.adoption_decision(0.10, 0.01, 0.50, settings)["passed"]


def test_truncate_marks_and_stage1_guard() -> None:
    marks = pd.DataFrame(
        {
            "date": pd.to_datetime(["2015-12-30", "2015-12-31", "2016-01-04"]),
            "root": ["X", "X", "X"],
            "value": [1.0, 2.0, 3.0],
        }
    )
    stage1 = c_daily.truncate_marks(marks)
    assert stage1["date"].max() == pd.Timestamp("2015-12-31")
    assert len(stage1) == 2

    c_daily.assert_stage1_only(stage1)
    with pytest.raises(ValueError):
        c_daily.assert_stage1_only(marks)


def test_gross_series_and_sharpe() -> None:
    dates = pd.bdate_range("2020-01-01", periods=5)
    daily = pd.DataFrame(
        {
            "date": dates,
            "ret_gross": [0.01, -0.01, 0.02, 0.0, -0.02],
            "turnover": [0.0] * 5,
        }
    )
    # Minimal object with the attributes gross_series/sharpe use.
    class _Result:
        pass

    result = _Result()
    result.daily = daily
    series = c_daily.gross_series(result)
    assert series.index.equals(pd.DatetimeIndex(dates))
    assert np.isclose(c_daily.sharpe(series), series.mean() / series.std() * np.sqrt(252))
    summary = c_daily.gross_summary(result)
    assert np.isclose(summary["sharpe"], c_daily.sharpe(series))
    assert summary["n_days"] == 5

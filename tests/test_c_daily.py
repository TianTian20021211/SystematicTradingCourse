"""Unit tests for the daily C audit helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import c_daily, sizing, simulate


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


def _synthetic_item(method: str) -> dict:
    dates = pd.bdate_range("2020-01-01", periods=4)
    signal = pd.DataFrame(
        {
            "date": dates,
            "root": "X",
            "score": [0.5, -0.5, 1.0, 1.0],
            "target": [0.0, 1.0, 1.0, 0.0],
            "is_evaluation": True,
            "has_pair": True,
            "spread_index": [1.0, 1.1, 1.2, 1.1],
            "state": [0.0, 1.0, 1.0, 0.0],
        }
    )
    if method != "1:1":
        signal["hedge_ratio"] = [np.nan, 1.0, 1.0, 1.0]
        signal["hedge_ratio_valid"] = [False, True, True, True]
    legs = pd.DataFrame(
        {
            "date": [dates[1]],
            "root": ["X"],
            "group_id": ["0"],
            "contract": ["XZ20"],
            "units": [1.0],
            "budget": [0.5],
            "target": [1.0],
            "resize_key": [""],
        }
    )
    daily = pd.DataFrame(
        {
            "date": dates,
            "ret_gross": [0.0, 0.01, -0.01, 0.0],
            "ret_net_spread": [0.0, 0.01, -0.01, 0.0],
            "ret_net_fee": [0.0, 0.01, -0.01, 0.0],
            "ret_net_all": [0.0, 0.01, -0.01, 0.0],
            "turnover": [0.0, 0.5, 0.0, 0.5],
            "gross_exposure": [0.0, 0.5, 0.5, 0.0],
        }
    )
    positions = pd.DataFrame(
        {
            "date": [dates[1], dates[2]],
            "root": ["X", "X"],
            "contract": ["XZ20", "XZ20"],
            "n": [1.0, 1.0],
            "mark": [10.0, 11.0],
            "point_value": [1.0, 1.0],
            "signed_notional": [10.0, 11.0],
            "gross_notional": [10.0, 11.0],
            "pnl": [0.0, 1.0],
        }
    )
    performance = pd.DataFrame(
        {"layer": ["gross"], "ann_ret_pct": [1.0]},
        index=pd.MultiIndex.from_tuples([("full", 0)], names=["period", None]),
    )
    root = pd.DataFrame(
        {"gross_pct_yr": [1.0]}, index=pd.Index(["X"], name="root")
    )
    result = type(
        "Result",
        (),
        {"daily": daily, "positions": positions},
    )()
    return {
        "method": method,
        "signal": signal,
        "legs": legs,
        "result": result,
        "performance": performance,
        "root": root,
    }


@pytest.mark.parametrize(
    ("method", "name"),
    [("1:1", "c1"), ("ols", "c2"), ("kalman", "c3")],
)
def test_save_variant_artifacts_round_trip(tmp_path, method: str, name: str) -> None:
    item = _synthetic_item(method)
    paths = c_daily.save_variant_artifacts(item, tmp_path)
    assert all(path.exists() for path in paths.values())

    signal = pd.read_parquet(paths["signal"])
    expected_columns = (
        c_daily.HEDGE_SIGNAL_COLUMNS
        if method != "1:1"
        else c_daily.SIGNAL_COLUMNS
    )
    assert list(signal.columns) == expected_columns
    assert list(pd.read_parquet(paths["legs"]).columns) == sizing.LEG_COLUMNS
    assert list(pd.read_parquet(paths["positions"]).columns) == simulate.POSITION_COLUMNS
    assert list(pd.read_csv(paths["daily"]).columns) == list(item["result"].daily.columns)

    loaded = c_daily.load_variant_artifacts(name, tmp_path)
    assert loaded["method"] == method
    assert loaded["result"].config.capital == 10_000_000.0
    assert loaded["result"].calendar.equals(pd.DatetimeIndex(item["result"].daily["date"]))
    pd.testing.assert_frame_equal(loaded["positions"], item["result"].positions)
    assert {"period", "layer"}.issubset(loaded["performance"].columns)


def test_full_read_guard(tmp_path) -> None:
    marker = tmp_path / "test_readonce.json"

    with pytest.raises(ValueError, match="confirm-read-once"):
        c_daily.check_full_read_allowed(marker, confirm_read_once=False)
    c_daily.check_full_read_allowed(marker, confirm_read_once=True)

    marker.write_text("{}")
    with pytest.raises(ValueError, match="already read"):
        c_daily.check_full_read_allowed(marker, confirm_read_once=True)
    c_daily.check_full_read_allowed(marker, confirm_read_once=True, force=True)

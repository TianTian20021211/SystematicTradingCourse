"""Tests for the carry signal."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import signals


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

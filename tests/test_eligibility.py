"""Tests for ex-ante K-only eligibility and pair selection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import curve


def _eligibility_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-02"] * 6),
            "root": ["X"] * 6,
            "rank": [1, 1, 1, 1, 1, 1],
            "contract_code": ["A", "B", "C", "D", "E", np.nan],
            "settle": [100.0, 100.0, 100.0, 100.0, np.nan, 100.0],
            "days_to_delivery_start": [5, 4, np.nan, 5, 5, 5],
            "days_to_last_trading": [0, 100, 100, np.nan, 100, 100],
            "delivery_year": [2020] * 6,
            "delivery_month": [3] * 6,
        }
    )


def test_k_only_eligibility_ignores_last_trade_proxy() -> None:
    out = curve.add_eligibility(_eligibility_frame(), d=None, k=5)
    reasons = out["eligibility_reason"].tolist()
    assert reasons[0] == "eligible"       # exactly 5 sessions is eligible
    assert reasons[1] == "delivery_buffer"
    assert reasons[2] == "missing_calendar"
    assert reasons[3] == "eligible"       # NaN last-trade is ignored with d=None
    assert reasons[4] == "missing_price"
    assert reasons[5] == "missing_code"


def test_d_equals_five_is_not_k_only() -> None:
    out = curve.add_eligibility(_eligibility_frame(), d=5, k=5)
    reasons = out["eligibility_reason"].tolist()
    assert reasons[0] == "expiry_buffer"  # requires > 5 sessions
    assert reasons[3] == "missing_calendar"


def _rank_frame() -> pd.DataFrame:
    dates = pd.to_datetime(["2020-01-02", "2020-01-03"])
    rows = []
    for date in dates:
        for rank, code, settle, last in [
            (1, "A", 100.0, 0),
            (2, "B", 99.0, 100),
            (3, "C", 98.0, 100),
        ]:
            rows.append(
                {
                    "date": date,
                    "root": "X",
                    "commodity": "Test",
                    "sector": "Test",
                    "exchange": "TEST",
                    "rank": rank,
                    "contract_code": code,
                    "settle": settle,
                    "delivery_year": 2020,
                    "delivery_month": 3,
                    "expiry_id": 202003,
                    "days_to_delivery_start": 5,
                    "days_to_last_trading": last,
                }
            )
    return pd.DataFrame(rows)


def test_k_only_pair_selection_keeps_m1_m2() -> None:
    k5 = curve.select_pairs(_rank_frame(), d=None, k=5)
    d10 = curve.select_pairs(_rank_frame(), d=10, k=5)
    assert len(k5) == 2
    assert set(k5["pair_rank_mix"]) == {"M1-M2"}
    assert len(d10) == 2
    assert set(d10["pair_rank_mix"]) == {"M2-M3"}


def test_pair_selection_truncation_invariance() -> None:
    panel = _rank_frame()
    cutoff = pd.Timestamp("2020-01-02")
    full = curve.select_pairs(panel, d=None, k=5)
    truncated = curve.select_pairs(
        panel.loc[panel["date"] <= cutoff], d=None, k=5
    )
    left = full.loc[full["date"] == cutoff].reset_index(drop=True)
    right = truncated.loc[truncated["date"] == cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)

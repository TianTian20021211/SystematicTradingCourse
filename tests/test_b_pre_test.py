"""Tests for the cheap B pre-test."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import b_pre_test as b


def _rank_pair() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(["2020-01-02", "2020-01-03"])
    rows = []
    for date in dates:
        for rank, code, settle, month in [
            (1, "P1", 104.0, 3),
            (2, "P2", 102.0, 4),
            (3, "P3", 100.0, 5),
            (4, "P4", 99.0, 6),
        ]:
            rows.append(
                dict(
                    date=date, root="X", commodity="Test", sector="Test",
                    rank=rank, contract_code=code, settle=settle,
                    delivery_year=2020, delivery_month=month,
                )
            )
    rank = pd.DataFrame(rows)
    pair = pd.DataFrame(
        [
            dict(date=date, root="X", commodity="Test", sector="Test",
                 contract_near="P1", contract_far="P2")
            for date in dates
        ]
    )
    return rank, pair


def test_adjacent_carries_and_high_low_legs() -> None:
    rank, pair = _rank_pair()
    carries = b.build_adjacent_carries(rank)
    assert len(carries) == 6
    assert set(carries["rank_near"]) == {1, 2, 3}

    targets = b.build_b_targets(rank, pair)
    assert set(targets["group_id"]) == {"X_P1_P2"}
    units = targets.set_index("contract")["units"].to_dict()
    # High carry M2-M3, low M3-M4 -> long P2, short 2 P3, long P4.
    assert units["P2"] == 1.0
    assert units["P3"] == -2.0
    assert units["P4"] == 1.0
    # Main-pair near leg is retained with zero units for engine validation.
    assert units["P1"] == 0.0
    legs = targets.set_index("contract")["leg"].to_dict()
    assert legs["P1"] == "near"
    assert legs["P2"] == "far"
    assert legs["P3"] == "extra"


def test_decision_rule() -> None:
    def summary(gross: float, net: float) -> pd.DataFrame:
        return pd.DataFrame(
            [
                dict(period="full", sharpe_gross=gross, sharpe_net=net),
                dict(period="test", sharpe_gross=gross, sharpe_net=net),
            ]
        )

    assert b.should_skip_b(summary(0.10, 0.05))          # gross < 0.2
    assert b.should_skip_b(summary(0.30, -0.01))         # net <= 0
    assert not b.should_skip_b(summary(0.30, 0.10))      # clears both

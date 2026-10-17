from pathlib import Path

import pandas as pd

from src.load import build_rank_panel, read_commodity_metadata, read_raw_wide

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_wide.csv"


def _panel():
    raw = read_raw_wide(FIXTURE, expected_tickers=8)
    return build_rank_panel(raw, read_commodity_metadata())


def test_rolls_are_simultaneous_across_four_ranks():
    panel = _panel()
    roll_dates = panel.loc[panel.is_roll, "date"].unique()
    assert len(roll_dates) == 1
    roll_date = pd.Timestamp(roll_dates[0])

    for root, group in panel.loc[panel.date.eq(roll_date)].groupby("root"):
        assert sorted(group.loc[group.is_roll, "rank"].tolist()) == [1, 2, 3, 4]


def test_rank_contract_order_is_monotonic():
    panel = _panel()
    for (root, day), group in panel.dropna(subset=["contract_code"]).groupby(["root", "date"]):
        ordered = group.sort_values("rank")["expiry_id"].tolist()
        assert ordered == sorted(ordered)
        assert len(ordered) == len(set(ordered))


def test_first_observation_is_not_a_roll():
    panel = _panel()
    first = panel.sort_values(["root", "rank", "date"]).groupby(["root", "rank"]).head(1)
    assert not first["is_roll"].any()


def test_negative_price_is_flagged():
    panel = _panel()
    row = panel.loc[panel.negative_price]
    assert len(row) == 1
    assert row.iloc[0]["settle"] == -1.0
    assert row.iloc[0]["root"] == "CL"
    assert row.iloc[0]["rank"] == 1

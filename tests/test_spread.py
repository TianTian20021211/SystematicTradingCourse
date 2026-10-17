import numpy as np
import pandas as pd

from pathlib import Path

from src import qa
from src.curve import add_eligibility, add_spreads, select_pairs
from src.load import build_rank_panel, read_commodity_metadata, read_raw_wide
from src.panel import (
    build_contract_panel,
    build_return_panel,
    enrich_rank_panel,
)

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_wide.csv"


def _fixture_panels():
    raw = read_raw_wide(FIXTURE, expected_tickers=8)
    rank = build_rank_panel(raw, read_commodity_metadata())
    contract = build_contract_panel(rank)
    returns = build_return_panel(rank, contract)
    enriched = enrich_rank_panel(rank, contract)
    return rank, contract, returns, enriched


def test_contract_and_return_panels():
    rank, contract, returns, _ = _fixture_panels()
    assert len(contract) == 95  # one rank row has a missing contract code
    qa.assert_unique_contract_date(contract)
    qa.assert_rank_monotonic(rank)
    qa.assert_return_mapping(returns)
    qa.assert_contract_calendar(contract)
    assert contract.contract_key.nunique() == 10

    roll_date = pd.Timestamp("2020-01-09")
    row = returns.loc[
        returns.date.eq(roll_date)
        & returns.root.eq("CL")
        & returns["rank"].eq(1)
    ].iloc[0]
    assert row["contract_code"] == "CLH20"
    # New M1 CLH20: 61.4 on Jan 8 (as M2) -> 62.0 on Jan 9.
    assert np.isclose(row["ret_rank"], 62.0 / 61.4 - 1)
    # Naive M1 diff uses the old contract CLG20 (60.4) and is wrong.
    assert not np.isclose(row["ret_naive"], row["ret_rank"])


def test_eligibility_and_pair_selection():
    _, _, _, enriched = _fixture_panels()
    pairs = select_pairs(enriched, d=10, k=5)
    assert not pairs.empty
    assert pairs["rank_far"].eq(pairs["rank_near"] + 1).all()
    assert pairs["pair_rank_mix"].isin(["M1-M2", "M2-M3"]).all()

    # No eligible contract may be inside its delivery month.
    eligible_panel = add_eligibility(enriched, d=10, k=5)
    eligible = eligible_panel.loc[eligible_panel["eligible"]]
    assert not eligible["in_delivery_month"].any()

    # D=10 on this short fixture forces M1 out; M2-M3 remains.
    assert pairs["pair_rank_mix"].eq("M2-M3").all()


def test_spread_definitions_and_negative_price():
    frame = pd.DataFrame(
        {
            "settle_near": [10.0, -1.0, 0.0],
            "settle_far": [9.0, 2.0, 2.0],
            "expiry_id_near": [1, 1, 1],
            "expiry_id_far": [2, 2, 2],
        }
    )
    out = add_spreads(frame)
    assert out.loc[0, "spread_dollar"] == 1.0
    assert np.isclose(out.loc[0, "spread_log"], np.log(10.0) - np.log(9.0))
    assert np.isnan(out.loc[1, "spread_log"])
    assert np.isnan(out.loc[2, "spread_log"])
    assert out.loc[1, "negative_price"]
    assert out.loc[2, "negative_price"]
    assert out["months_between"].eq(1).all()

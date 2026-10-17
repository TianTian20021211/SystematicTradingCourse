import numpy as np
import pandas as pd

from pathlib import Path

from src import qa
from src.curve import add_eligibility, add_spreads, build_pair_episodes, select_pairs
from src.load import build_rank_panel, read_commodity_metadata, read_raw_wide
from src.panel import (
    build_adjacent_pairs,
    build_contract_panel,
    build_return_panel,
    build_universe,
    enrich_rank_panel,
    liquidity_summary,
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


def test_pair_episodes_are_additive():
    dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08"])
    panel = pd.DataFrame(
        {
            "date": dates,
            "root": ["A"] * 5,
            "contract_near": ["X", "X", "X", "Y", "Y"],
            "contract_far": ["Z", "Z", "Z", "W", "W"],
            "pair_rank_mix": ["M1-M2"] * 5,
            "spread_dollar": [1.0, 2.0, 4.0, 5.0, 6.0],
        }
    )
    episodes = build_pair_episodes(panel)
    assert len(episodes) == 2
    assert episodes.loc[0, "holding_days"] == 3
    assert episodes.loc[0, "entry_spread"] == 1.0
    assert episodes.loc[0, "exit_spread"] == 4.0
    assert episodes.loc[0, "spread_change"] == 3.0
    assert episodes.loc[1, "holding_days"] == 2
    assert episodes.loc[1, "spread_change"] == 1.0


def test_adjacent_pairs_include_main_pair():
    _, _, _, enriched = _fixture_panels()
    adjacent = build_adjacent_pairs(enriched, d=10, k=5)
    main = select_pairs(enriched, d=10, k=5)
    assert not adjacent.empty
    assert adjacent["rank_far"].eq(adjacent["rank_near"] + 1).all()
    assert int(adjacent["is_main_pair"].sum()) == len(main)
    assert set(adjacent["pair_rank_mix"]).issubset({"M1-M2", "M2-M3", "M3-M4"})


def test_universe_liquidity_and_thresholds():
    dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
    # Two contracts per leg; simple volumes/OI.
    contract = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "root": ["A"] * 6,
            "contract_code": ["X"] * 3 + ["Z"] * 3,
            "volume": [6_000, 7_000, 8_000, 5_000, 6_000, 7_000],
            "open_interest": [20_000, 21_000, 22_000, 15_000, 16_000, 17_000],
        }
    )
    rank = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "root": ["A"] * 6,
            "rank": [1] * 3 + [2] * 3,
            "volume": [6_000, 7_000, 8_000, 5_000, 6_000, 7_000],
            "open_interest": [20_000, 21_000, 22_000, 15_000, 16_000, 17_000],
        }
    )
    spread = pd.DataFrame(
        {
            "date": dates,
            "root": ["A"] * 3,
            "rank_near": [1] * 3,
            "rank_far": [2] * 3,
            "contract_near": ["X"] * 3,
            "contract_far": ["Z"] * 3,
            "pair_rank_mix": ["M1-M2"] * 3,
        }
    )
    universe = build_universe(
        spread, contract, rank, thresholds=(1_000, 5_000), window=1, min_obs=1
    )
    assert universe["liq_volume_pair"].tolist() == [5_000, 6_000, 7_000]
    assert universe["liq_oi_pair"].tolist() == [15_000, 16_000, 17_000]
    assert universe["pass_vol_5k"].all()
    summary = liquidity_summary(universe, thresholds=(1_000, 5_000))
    assert summary.loc[summary.threshold.eq(5_000), "pass_volume_days"].iloc[0] == 3


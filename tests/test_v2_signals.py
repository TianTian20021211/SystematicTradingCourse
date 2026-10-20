"""Tests for the v2 signal adapters."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import marks, panel, v2_signals


def _rank_fixture() -> pd.DataFrame:
    # Ten sessions so the K=5 delivery buffer is satisfied (the calendar
    # distance counts observed sessions, not calendar days).
    dates = pd.bdate_range("2020-01-02", periods=10)
    rows = []
    for date in dates:
        for rank, code, settle, month in [
            (1, "P1", 104.0, 3),
            (2, "P2", 102.0, 4),
            (3, "P3", 100.0, 5),
            (4, "P4", 99.0, 6),
        ]:
            rows.append(dict(
                date=date, root="X", commodity="Test", sector="Test",
                exchange="TEST", rank=rank, contract_code=code, settle=settle,
                delivery_year=2020, delivery_month=month,
                volume=1000.0, open_interest=100.0,
            ))
    return pd.DataFrame(rows)


def _synthetic_marks(rank: pd.DataFrame) -> pd.DataFrame:
    contract = panel.build_contract_panel(rank)
    if "stale" not in contract.columns:
        contract = contract.assign(stale=False)
    specs = pd.DataFrame(
        {"point_value_usd": [1.0], "tick_size": [0.01]},
        index=pd.Index(["X"], name="root"),
    )
    return marks.build_marks(contract, specs)


def _variant_inputs(rank: pd.DataFrame) -> v2_signals.V2Inputs:
    return v2_signals.V2Inputs(
        bt={"rank": rank, "contract": panel.build_contract_panel(rank)},
        marks=_synthetic_marks(rank),
        pairs=pd.DataFrame(),
    )


def test_flip_legs_negates_active_units_only() -> None:
    rank = _rank_fixture()
    inputs = _variant_inputs(rank)
    legs = v2_signals.b_legs(inputs, rank)
    flipped = v2_signals.flip_legs(legs)
    last_legs = legs.loc[legs["date"] == legs["date"].max()]
    last_flip = flipped.loc[flipped["date"] == flipped["date"].max()]
    assert last_flip.set_index("contract")["units"].to_dict() == {
        "P2": -1.0, "P3": 2.0, "P4": -1.0,
    }
    assert np.allclose(
        last_flip.set_index("contract")["units"],
        -last_legs.set_index("contract")["units"],
    )


def test_b_flip_and_static_legs_on_eligible_fixture() -> None:
    rank = _rank_fixture()
    inputs = _variant_inputs(rank)

    flip = v2_signals.b_flip_legs(inputs, rank, d=None, min_adv=None)
    last = flip.loc[flip["date"] == flip["date"].max()]
    assert last.set_index("contract")["units"].to_dict() == {
        "P2": -1.0, "P3": 2.0, "P4": -1.0,
    }

    static = v2_signals.b_static_legs(inputs, rank, d=None, min_adv=None)
    last = static.loc[static["date"] == static["date"].max()]
    assert last.set_index("contract")["units"].to_dict() == {
        "P1": 1.0, "P2": -1.0, "P3": -1.0, "P4": 1.0,
    }


def test_b_flip_liquidity_filter_can_empty_the_book() -> None:
    rank = _rank_fixture()
    inputs = _variant_inputs(rank)
    assert v2_signals.b_flip_legs(
        inputs, rank, d=None, min_adv=1e9
    ).empty


def test_b_legs_nets_shared_contracts_and_uses_one_group() -> None:
    rank = _rank_fixture()
    contract = panel.build_contract_panel(rank)
    inputs = v2_signals.V2Inputs(
        bt={"rank": rank, "contract": contract},
        marks=pd.DataFrame(),
        pairs=pd.DataFrame(),
    )
    legs = v2_signals.b_legs(inputs, rank)
    assert not legs.empty
    # The v1 B fixture's high/low adjacent spreads net to P2 +1, P3 -2, P4 +1.
    last = legs.loc[legs["date"] == legs["date"].max()]
    units = last.set_index("contract")["units"].to_dict()
    assert units == {"P2": 1.0, "P3": -2.0, "P4": 1.0}
    assert last["group_id"].nunique() == 1
    assert set(last["budget"]) == {1.0}


def test_weekly_snap_uses_evaluation_and_pair_change_dates() -> None:
    dates = pd.bdate_range("2020-01-06", periods=5)  # Mon-Fri
    sig = pd.DataFrame(dict(
        date=dates, root="X",
        is_evaluation=[False, False, False, False, True],
        hedge_ratio=[1.0, 2.0, 3.0, 4.0, 5.0],
    ))
    leg = pd.DataFrame(dict(date=dates, root="X", is_pair_change=False))
    out = v2_signals._weekly_snap(sig, leg)
    assert np.allclose(
        out.to_numpy(), [np.nan, np.nan, np.nan, np.nan, 5.0], equal_nan=True
    )

    leg.loc[leg["date"] == dates[2], "is_pair_change"] = True
    out = v2_signals._weekly_snap(sig, leg)
    assert np.allclose(
        out.to_numpy(), [np.nan, np.nan, 3.0, 3.0, 5.0], equal_nan=True
    )


def test_flats_include_bad_price_and_no_pair() -> None:
    sig = pd.DataFrame(dict(
        date=pd.to_datetime(["2020-01-06", "2020-01-07", "2020-01-08"]),
        root="X", target=[1.0, 0.0, 1.0],
        has_pair=[True, True, False],
    ))
    pairs = pd.DataFrame(dict(
        date=pd.to_datetime(["2020-01-06", "2020-01-07"]),
        root="X", settle_near=[100.0, -1.0], settle_far=[50.0, 50.0],
    ))
    flat = v2_signals._flats_for_signal(sig, pairs)
    keys = set(zip(flat["date"], flat["root"]))
    assert (pd.Timestamp("2020-01-06"), "X") not in keys
    assert (pd.Timestamp("2020-01-07"), "X") in keys  # target 0 + bad price
    assert (pd.Timestamp("2020-01-08"), "X") in keys  # no pair

"""Tests for leg building and hedge-ratio leg targets."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import sizing


def _pairs() -> pd.DataFrame:
    return pd.DataFrame(dict(
        date=pd.to_datetime(["2020-01-02", "2020-01-03"]),
        root="X", contract_near="A", contract_far="B",
        settle_near=[100.0, 100.0], settle_far=[50.0, 50.0],
    ))


def _signal(target=1.0, hedge_ratio=None) -> pd.DataFrame:
    sig = pd.DataFrame(dict(
        date=pd.to_datetime(["2020-01-02", "2020-01-03"]),
        root="X", target=target,
    ))
    if hedge_ratio is not None:
        sig["hedge_ratio"] = hedge_ratio
    return sig


def test_hedge_ratio_sets_far_units_and_resize_key() -> None:
    legs = sizing.legs_from_signal(_signal(hedge_ratio=[2.0, 2.0]), _pairs())
    active = legs.loc[legs["group_id"].ne("flat")]
    near = active.loc[active["contract"].eq("A")]
    far = active.loc[active["contract"].eq("B")]
    assert np.allclose(near["units"], 1.0)
    assert np.allclose(far["units"], -2.0)
    assert set(active["resize_key"]) == {"_h2.0"}


def test_invalid_hedge_ratio_flattens() -> None:
    legs = sizing.legs_from_signal(_signal(hedge_ratio=[np.nan, 0.0]), _pairs())
    flat = legs.loc[legs["group_id"].eq("flat")]
    assert len(flat) == 2
    assert flat["resize_key"].eq("").all()
    assert legs.loc[legs["group_id"].ne("flat")].empty


def test_legs_from_rows_nets_shared_contracts() -> None:
    rows = pd.DataFrame(dict(
        date=pd.to_datetime(["2020-01-02"] * 3),
        root="X", contract=["P2", "P3", "P4"],
        units=[1.0, -2.0, 1.0], target=1.0,
    ))
    legs = sizing.legs_from_rows(rows, budget=0.5)
    assert list(legs.columns) == sizing.LEG_COLUMNS
    assert legs["group_id"].nunique() == 1
    assert legs.set_index("contract")["units"].to_dict() == {
        "P2": 1.0, "P3": -2.0, "P4": 1.0,
    }
    assert np.allclose(legs["budget"], 0.5)
    assert legs["resize_key"].nunique() == 1


def test_legs_from_rows_rejects_multiple_groups_per_root_date() -> None:
    rows = pd.DataFrame(dict(
        date=pd.to_datetime(["2020-01-02"] * 2),
        root="X", contract=["P2", "P3"], units=[1.0, -1.0], target=1.0,
        group_id=["g1", "g2"],
    ))
    with pytest.raises(ValueError, match="multiple non-flat leg groups"):
        sizing.legs_from_rows(rows, budget=0.5)


def test_legs_from_rows_flat_rows_are_explicit_exits() -> None:
    active = pd.DataFrame(dict(
        date=pd.to_datetime(["2020-01-02"]), root="X", contract=["P2"],
        units=[1.0], target=1.0,
    ))
    flat = pd.DataFrame(dict(
        date=pd.to_datetime(["2020-01-03"]), root="X", contract=[None],
        units=[0.0], target=0.0, group_id="flat",
    ))
    legs = sizing.legs_from_rows(pd.concat([active, flat], ignore_index=True), budget=0.5)
    flat_out = legs.loc[legs["group_id"].eq("flat")]
    assert len(flat_out) == 1
    assert flat_out["contract"].isna().all()
    assert flat_out["budget"].eq(0.0).all()

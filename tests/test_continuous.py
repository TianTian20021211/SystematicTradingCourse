"""Tests for roll-chained continuous leg price indices."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import continuous


def _dates(n: int = 10) -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-01", periods=n)


def _contract_frame(
    prices: dict[str, list[float | None]],
    dates: pd.DatetimeIndex,
    root: str = "X",
) -> pd.DataFrame:
    rows = []
    for code, values in prices.items():
        for date, value in zip(dates, values):
            if value is None:
                continue
            rows.append(
                {
                    "date": date,
                    "root": root,
                    "contract_code": code,
                    "settle": float(value),
                }
            )
    return pd.DataFrame(rows)


def _pair_frame(
    dates: pd.DatetimeIndex,
    pairs: list[tuple[str, str]],
    root: str = "X",
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": date,
                "root": root,
                "commodity": "Test",
                "sector": "Test",
                "contract_near": near,
                "contract_far": far,
            }
            for date, (near, far) in zip(dates, pairs)
        ]
    )


def _base_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
    dates = _dates(10)
    prices = {
        "A": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        "B": [90, 91, 92, 93, 94, 95, 96, 97, 98, 99],
        "C": [70, 71, 72, 73, 74, 75, 76, 77, 78, 79],
        "D": [40, 41, 42, 43, 44, 45, 46, 47, 48, 49],
    }
    pairs = [("A", "B")] * 3 + [("B", "C")] * 3 + [("C", "D")] * 4
    return (
        _pair_frame(dates, pairs),
        _contract_frame(prices, dates),
        dates,
    )


def test_initialization_and_non_roll_tracking() -> None:
    pairs, contract, dates = _base_frames()
    out = continuous.build_continuous_leg_prices(pairs, contract)
    indexed = out.set_index("date")

    first = indexed.loc[dates[0]]
    assert np.isclose(first["near_index"], 100.0)
    assert np.isclose(first["far_index"], 90.0)
    assert np.isclose(first["spread_index"], 10.0)

    for date in dates[:3]:
        row = indexed.loc[date]
        assert np.isclose(row["spread_index"], row["raw_spread"])
        assert not bool(row["is_pair_change"])


def test_two_rolls_do_not_jump() -> None:
    pairs, contract, dates = _base_frames()
    out = continuous.build_continuous_leg_prices(pairs, contract)
    indexed = out.set_index("date")

    for date in dates:
        assert np.isclose(indexed.loc[date, "spread_index"], 10.0)
    assert np.isclose(indexed.loc[dates[3], "raw_spread"], 20.0)
    assert np.isclose(indexed.loc[dates[6], "raw_spread"], 30.0)
    assert bool(indexed.loc[dates[3], "is_pair_change"])
    assert bool(indexed.loc[dates[6], "is_pair_change"])

    diagnostics = continuous.roll_diagnostics(out).set_index("date")
    for date in (dates[3], dates[6]):
        assert np.isclose(diagnostics.loc[date, "spread_index_change"], 0.0)
        assert np.isclose(diagnostics.loc[date, "expected_change"], 0.0)
        assert np.isclose(diagnostics.loc[date, "raw_spread_change"], 10.0)


def test_adjacent_rolls_do_not_reset() -> None:
    dates = _dates(8)
    prices = {
        "A": [100, 101, 102, 103, 104, 105, 106, 107],
        "B": [90, 91, 92, 93, 94, 95, 96, 97],
        "C": [70, 71, 72, 73, 74, 75, 76, 77],
        "D": [40, 41, 42, 43, 44, 45, 46, 47],
    }
    pairs_list = [("A", "B")] * 3 + [("B", "C")] + [("C", "D")] * 4
    out = continuous.build_continuous_leg_prices(
        _pair_frame(dates, pairs_list),
        _contract_frame(prices, dates),
    )
    indexed = out.set_index("date")
    assert np.isclose(indexed.loc[dates[2], "spread_index"], 10.0)
    assert np.isclose(indexed.loc[dates[3], "spread_index"], 10.0)
    assert np.isclose(indexed.loc[dates[4], "spread_index"], 10.0)
    assert bool(indexed.loc[dates[3], "is_pair_change"])
    assert bool(indexed.loc[dates[4], "is_pair_change"])
    assert indexed["spread_index"].notna().all()


def test_pair_change_back_and_forth() -> None:
    dates = _dates(8)
    prices = {
        "A": [100, 101, 102, 103, 104, 105, 106, 107],
        "B": [90, 91, 92, 93, 94, 95, 96, 97],
        "C": [70, 71, 72, 73, 74, 75, 76, 77],
    }
    pairs_list = [("A", "B")] * 3 + [("B", "C")] * 2 + [("A", "B")] * 3
    out = continuous.build_continuous_leg_prices(
        _pair_frame(dates, pairs_list),
        _contract_frame(prices, dates),
    )
    indexed = out.set_index("date")
    for date in dates:
        assert np.isclose(indexed.loc[date, "spread_index"], 10.0)
    assert bool(indexed.loc[dates[3], "is_pair_change"])
    assert bool(indexed.loc[dates[5], "is_pair_change"])


def test_missing_price_change_holds_and_flags() -> None:
    pairs, contract, dates = _base_frames()
    # Drop B on the first date of the B-C episode. The next B change spans
    # the gap, and the spread index is NaN only on the missing date.
    contract = contract.loc[
        ~((contract["contract_code"] == "B") & (contract["date"] == dates[4]))
    ]
    out = continuous.build_continuous_leg_prices(pairs, contract)
    indexed = out.set_index("date")

    missing = indexed.loc[dates[4]]
    assert bool(missing["near_price_change_missing"])
    assert not bool(missing["far_price_change_missing"])
    assert np.isnan(missing["spread_index"])
    assert np.isclose(missing["near_index"], 103.0)
    assert np.isclose(missing["far_index"], 94.0)

    resumed = indexed.loc[dates[5]]
    assert not bool(resumed["near_price_change_missing"])
    assert np.isclose(resumed["near_index"], 105.0)
    assert np.isclose(resumed["spread_index"], 10.0)


def test_zero_previous_settle_is_flagged() -> None:
    dates = _dates(4)
    prices = {
        "A": [100, 101, 102, 103],
        "B": [90, 0, 1, 2],
    }
    out = continuous.build_continuous_leg_prices(
        _pair_frame(dates, [("A", "B")] * 4),
        _contract_frame(prices, dates),
    )
    indexed = out.set_index("date")
    assert np.isclose(indexed.loc[dates[0], "spread_index"], 10.0)
    assert np.isclose(indexed.loc[dates[1], "spread_index"], 101.0)
    flagged = indexed.loc[dates[2]]
    assert bool(flagged["zero_prev_settle_far"])
    assert np.isnan(flagged["spread_index"])
    assert np.isclose(flagged["far_index"], 0.0)
    resumed = indexed.loc[dates[3]]
    assert np.isclose(resumed["spread_index"], 102.0)


def test_negative_settle_is_supported() -> None:
    dates = _dates(4)
    prices = {
        "A": [100, 101, -1, 1],
        "B": [90, 91, 92, 93],
    }
    out = continuous.build_continuous_leg_prices(
        _pair_frame(dates, [("A", "B")] * 4),
        _contract_frame(prices, dates),
    )
    indexed = out.set_index("date")
    assert np.isclose(indexed.loc[dates[2], "near_index"], -1.0)
    assert np.isclose(indexed.loc[dates[2], "spread_index"], -93.0)
    assert indexed["spread_index"].notna().all()


def test_grid_has_no_zero_filled_prehistory() -> None:
    dates = _dates(5)
    pairs = _pair_frame(dates, [("A", "B")] * 5)
    contract = _contract_frame(
        {"A": [None, None, 102, 103, 104], "B": [None, None, 92, 93, 94]},
        dates,
    )
    out = continuous.build_continuous_leg_prices(pairs, contract)
    indexed = out.set_index("date")
    assert indexed.loc[dates[:2], "near_index"].isna().all()
    assert indexed.loc[dates[:2], "spread_index"].isna().all()
    assert np.isclose(indexed.loc[dates[2], "spread_index"], 10.0)
    assert len(out) == len(pairs)
    assert not out.duplicated(["date", "root"]).any()


def test_duplicate_keys_raise() -> None:
    pairs, contract, _dates_ = _base_frames()
    with pytest.raises(ValueError, match="Duplicate"):
        continuous.build_continuous_leg_prices(
            pd.concat([pairs, pairs.iloc[[0]]], ignore_index=True),
            contract,
        )
    with pytest.raises(ValueError, match="Duplicate"):
        continuous.build_continuous_leg_prices(
            pairs,
            pd.concat([contract, contract.iloc[[0]]], ignore_index=True),
        )


def test_build_spread_index_returns_continuous_columns() -> None:
    pairs, contract, _dates_ = _base_frames()
    legs = continuous.build_continuous_leg_prices(pairs, contract)
    spread = continuous.build_spread_index(legs)
    assert {"date", "root", "spread_index", "raw_spread"}.issubset(spread.columns)
    assert np.allclose(
        spread.sort_values(["date", "root"])["spread_index"].to_numpy(),
        legs.sort_values(["date", "root"])["spread_index"].to_numpy(),
        equal_nan=True,
    )

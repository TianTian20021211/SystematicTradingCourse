"""Tests for the return-based backtest engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import backtest, curve, signals


def _case(
    n: int = 10,
    spread_slope: float = 0.0,
    roll: bool = False,
    old_near_missing: bool = False,
    stale_far: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2020-01-01", periods=n)
    contract_rows = []
    pair_rows = []
    signal_rows = []
    for i, date in enumerate(dates):
        a = 100.0 + i
        b = 98.0 + i + spread_slope * i
        c = 96.0 + i
        has_a = not (old_near_missing and i >= 5)
        if has_a:
            contract_rows.append(
                dict(date=date, root="X", contract_code="A", settle=a, volume=100)
            )
        b_volume = 0 if stale_far else 100
        contract_rows.append(
            dict(date=date, root="X", contract_code="B", settle=b, volume=b_volume)
        )
        contract_rows.append(
            dict(date=date, root="X", contract_code="C", settle=c, volume=100)
        )
        if roll and i >= 5:
            near, far, sn, sf = "B", "C", b, c
        else:
            near, far, sn, sf = "A", "B", a, b
        pair_rows.append(
            dict(
                date=date, root="X", commodity="Test", sector="Test",
                contract_near=near, contract_far=far,
                settle_near=sn, settle_far=sf, spread_dollar=sn - sf,
            )
        )
        signal_rows.append(dict(date=date, root="X", target=1.0))
    contract = pd.DataFrame(contract_rows)
    pair = pd.DataFrame(pair_rows)
    signal = pd.DataFrame(signal_rows)
    targets = backtest.build_target_legs(signal, pair)
    return pair, contract, signal, targets


def _run(
    pair: pd.DataFrame,
    contract: pd.DataFrame,
    targets: pd.DataFrame,
    start: str = "2020-01-01",
    end: str = "2020-01-20",
) -> backtest.BacktestResult:
    return backtest.run_backtest(
        pair,
        contract,
        targets,
        backtest.BacktestConfig(start_date=start, end_date=end),
    )


def test_build_target_legs_signs() -> None:
    pair = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-02"]),
            "root": ["X"],
            "commodity": ["Test"],
            "sector": ["Test"],
            "contract_near": ["A"],
            "contract_far": ["B"],
        }
    )
    signal = pd.DataFrame(
        {"date": pd.to_datetime(["2020-01-02"] * 3), "root": ["X"] * 3,
         "target": [1.0, -1.0, 0.0]}
    )
    out = backtest.build_target_legs(signal, pair)
    assert len(out) == 4  # target 0 produces no legs
    long_spread = out.loc[out["target"] == 1.0]
    assert set(long_spread["contract"]) == {"A", "B"}
    assert long_spread.loc[long_spread["leg"] == "near", "units"].item() == 1.0
    assert long_spread.loc[long_spread["leg"] == "far", "units"].item() == -1.0
    short_spread = out.loc[out["target"] == -1.0]
    assert short_spread.loc[short_spread["leg"] == "near", "units"].item() == -1.0
    assert short_spread.loc[short_spread["leg"] == "far", "units"].item() == 1.0


def test_entry_is_next_trading_day() -> None:
    pair, contract, _signal, targets = _case()
    res = _run(pair, contract, targets)
    entries = res.trades.loc[res.trades["reason"] == "entry"]
    assert not entries.empty
    assert entries["date"].min() == pd.Timestamp("2020-01-06")
    assert res.portfolio_returns.loc[
        res.portfolio_returns["date"] < pd.Timestamp("2020-01-06"), "N_t"
    ].eq(0).all()


def test_return_uses_lagged_gross_notional() -> None:
    pair, contract, _signal, targets = _case(spread_slope=1.0)
    res = _run(pair, contract, targets)
    row = res.portfolio_returns.loc[
        res.portfolio_returns["date"] == pd.Timestamp("2020-01-07")
    ].iloc[0]
    # 01-06 fill: A=103, B=104 -> gross=207; 01-07 spread moves -1.
    assert np.isclose(row["return_gross"], -1.0 / 207.0)


def test_roll_uses_net_legs_and_no_fake_pnl() -> None:
    pair, contract, _signal, targets = _case(roll=True)
    res = _run(pair, contract, targets)
    rolls = res.trades.loc[res.trades["reason"] == "roll"]
    assert not rolls.empty
    assert rolls["date"].min() == pd.Timestamp("2020-01-09")
    # old A-B -> new B-C: sell A, buy 2 B, sell C = 4 leg-units.
    assert len(rolls) == 3
    assert abs(rolls["units"]).sum() == 4.0
    roll_cost = res.portfolio_returns.loc[
        res.portfolio_returns["date"] == pd.Timestamp("2020-01-09"), "cost"
    ].item()
    assert 0.0009 < roll_cost < 0.0011


def test_roll_with_missing_old_near_flags() -> None:
    pair, contract, _signal, targets = _case(roll=True, old_near_missing=True)
    res = _run(pair, contract, targets)
    flags = res.trades.loc[res.trades["reason"] == "roll", "flag"]
    assert "roll_leg_missing" in set(flags)


def test_stale_entry_is_blocked() -> None:
    pair, contract, _signal, targets = _case(stale_far=True, spread_slope=-1.0)
    res = _run(pair, contract, targets)
    assert (res.trades["reason"] == "entry_blocked").any()
    assert res.positions.empty


def test_same_sign_rebalance_has_zero_cost() -> None:
    pair, contract, _signal, targets = _case(n=15)
    res = _run(pair, contract, targets, end="2020-01-31")
    rebalances = res.trades.loc[res.trades["reason"] == "rebalance"]
    assert rebalances.empty
    # Only the initial entry trades.
    assert (res.trades["reason"] == "entry").sum() == 2


def test_missing_leg_forces_exit_on_sixth_session() -> None:
    pair, contract, _signal, targets = _case(n=25)
    # Remove the near leg after 2020-01-10.
    cutoff = pd.Timestamp("2020-01-10")
    contract = contract.loc[
        ~((contract["contract_code"] == "A") & (contract["date"] > cutoff))
    ]
    res = _run(pair, contract, targets, end="2020-02-28")
    forced = res.trades.loc[res.trades["flag"] == "forced_exit"]
    assert not forced.empty
    assert forced["date"].min() > cutoff


def test_multi_leg_target_sums_leg_pnl() -> None:
    dates = pd.bdate_range("2020-01-01", periods=10)
    contract_rows = []
    for i, date in enumerate(dates):
        for code, price in [("A", 100.0 + i), ("B", 98.0 + i), ("C", 96.0 + i)]:
            contract_rows.append(
                dict(date=date, root="X", contract_code=code, settle=price, volume=100)
            )
    contract = pd.DataFrame(contract_rows)
    pair = pd.DataFrame(
        [
            dict(date=d, root="X", commodity="Test", sector="Test",
                 contract_near="A", contract_far="B",
                 settle_near=100.0 + i, settle_far=98.0 + i)
            for i, d in enumerate(dates)
        ]
    )
    targets = pd.DataFrame(
        [
            dict(date=d, root="X", commodity="Test", sector="Test",
                 group_id="X_A_B", contract="A", units=1.0, leg="near", target=1.0)
            for d in dates
        ]
        + [
            dict(date=d, root="X", commodity="Test", sector="Test",
                 group_id="X_A_B", contract="B", units=-1.0, leg="far", target=1.0)
            for d in dates
        ]
        + [
            dict(date=d, root="X", commodity="Test", sector="Test",
                 group_id="X_A_B", contract="C", units=0.5, leg="extra", target=1.0)
            for d in dates
        ]
    )
    res = _run(pair, contract, targets)
    # 01-06 fill: A=103, B=101, C=99. On 01-07 all legs rise by 1; the extra
    # C leg contributes +0.5, so the group return is 0.5 / 253.5.
    row = res.portfolio_returns.loc[
        res.portfolio_returns["date"] == pd.Timestamp("2020-01-07")
    ].iloc[0]
    expected = 0.5 / (103.0 + 101.0 + 0.5 * 99.0)
    assert np.isclose(row["return_gross"], expected)


def test_mean_reversion_signal_rolls_position() -> None:
    dates = pd.bdate_range("2020-01-01", periods=30)
    spread_values = np.full(30, 0.5)
    spread_values[7:] = 10.0
    spread_panel = pd.DataFrame(
        {"date": dates, "root": "X", "spread_index": spread_values}
    )
    signal = signals.mean_reversion_signal(
        spread_panel,
        signals.MeanReversionParams(window=10),
        trading_days=dates,
        pair_grid=spread_panel[["date", "root"]],
    )
    assert signal.loc[signal["date"].eq(dates[15]), "target"].item() == -1.0

    contract_rows = []
    pair_rows = []
    for index, date in enumerate(dates):
        a = 100.0 + index
        b = 90.0 + index
        c = 70.0 + index
        for code, price in (("A", a), ("B", b), ("C", c)):
            contract_rows.append(
                dict(date=date, root="X", contract_code=code, settle=price, volume=100)
            )
        if index < 15:
            near, far, settle_near, settle_far = "A", "B", a, b
        else:
            near, far, settle_near, settle_far = "B", "C", b, c
        pair_rows.append(
            dict(
                date=date, root="X", commodity="Test", sector="Test",
                contract_near=near, contract_far=far,
                settle_near=settle_near, settle_far=settle_far,
                spread_dollar=settle_near - settle_far,
            )
        )
    contract = pd.DataFrame(contract_rows)
    pairs = pd.DataFrame(pair_rows)
    targets = backtest.build_target_legs(signal, pairs)
    result = backtest.run_backtest(
        pairs, contract, targets, backtest.BacktestConfig()
    )

    rolls = result.trades.loc[result.trades["reason"] == "roll"]
    assert not rolls.empty
    assert rolls["date"].min() == dates[16]
    assert set(rolls["contract"]) == {"A", "B", "C"}
    exits = result.trades.loc[
        (result.trades["reason"] == "exit") & (result.trades["date"] == dates[16])
    ]
    assert exits.empty


def test_weekly_rebalance_dates_match_legacy_expression() -> None:
    days = pd.bdate_range("2020-01-01", periods=30)
    series = pd.Series(days)
    expected = set(
        pd.to_datetime(
            series.groupby(series.dt.to_period("W-FRI")).max()
        ).tolist()
    )
    assert curve.weekly_rebalance_dates(days) == expected


def test_weekly_rebalance_dates_holiday_fallback() -> None:
    days = pd.DatetimeIndex(
        [
            day
            for day in pd.bdate_range("2020-12-21", "2020-12-25")
            if day != pd.Timestamp("2020-12-25")
        ]
    )
    assert curve.weekly_rebalance_dates(days) == {pd.Timestamp("2020-12-24")}


def test_config_guards() -> None:
    pair, contract, _signal, targets = _case()
    with pytest.raises(ValueError):
        backtest.run_backtest(
            pair, contract, targets,
            backtest.BacktestConfig(execution_lag=0),
        )
    with pytest.raises(ValueError):
        backtest.run_backtest(
            pair, contract, targets,
            backtest.BacktestConfig(rebalance="daily"),
        )

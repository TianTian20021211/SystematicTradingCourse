"""Tests for the holdings-based simulator (marks, sizing, costs, simulate)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import costs, marks, simulate, sizing

SPECS = pd.DataFrame(
    {"point_value_usd": [1.0], "tick_size": [0.01], "tick_value_usd": [0.01]},
    index=pd.Index(["X"], name="root"),
)


def _contract_panel(n: int = 12, drop: dict | None = None, blank: dict | None = None) -> pd.DataFrame:
    """Two contracts: A = 100 + i, B = 100 + 2i.

    ``drop`` = {contract: [i]} removes rows; ``blank`` keeps the row with a
    missing settle (contract listed but not priced).
    """

    rows = []
    for i, date in enumerate(pd.bdate_range("2020-01-06", periods=n)):
        for code, px in (("A", 100.0 + i), ("B", 100.0 + 2 * i)):
            if drop and i in drop.get(code, []):
                continue
            if blank and i in blank.get(code, []):
                px = np.nan
            rows.append(dict(date=date, root="X", contract_code=code, settle=px, volume=1000.0, stale=False))
    return pd.DataFrame(rows)


def _pairs(cp: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(cp["date"].unique())
    return pd.DataFrame(
        dict(date=dates, root="X", contract_near="A", contract_far="B",
             settle_near=[100.0 + i for i in range(len(dates))],
             settle_far=[100.0 + 2 * i for i in range(len(dates))])
    )


def _run(cp, target=1.0, resize="on_change", leg_ratio="notional", signal=None, **cost):
    pairs = _pairs(cp)
    if signal is None:
        signal = pairs[["date", "root"]].assign(target=target)
    legs = sizing.legs_from_signal(signal, pairs, leg_ratio=leg_ratio)
    cfg = simulate.SimConfig(capital=1e6, resize=resize, cost=costs.CostParams(**cost))
    return simulate.simulate(legs, marks.build_marks(cp, SPECS), cfg)


def test_fill_next_day_and_first_pnl_day_after() -> None:
    cp = _contract_panel()
    res = _run(cp)
    days = pd.bdate_range("2020-01-06", periods=12)
    assert res.trades["date"].min() == days[1]
    pnl = res.by_root.set_index("date")["pnl_gross"]
    assert pnl.get(days[1], 0.0) == 0.0
    # Leg ratio from signal-day prices (100/100 = 1); gross scaled at the
    # day-1 fill prices A=101, B=102 with budget 1.
    n = 1e6 / (101 + 102)
    assert np.isclose(pnl[days[2]], n * 1 - n * 2)


def test_on_change_trades_once_daily_resizes() -> None:
    cp = _contract_panel()
    once = _run(cp, resize="on_change")
    assert len(once.trades) == 2
    daily = _run(cp, resize="daily")
    assert daily.trades["date"].nunique() > 5


def test_blocked_fill_waits_for_tradable_price() -> None:
    cp = _contract_panel(drop={"B": [1]})
    res = _run(cp)
    days = pd.bdate_range("2020-01-06", periods=12)
    assert res.trades["date"].min() == days[2]
    assert (res.by_root["status"] == "blocked").any()


def test_forced_exit_after_max_invalid_sessions() -> None:
    cp = _contract_panel(n=15, blank={"A": list(range(4, 15))})
    res = _run(cp)
    forced = res.trades.loc[res.trades["reason"] == "forced_exit"]
    days = pd.bdate_range("2020-01-06", periods=15)
    assert forced["date"].min() == days[4 + 5]
    assert set(forced["contract"]) == {"A"}
    assert np.isclose(forced["price"].item(), 103.0)  # last valid mark


def test_expired_contract_closes_at_final_settle_next_day() -> None:
    cp = _contract_panel(n=12, drop={"A": list(range(6, 12))})
    res = _run(cp)
    days = pd.bdate_range("2020-01-06", periods=12)
    exp = res.trades.loc[res.trades["reason"] == "expiry"]
    assert exp["date"].item() == days[6]
    assert np.isclose(exp["price"].item(), 105.0)
    assert exp["adv"].notna().all()


def test_gap_pnl_is_realised_later() -> None:
    full = _run(_contract_panel(), leg_ratio="contracts")
    gap = _run(_contract_panel(drop={"A": [5]}), leg_ratio="contracts")
    assert np.isclose(full.by_root["pnl_gross"].sum(), gap.by_root["pnl_gross"].sum())


def test_spread_execution_halves_half_spread_and_fee_per_leg() -> None:
    cp = _contract_panel()
    legs_mode = _run(cp, execution="legs", liquidity_elasticity=0.0)
    spread_mode = _run(cp, execution="spread", liquidity_elasticity=0.0)
    hs_legs = legs_mode.trades["cost_half_spread"].sum()
    assert np.isclose(spread_mode.trades["cost_half_spread"].sum(), 0.5 * hs_legs)
    qty = legs_mode.trades["dn"].abs()
    assert np.isclose(hs_legs, (qty * 0.5 * 0.01).sum())
    assert np.isclose(legs_mode.trades["cost_fee"].sum(), 1.5 * qty.sum())


def test_impact_follows_square_root_law() -> None:
    t = pd.DataFrame(dict(date=[1], root=["X"], dn=[400.0], price=[50.0], point_value=[10.0],
                          tick_size=[0.01], adv=[10_000.0], sigma=[0.02]))
    out = costs.trade_costs(t, costs.CostParams(impact_y=0.5, impact_free_contracts=0.0))
    expected = 400 * 50 * 10 * 0.5 * 0.02 * np.sqrt(400 / 10_000)
    assert np.isclose(out["cost_impact"].iat[0], expected)


def test_smooth_target_averages_last_k() -> None:
    sig = pd.DataFrame(dict(date=pd.bdate_range("2020-01-01", periods=4), root="X",
                            target=[1.0, -1.0, -1.0, -1.0]))
    out = sizing.smooth_target(sig, 3)
    assert np.allclose(out["target"], [1.0, 0.0, -1 / 3, -1.0])


def test_flip_trades_twice_the_position() -> None:
    cp = _contract_panel()
    dates = pd.bdate_range("2020-01-06", periods=12)
    sig = pd.DataFrame(dict(date=dates, root="X", target=np.where(np.arange(12) < 5, 1.0, -1.0)))
    res = _run(cp, signal=sig, leg_ratio="contracts")
    flip = res.trades.loc[(res.trades["date"] == dates[6]) & (res.trades["contract"] == "A")]
    # Close 1e6/203 long (filled at A=101, B=102), open 1e6/218 short (A=106, B=112).
    assert np.isclose(flip["dn"].item(), -(1e6 / 203 + 1e6 / 218))


def test_missing_signal_keeps_holdings_zero_target_flattens() -> None:
    cp = _contract_panel()
    dates = pd.bdate_range("2020-01-06", periods=12)
    sig = pd.DataFrame(dict(date=dates, root="X", target=1.0))
    gap = _run(cp, signal=sig.loc[sig["date"] != dates[4]])
    assert len(gap.trades) == 2  # no round trip around the missing day
    flat = sig.assign(target=np.where(sig["date"] == dates[4], 0.0, 1.0))
    res = _run(cp, signal=flat)
    assert res.trades.loc[res.trades["date"] == dates[5], "dn"].abs().sum() > 0
    assert res.holdings.loc[res.holdings["date"] == dates[5]].empty


def test_rebalance_band_ignores_small_budget_changes() -> None:
    cp = _contract_panel()
    pairs = _pairs(cp)
    sig = pairs[["date", "root"]].assign(target=1.0)
    legs = sizing.legs_from_signal(sig, pairs)
    legs.loc[legs["date"] == legs["date"].unique()[5], "budget"] *= 1.1
    cfg = simulate.SimConfig(capital=1e6, rebalance_band=0.25)
    small = simulate.simulate(legs, marks.build_marks(cp, SPECS), cfg)
    assert len(small.trades) == 2
    legs.loc[legs["date"] == legs["date"].unique()[5], "budget"] *= 2.0
    big = simulate.simulate(legs, marks.build_marks(cp, SPECS), cfg)
    assert len(big.trades) > 2


def test_forward_returns_fixed_pair_and_expiry_nan() -> None:
    from src import horizon

    cp = _contract_panel(n=12, drop={"A": list(range(8, 12))})
    mk = marks.build_marks(cp, SPECS)
    fwd = horizon.forward_returns(_pairs(cp), mk, horizons=[(1, 2), (1, 4), (5, 10)])
    row = fwd.iloc[0]
    # Window t+1 -> t+4: A 101 -> 104, B 102 -> 108.
    assert np.isclose(row["fwd_1_4"], 3 / 101 - 6 / 102)
    assert np.isclose(row["fwd_1_2"], 1 / 101 - 2 / 102)
    assert np.isnan(row["fwd_5_10"])  # A expires after day 7


def test_newey_west_matches_iid_t_with_zero_lag() -> None:
    from src import horizon

    x = pd.Series(np.random.default_rng(0).normal(0.1, 1.0, 500))
    t_iid = x.mean() / (x.std(ddof=0) / np.sqrt(len(x)))
    assert np.isclose(horizon.newey_west_t(x, 0), t_iid)


def test_capacity_curve_matches_resimulation() -> None:
    from src import report

    cp = _contract_panel(n=20)
    dates = pd.bdate_range("2020-01-06", periods=20)
    sig = pd.DataFrame(dict(date=dates, root="X", target=np.where(np.arange(20) % 4 < 2, 1.0, -1.0)))
    pairs, mk = _pairs(cp), marks.build_marks(cp, SPECS)
    legs = sizing.legs_from_signal(sig, pairs)
    base = simulate.simulate(legs, mk, simulate.SimConfig(capital=1e6))
    big = simulate.simulate(legs, mk, simulate.SimConfig(capital=4e6))
    curve = report.capacity_curve(base, [4e6])
    actual = big.daily["ret_net_all"].mean() * 252 * 100
    assert np.isclose(curve["ann_ret_pct"].item(), actual)


def test_first_lot_is_impact_free() -> None:
    t = pd.DataFrame(dict(date=[1, 1], root=["X", "X"], dn=[1.0, 4.0], price=[50.0, 50.0],
                          point_value=[10.0, 10.0], tick_size=[0.01, 0.01], adv=[1e4, 1e4], sigma=[0.02, 0.02]))
    out = costs.trade_costs(t, costs.CostParams(impact_y=0.5, impact_free_contracts=1.0))
    assert out["cost_impact"].iat[0] == 0.0
    expected = 3 * 50 * 10 * 0.5 * 0.02 * np.sqrt(4 / 1e4)
    assert np.isclose(out["cost_impact"].iat[1], expected)


def test_liquidity_budget_scales_with_dollar_adv_power() -> None:
    dates = pd.to_datetime(["2020-01-02"] * 2)
    pairs = pd.DataFrame(dict(date=dates, root=["X", "Y"], contract_near=["A", "C"], contract_far=["B", "D"],
                              settle_near=100.0, settle_far=100.0, dollar_adv=[1e6, 4e6]))
    sig = pairs[["date", "root"]].assign(target=1.0)
    legs = sizing.legs_from_signal(sig, pairs, scheme="liquidity", alpha=0.5)
    b = legs.drop_duplicates("root").set_index("root")["budget"]
    assert np.isclose(b["Y"] / b["X"], 2.0) and np.isclose(b.sum(), 1.0)


def test_time_series_ic_is_per_root_spearman() -> None:
    from src import horizon

    rng = np.random.default_rng(1)
    dates = pd.bdate_range("2010-01-01", periods=400)
    score = rng.normal(size=400)
    fwd = pd.DataFrame(dict(date=dates, root="X", fwd_1_2=score + rng.normal(size=400)))
    sig = pd.DataFrame(dict(date=dates, root="X", score=score))
    out = horizon.ts_ic(fwd, sig, col="fwd_1_2", score_col="score").set_index("root")
    expected = pd.Series(score).rank().corr(fwd["fwd_1_2"].rank())
    assert np.isclose(out.loc["X", "ic"], expected)


def test_block_bootstrap_ic_detects_signal_and_null() -> None:
    from src import horizon

    rng = np.random.default_rng(3)
    n = 800
    dates = pd.bdate_range("2000-01-03", periods=n)
    score = rng.normal(size=n)
    rows = [dict(date=d, root="SIG", score=s, fwd_1_2=0.3 * s + rng.normal()) for d, s in zip(dates, score)]
    rows += [dict(date=d, root="NUL", score=rng.normal(), fwd_1_2=rng.normal()) for d in dates]
    df = pd.DataFrame(rows)
    out, draws = horizon.block_bootstrap_ic(df[["date", "root", "fwd_1_2"]], df[["date", "root", "score"]],
                                            col="fwd_1_2", score_col="score", block=10, n_boot=500)
    out = out.set_index("root")
    assert out.loc["SIG", "p_value"] < 0.01 and out.loc["SIG", "ci_lo"] > 0
    assert out.loc["NUL", "p_value"] > 0.05
    assert len(draws["SIG"]) == 500


def test_flat_days_are_zero_filled_and_annualized_over_calendar() -> None:
    from src import report

    cp = _contract_panel(n=60)
    dates = pd.bdate_range("2020-01-06", periods=60)
    sig = pd.DataFrame(dict(
        date=dates, root="X",
        target=np.where(np.arange(60) < 10, 1.0, 0.0),
    ))
    res = _run(cp, signal=sig, leg_ratio="contracts")
    assert len(res.daily) == 60
    perf = report.performance_table(res).set_index("layer")
    expected = res.daily["ret_gross"].sum() / 60 * 252 * 100
    # performance_table rounds to three decimals.
    assert abs(perf.loc["gross", "ann_ret_pct"] - expected) < 0.01


def test_pure_flat_result_has_zero_returns() -> None:
    from src import report

    cp = _contract_panel(n=10)
    dates = pd.bdate_range("2020-01-06", periods=10)
    sig = pd.DataFrame(dict(date=dates, root="X", target=0.0))
    res = _run(cp, signal=sig, leg_ratio="contracts")
    assert len(res.daily) == 10
    assert np.allclose(res.daily["ret_gross"], 0.0)
    assert res.positions is not None and res.positions.empty
    assert "signed_notional" in res.positions.columns
    perf = report.performance_table(res).set_index("layer")
    assert np.isclose(perf.loc["gross", "ann_ret_pct"], 0.0)


def test_positions_expose_signed_notional() -> None:
    res = _run(_contract_panel())
    assert res.positions is not None
    assert set(simulate.POSITION_COLUMNS) <= set(res.positions.columns)
    p = res.positions.dropna(subset=["mark"])
    assert np.allclose(p["signed_notional"], p["n"] * p["point_value"] * p["mark"])
    assert np.allclose(p["gross_notional"], p["signed_notional"].abs())

    by_date = res.positions.groupby("date")["gross_notional"].sum()
    by_root = res.by_root.groupby("date")["gross_notional"].sum()
    common = by_date.index.intersection(by_root.index)
    assert np.allclose(by_date.loc[common], by_root.loc[common])


def test_overall_sharpe_matches_performance_table() -> None:
    from src import report

    res = _run(_contract_panel(), leg_ratio="contracts")
    perf = report.performance_table(res).set_index("layer")
    assert np.isclose(
        report.overall_sharpe(res),
        perf.loc["- impact (all)", "sharpe"],
        atol=5e-4,
    )


def test_price_derived_notional_ratio_does_not_resize_daily() -> None:
    cp = _contract_panel()
    res = _run(cp, target=1.0)
    assert len(res.trades) == 2


def test_resize_key_change_triggers_one_resize() -> None:
    cp = _contract_panel()
    dates = pd.bdate_range("2020-01-06", periods=12)
    sig = pd.DataFrame(dict(date=dates, root="X", target=1.0))
    pairs = _pairs(cp)
    legs = sizing.legs_from_signal(sig, pairs, leg_ratio="contracts")
    legs.loc[legs["date"] >= dates[5], "resize_key"] = "x"
    res = simulate.simulate(
        legs, marks.build_marks(cp, SPECS), simulate.SimConfig(capital=1e6)
    )
    assert len(res.trades) == 4
    assert (res.trades["date"] == dates[6]).sum() == 2


def test_multiple_groups_same_root_date_raise() -> None:
    legs = pd.DataFrame([
        dict(date=pd.Timestamp("2020-01-02"), root="X", group_id="g1",
             contract="A", units=1.0, budget=1.0, target=1.0, resize_key=""),
        dict(date=pd.Timestamp("2020-01-02"), root="X", group_id="g2",
             contract="B", units=-1.0, budget=1.0, target=1.0, resize_key=""),
    ])
    with pytest.raises(ValueError, match="multiple non-flat"):
        simulate._root_book(legs)


def test_mixed_flat_and_active_rows_raise() -> None:
    legs = pd.DataFrame([
        dict(date=pd.Timestamp("2020-01-02"), root="X", group_id="g1",
             contract="A", units=1.0, budget=1.0, target=1.0, resize_key=""),
        dict(date=pd.Timestamp("2020-01-02"), root="X", group_id="flat",
             contract=np.nan, units=0.0, budget=0.0, target=0.0, resize_key=""),
    ])
    with pytest.raises(ValueError, match="mixed flat"):
        simulate._root_book(legs)

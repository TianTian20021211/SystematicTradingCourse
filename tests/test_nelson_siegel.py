"""Tests for the Nelson–Siegel module (idea E, D-016) and related engine options."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import costs, marks, nelson_siegel as ns, simulate, sizing


def _wide(n_days: int = 300, lam: float = 0.3, seed: int = 0) -> pd.DataFrame:
    """Synthetic noise-free NS curves for one root on four maturities."""

    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2010-01-04", periods=n_days)
    M = np.array([1.0, 2.0, 3.0, 4.0]) + rng.uniform(0, 0.5, size=(n_days, 1))
    beta = np.column_stack([50 + rng.normal(0, 1, n_days), rng.normal(0, 2, n_days), rng.normal(0, 1, n_days)])
    X = ns.loadings(M, np.full(n_days, lam))
    F = np.einsum("bij,bj->bi", X, beta)
    out = pd.DataFrame({"date": dates, "root": "X"})
    for k in range(4):
        out[f"F{k}"], out[f"M{k}"], out[f"C{k}"] = F[:, k], M[:, k], f"K{k}"
    return out, beta


def test_loadings_match_closed_form() -> None:
    X = ns.loadings(np.array([[2.0]]), np.array([0.5]))
    s = (1 - np.exp(-1.0)) / 1.0
    assert np.allclose(X[0, 0], [1.0, s, s - np.exp(-1.0)])


def test_fit_recovers_betas_and_paper_lambda() -> None:
    wide, beta = _wide(lam=0.3)
    fit = ns.fit_ns(wide, pd.Series(0.3, index=wide.index))
    assert np.allclose(fit[["bL", "bS", "bC"]].to_numpy(), beta, atol=1e-8)
    assert np.allclose(fit["r2"], 1.0)
    lam = ns.lambda_series(wide, "paper")
    mbar = wide[[f"M{k}" for k in range(4)]].mean(axis=1)
    assert np.allclose(lam, 1.7933 / mbar)
    assert np.allclose(ns.lambda_series(wide, "fixed_3"), 1.7933 / 3)


def test_rolling_ssr_finds_true_lambda_causally() -> None:
    true = float(ns.LAMBDA_GRID[6])
    wide, _ = _wide(n_days=200, lam=true)
    lam = ns.lambda_series(wide, "rolling_ssr", window=100)
    assert np.allclose(lam.iloc[100:], true)
    # Before 63 past days exist the paper rule is used (no look-ahead).
    assert np.allclose(lam.iloc[:63], ns.lambda_series(wide, "paper").iloc[:63])


def _contracts() -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2020-01-02", periods=30)
    specs = {"A": ("2020-01-01", "2020-01-14"), "B": ("2020-03-01", "2020-02-20"),
             "C": ("2020-05-01", "2020-04-21"), "D": ("2020-07-01", "2020-06-19"),
             "E": ("2020-09-01", "2020-08-20")}
    for d in dates:
        for code, (dms, last) in specs.items():
            if pd.Timestamp(last) < d:
                continue
            rows.append(dict(date=d, root="X", contract_code=code, settle=100.0, in_delivery_month=d >= pd.Timestamp(dms),
                             delivery_month_start=pd.Timestamp(dms), last_date=pd.Timestamp(last), is_censored=False))
    df = pd.DataFrame(rows)
    df.loc[df["contract_code"] == "E", "is_censored"] = True
    return df


def test_eligible_curve_drops_delivery_month_and_infers_censored_ltd() -> None:
    c = _contracts()
    curve = ns.eligible_curve(c)
    assert "A" not in set(curve["contract_code"])  # A is in its delivery month throughout
    ltd = ns.last_trading_days(c)
    # Median offset of expired contracts B, C, D (-10, -10, -12 days) -> -10.
    assert ltd[("X", "E")] == pd.Timestamp("2020-09-01") - pd.Timedelta(days=10)
    m = curve.loc[(curve["contract_code"] == "B") & (curve["date"] == "2020-01-02"), "maturity"].item()
    assert np.isclose(m, (pd.Timestamp("2020-02-20") - pd.Timestamp("2020-01-02")).days / ns.MONTH_DAYS)


def test_changes_undefined_across_gaps() -> None:
    wide, _ = _wide(n_days=10)
    wide = wide.drop(index=5).reset_index(drop=True)
    curve = wide[["date", "root"]].assign(contract_code="K0")
    curve = pd.concat([curve, pd.DataFrame({"date": [pd.bdate_range("2010-01-04", periods=10)[5]], "root": ["X"],
                                            "contract_code": ["K0"]})])
    fits = ns.fit_ns(wide, ns.lambda_series(wide))
    sig = ns.ns_signals(fits, wide, curve)
    day_after_gap = pd.bdate_range("2010-01-04", periods=10)[6]
    assert np.isnan(sig.loc[sig["date"] == day_after_gap, "dbS"].item())
    assert sig["dbS"].notna().sum() == 10 - 1 - 2  # first day and the day after the gap


def test_butterfly_notional_shares_and_flat_rows() -> None:
    sig = pd.DataFrame({"date": pd.to_datetime(["2020-01-02", "2020-01-03"]), "root": "X",
                        "C0": "A", "C1": "B", "C2": "C", "C3": "D", "F0": 100.0, "F1": 50.0, "F2": 40.0, "F3": 25.0,
                        "dbC": [0.5, np.nan]})
    curve = sig[["date", "root"]]
    legs = ns.butterfly_legs(sig, curve)
    day = legs.loc[legs["date"] == "2020-01-02"].set_index("contract")
    notional = day["units"] * pd.Series({"A": 100.0, "B": 50.0, "D": 25.0})
    assert np.allclose(notional[["A", "B", "D"]], [-1.0, 2.0, -1.0])
    assert legs.loc[legs["date"] == "2020-01-03", "group_id"].item() == "flat"


def test_round_lots_skip_spreads_below_one_contract() -> None:
    dates = pd.bdate_range("2020-01-06", periods=6)
    cp = pd.DataFrame([dict(date=d, root="X", contract_code=c, settle=100.0 + i, volume=1e3, stale=False)
                       for i, d in enumerate(dates) for c in ("A", "B")])
    specs_ = pd.DataFrame({"point_value_usd": [1000.0], "tick_size": [0.01], "tick_value_usd": [10.0]},
                          index=pd.Index(["X"], name="root"))
    pairs = pd.DataFrame({"date": dates, "root": "X", "contract_near": "A", "contract_far": "B",
                          "settle_near": 100.0, "settle_far": 100.0})
    legs = sizing.legs_from_signal(pairs[["date", "root"]].assign(target=1.0), pairs)
    mk = marks.build_marks(cp, specs_)
    small = simulate.simulate(legs, mk, simulate.SimConfig(capital=50_000, round_lots=True))
    assert small.trades.empty  # 25k per leg < half a 100k contract
    big = simulate.simulate(legs, mk, simulate.SimConfig(capital=1_000_000, round_lots=True))
    assert np.allclose(big.trades["dn"].abs(), 5.0)  # 500k per leg / 101k ≈ 4.95 -> 5 lots


def test_paper_tc2_is_proportional() -> None:
    t = pd.DataFrame(dict(date=[1], root=["X"], dn=[2.0], price=[50.0], point_value=[100.0],
                          tick_size=[0.01], adv=[1e4], sigma=[0.02]))
    out = costs.trade_costs(t, costs.paper_scenarios()["TC2"])
    assert np.isclose(out["cost_fee"].item(), 2 * 50 * 100 * 0.835e-4)
    assert out["cost_half_spread"].item() == 0 and out["cost_impact"].item() == 0


def test_same_settle_fills_on_signal_day_and_earns_that_day() -> None:
    dates = pd.bdate_range("2020-01-06", periods=8)
    cp = pd.DataFrame([dict(date=d, root="X", contract_code=c, settle=100.0 + (i if c == "A" else 0.0),
                            volume=1e3, stale=False) for i, d in enumerate(dates) for c in ("A", "B")])
    specs_ = pd.DataFrame({"point_value_usd": [1.0], "tick_size": [0.01], "tick_value_usd": [0.01]},
                          index=pd.Index(["X"], name="root"))
    pairs = pd.DataFrame({"date": dates, "root": "X", "contract_near": "A", "contract_far": "B",
                          "settle_near": 100.0, "settle_far": 100.0})
    sig = pairs[["date", "root"]].assign(target=np.where(np.arange(8) >= 3, 1.0, 0.0))
    mk = marks.build_marks(cp, specs_)
    legs = sizing.legs_from_signal(sig, pairs)
    lagged = simulate.simulate(legs, mk, simulate.SimConfig(capital=1e6))
    same = simulate.simulate(simulate.same_settle(legs, mk), mk, simulate.SimConfig(capital=1e6))
    assert lagged.trades["date"].min() == dates[4]
    assert same.trades["date"].min() == dates[3]  # filled at the signal's own settle
    first = same.by_root.set_index("date")["pnl_gross"]
    assert first[dates[4]] > 0  # earns the t -> t+1 move of A


def test_fit_quality_perfect_on_noise_free_curves() -> None:
    wide, _ = _wide(n_days=20, lam=0.3)
    q = ns.fit_quality(wide, pd.Series(0.3, index=wide.index))
    assert np.allclose(q["r2_LSC"], 1.0) and np.allclose(q["adj_LSC"], 1.0) and np.allclose(q["loo_LSC"], 1.0)
    assert np.allclose(q["r2_L"], 0.0) and np.allclose(q["adj_L"], 0.0)
    assert (q["r2_LS"] <= q["r2_LSC"] + 1e-12).all()  # nested in-sample R² never falls


def test_block_bootstrap_mean_detects_shift() -> None:
    from src import horizon

    rng = np.random.default_rng(5)
    dates = pd.bdate_range("2000-01-03", periods=600)
    df = pd.concat([pd.DataFrame({"date": dates, "root": "POS", "x": 0.3 + rng.normal(size=600)}),
                    pd.DataFrame({"date": dates, "root": "NUL", "x": rng.normal(size=600)})])
    s, d = horizon.block_bootstrap_mean(df, "x", block=10, n_boot=500)
    s = s.set_index("root")
    assert s.loc["POS", "p_value"] < 0.01 and s.loc["NUL", "p_value"] > 0.01  # a 5% test rejects a true null 5% of the time
    med, _ = horizon.block_bootstrap_mean(df, "x", block=10, n_boot=200, stat="median")
    assert np.isclose(med.set_index("root").loc["POS", "mean"], df.loc[df["root"] == "POS", "x"].median())


def test_kalman_tracks_constant_curve_and_predicts_it() -> None:
    from src import ns_kalman as nk

    M = np.array([1.0, 2.0, 3.0, 4.0])
    beta = np.array([50.0, -3.0, 2.0])
    X = ns.loadings(M[None, :], np.array([1.7933 / M.mean()]))[0]
    obs = [(pd.Timestamp("2020-01-01") + pd.Timedelta(days=i), X @ beta, M, 1.7933 / M.mean()) for i in range(30)]
    res = nk.run_filter(obs, np.array([1e-5]), np.array([1e-6]), loo=True)
    assert np.allclose(res["beta_post"][-1], beta, atol=1e-6)
    assert np.allclose(res["sse_pred"][1:, 0], 0.0, atol=1e-8)  # a constant curve is predicted exactly
    assert np.allclose(res["press_loo"][1:, 0], 0.0, atol=1e-6)


def test_fit_quality_interior_holdout_matches_manual() -> None:
    rng = np.random.default_rng(3)
    m = np.array([[0.5, 1.5, 2.5, 3.5]])
    f = np.array([[60.0, 63.0, 64.0, 66.0]]) + rng.normal(0, 0.1, (1, 4))
    wide = pd.DataFrame({"date": [pd.Timestamp("2000-01-03")], "root": ["AA"],
                         **{f"F{k}": f[:, k] for k in range(4)}, **{f"M{k}": m[:, k] for k in range(4)}})
    q_all = ns.fit_quality(wide, pd.Series(0.5, index=wide.index))
    q_int = ns.fit_quality(wide, pd.Series(0.5, index=wide.index), holdout=(1, 2))
    # Level-only interior LOO: predict contracts 1 and 2 by the mean of the other three.
    press = sum((f[0, k] - np.delete(f[0], k).mean()) ** 2 for k in (1, 2)) * 2
    sst = ((f[0] - f[0].mean()) ** 2).sum()
    assert np.isclose(q_int["loo_L"].iloc[0], 1 - press / sst)
    assert np.isclose(q_all["loo_L"].iloc[0], 1 - 16 / 9)

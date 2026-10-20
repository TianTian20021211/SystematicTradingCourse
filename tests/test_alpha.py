"""Synthetic tests for the alpha-combination layer (D-030)."""

import numpy as np
import pandas as pd

from src import alpha_factors as af
from src import alpha_models as M
from src import alpha_portfolio as P
from src import alpha_screen as S


def _planted(n_dates=600, roots=("AA", "BB", "CC", "DD"), beta=0.3, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("1990-01-01", periods=n_dates)
    rows = []
    for r in roots:
        x = rng.standard_normal(n_dates)
        rows.append(pd.DataFrame({
            "date": dates, "root": r, "good": x, "noise": rng.standard_normal(n_dates),
            "fwd_1_2": beta * x + rng.standard_normal(n_dates),
        }))
    return pd.concat(rows, ignore_index=True)


def test_screen_keeps_planted_and_drops_noise():
    f = _planted()
    mats = S.rank_matrices(f, ["good", "noise"], "fwd_1_2", min_obs=100)
    boot = S.joint_bootstrap(mats, ["good", "noise"], block=5, n_boot=300)
    tab = pd.concat([S.ic_table(mats, boot, c) for c in ("good", "noise")])
    out = S.screen(tab, fallback_min=0).set_index("score")
    assert out.loc["good", "primary"] and out.loc["good", "n_sig"] == 4
    assert not out.loc["noise", "selected"]


def test_joint_bootstrap_point_matches_spearman():
    f = _planted()
    mats = S.rank_matrices(f, ["good"], "fwd_1_2", min_obs=100)
    point, draws = S.joint_bootstrap(mats, ["good"], block=5, n_boot=50)["good"]
    g = f.loc[f["root"].eq("AA")]
    assert np.isclose(point[0], g["good"].corr(g["fwd_1_2"], method="spearman"))
    assert draws.shape == (50, 4)


def test_choose_block_finds_plateau():
    sens = pd.DataFrame({"root": "ALL", "score": "x", "block": [1, 5, 10, 21], "se": [0.4, 0.7, 0.95, 1.0]})
    assert S.choose_block(sens) == 10


def test_identical_models_have_no_wins():
    f = _planted()
    f["m1"], f["m2"] = f["good"], f["good"]
    pairs, summ, _ = M.compare_models(f, ["m1", "m2"], "fwd_1_2", block=5, n_boot=200)
    assert np.allclose(pairs["diff"], 0) and not pairs["win"].any()
    assert M.select_model(summ) in ("m1", "m2")


def test_select_model_tie_goes_to_simpler():
    summ = pd.DataFrame({"model": ["xgb", "ols", "rf"], "mean_ic": [0.1, 0.05, 0.2], "wins": [1, 1, 0]})
    assert M.select_model(summ) == "ols"


def test_xs_signal_is_balanced():
    rng = np.random.default_rng(1)
    dates = pd.bdate_range("2000-01-03", periods=5)
    fc = pd.DataFrame([(d, f"R{i}", rng.standard_normal()) for d in dates for i in range(12)],
                      columns=["date", "root", "pred"]).assign(exp_ret=0.0)
    sig = P.make_signal(fc, "xs", n_xs=3)
    by = sig.groupby("date")["target"]
    assert (by.apply(lambda s: (s > 0).sum()) == 3).all() and (by.sum() == 0).all()


def test_band_holds_state_below_cost():
    fc = pd.DataFrame({
        "date": pd.bdate_range("2000-01-03", periods=4), "root": "AA",
        "pred": [1.0, -0.1, -1.0, 0.2], "exp_ret": [0.02, -0.001, -0.02, 0.002],
    })
    sig = P.make_signal(fc, "band", cost=pd.Series(0.01, index=fc.index))
    assert sig.sort_values("date")["target"].tolist() == [1.0, 1.0, -1.0, -1.0]


def test_scale_factors_is_causal():
    rng = np.random.default_rng(2)
    p = pd.DataFrame({"date": pd.bdate_range("2000-01-03", periods=400), "root": "AA",
                      "x": rng.standard_normal(400)})
    base = af.scale_factors(p, ["x"], min_obs=50)
    q = p.copy()
    q.loc[300:, "x"] *= 100
    pert = af.scale_factors(q, ["x"], min_obs=50)
    assert np.allclose(base["z_x"].iloc[:300], pert["z_x"].iloc[:300], equal_nan=True)
    assert base["z_x"].iloc[:49].isna().all()


def test_pair_daily_returns_uses_both_legs():
    pairs = pd.DataFrame({"date": pd.to_datetime(["2000-01-04"]), "root": ["AA"],
                          "contract_near": ["AAH0"], "contract_far": ["AAK0"]})
    marks = pd.DataFrame({"date": pd.to_datetime(["2000-01-04"] * 2), "root": "AA",
                          "contract_code": ["AAH0", "AAK0"], "ret": [0.03, 0.01]})
    assert np.isclose(af.pair_daily_returns(pairs, marks).iloc[0], 0.02)


def test_rolled_forward_sums_next_days():
    p = pd.DataFrame({"date": pd.bdate_range("2000-01-03", periods=8), "root": "AA",
                      "r": [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07]})
    out = af.rolled_forward(p, horizons=(1, 3))
    # Window [t+1, t+1+h]: the returns realised on rows t+2 ... t+1+h.
    assert np.isclose(out["roll_1"].iloc[0], 0.02)
    assert np.isclose(out["roll_3"].iloc[0], 0.02 + 0.03 + 0.04)
    assert out["roll_3"].iloc[-4:].isna().all()


def test_hold_between_rebalances_updates_every_m():
    sig = pd.DataFrame({"date": pd.bdate_range("2000-01-03", periods=6), "root": "AA",
                        "target": [1.0, -1.0, -1.0, -1.0, 1.0, 1.0]})
    out = P.hold_between_rebalances(sig, every=3)
    assert out["target"].tolist() == [1.0, 1.0, 1.0, -1.0, -1.0, -1.0]

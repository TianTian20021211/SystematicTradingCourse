"""Tests for the execution-independent C audit diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import c_audit


def _signal_fwd() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2020-01-01", periods=300)
    target = np.zeros(len(dates))
    target[50:100] = 1.0
    target[150:200] = -1.0
    signal = pd.DataFrame(
        {
            "date": dates,
            "root": "X",
            "target": target,
            "score": -target,
            "spread_index": np.arange(len(dates), dtype=float) * 0.01,
        }
    )
    fwd = pd.DataFrame({"date": dates, "root": "X"})
    for col, value in {
        "fwd_0_1": 0.001,
        "fwd_1_2": 0.002,
        "fwd_1_6": 0.004,
        "fwd_1_11": 0.008,
        "fwd_1_21": 0.010,
    }.items():
        fwd[col] = target * value
    return signal, fwd


def test_event_study_fresh_entries_and_sides() -> None:
    signal, fwd = _signal_fwd()
    out = c_audit.event_study(signal, fwd)
    fresh = out.loc[out["event"].eq("fresh")]
    assert set(fresh["side"]) == {"all", "long", "short"}
    assert fresh["n_events"].sum() > 0
    assert (fresh["mean_bps"] > 0).all()
    assert (fresh["hit_rate"] == 1.0).all()


def test_persistence_table_recovers_ar1() -> None:
    rng = np.random.default_rng(0)
    n = 1_000
    phi = 0.9
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal(scale=0.1)
    dates = pd.bdate_range("2010-01-01", periods=n)
    signal = pd.DataFrame(
        {"date": dates, "root": "X", "spread_index": x, "score": x}
    )
    out = c_audit.persistence_table(signal, {"full": (None, None)})
    assert len(out) == 1
    assert abs(out.loc[0, "phi_level"] - phi) < 0.05
    assert out.loc[0, "half_life_level"] > 0


def test_nested_predictive_informative_control() -> None:
    rng = np.random.default_rng(0)
    n = 600
    dates = pd.bdate_range("2015-01-01", periods=n)
    z = rng.normal(size=n)
    carry = rng.normal(size=n)
    y = z + carry + rng.normal(scale=0.1, size=n)
    signal = pd.DataFrame(
        {
            "date": dates,
            "root": "X",
            "score": -z,
            "spread_index": np.cumsum(rng.normal(size=n)),
        }
    )
    fwd = pd.DataFrame({"date": dates, "root": "X", "fwd_1_6": y})
    control = pd.DataFrame({"date": dates, "root": "X", "carry_ann": carry})
    out = c_audit.nested_predictive_table(signal, fwd, control)
    adj = out.set_index("model")["adj_r2"]
    assert adj["M1_z_carry"] > adj["M0_z"]
    assert adj["M3_z_both"] > adj["M0_z"]


def test_placebo_reproducible() -> None:
    signal, fwd = _signal_fwd()
    a, da = c_audit.placebo_table(signal, fwd, n_draws=20, seed=1)
    b, db = c_audit.placebo_table(signal, fwd, n_draws=20, seed=1)
    assert a["actual_sr"] == b["actual_sr"]
    np.testing.assert_allclose(da, db)
    assert 0.0 <= a["p_one_sided"] <= 1.0
    assert 0.0 <= a["p_two_sided"] <= 1.0

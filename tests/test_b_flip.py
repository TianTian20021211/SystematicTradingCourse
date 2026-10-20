"""Tests for the B-flip research helpers (synthetic fixtures, no raw data)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import b_flip, marks, panel, v2_signals


def _fixture() -> tuple[pd.DataFrame, v2_signals.V2Inputs]:
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
    rank = pd.DataFrame(rows)
    contract = panel.build_contract_panel(rank)
    if "stale" not in contract.columns:
        contract = contract.assign(stale=False)
    specs = pd.DataFrame(
        {"point_value_usd": [1.0], "tick_size": [0.01]},
        index=pd.Index(["X"], name="root"),
    )
    mk = marks.build_marks(contract, specs)
    inputs = v2_signals.V2Inputs(
        bt={"rank": rank, "contract": contract},
        marks=mk,
        pairs=pd.DataFrame(),
    )
    return rank, inputs


def test_horizon_profiles_returns_signal_level_stats() -> None:
    rank, inputs = _fixture()
    out = b_flip.horizon_profiles(
        inputs, rank, d=None, min_adv=None,
        marginal=[(1, 2)], cumulative=[(1, 3)],
    )
    assert not out["marginal"].empty
    assert not out["cumulative"].empty
    assert {"horizon", "mean_bps", "t_nw", "hit_rate", "n_dates"}.issubset(
        out["marginal"].columns
    )
    assert np.isfinite(out["marginal"]["mean_bps"]).all()


def test_bootstrap_selected_shapes() -> None:
    rank, inputs = _fixture()
    out = b_flip.horizon_profiles(
        inputs, rank, d=None, min_adv=None, cumulative=[(1, 2)]
    )
    summary, draws = b_flip.bootstrap_selected(
        out["selected"], window=(1, 2), block=2, n_boot=10, seed=0, min_obs=3
    )
    assert not summary.empty
    assert set(draws) == set(summary["root"])
    assert {"mean_bps", "ci_lo_bps", "ci_hi_bps", "p_value"}.issubset(
        summary.columns
    )


def test_rank_placebo_shapes() -> None:
    rank, inputs = _fixture()
    out = b_flip.rank_placebo(
        inputs, rank, d=None, min_adv=None, window=(1, 2), n_boot=20, seed=0
    )
    assert len(out["draws"]) == 20
    assert 0.0 <= out["p_one_sided"] <= 1.0
    assert 0.0 <= out["p_two_sided"] <= 1.0
    assert out["n_groups"] > 0
    assert np.isfinite(out["actual"])


def test_bootstrap_and_jackknife() -> None:
    rank, inputs = _fixture()
    item = b_flip.run_b_flip(
        inputs, rank, capital=1_000_000.0, d=None, min_adv=None
    )
    summary, draws = b_flip.bootstrap_roots(
        item["result"], capital=1_000_000.0,
        block=2, n_boot=10, seed=0, min_obs=3,
    )
    assert not summary.empty
    assert {"root", "mean_bps", "ci_lo_bps", "ci_hi_bps", "p_value"}.issubset(
        summary.columns
    )
    assert set(draws) == set(summary["root"])

    jack = b_flip.root_jackknife(item["result"], capital=1_000_000.0)
    assert "ALL" in set(jack["root"])
    assert {"ann_ret_pct", "sharpe", "t_nw"}.issubset(jack.columns)

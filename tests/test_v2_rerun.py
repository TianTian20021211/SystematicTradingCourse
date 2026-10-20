"""Tests for saving v2 strategy tables."""

from __future__ import annotations

import pandas as pd

from src import v2_rerun


def _item(name: str = "a") -> dict:
    performance = pd.DataFrame(
        {"layer": ["gross", "- impact (all)"], "sharpe": [-0.5, -2.6]}
    )
    root = pd.DataFrame({"root": ["CL"], "net_pct_yr": [-1.0]})
    return {"name": name, "performance": performance, "root": root}


def test_save_strategy_writes_only_per_strategy_files(tmp_path) -> None:
    out = v2_rerun.save_strategy(_item("a"), tmp_path)
    assert out == tmp_path
    assert (tmp_path / "a_performance.csv").exists()
    assert (tmp_path / "a_root.csv").exists()
    assert not (tmp_path / "comparison.csv").exists()


def test_save_results_writes_comparison(tmp_path) -> None:
    results = {"a": _item("a"), "b": _item("b")}
    v2_rerun.save_results(results, tmp_path)
    assert (tmp_path / "a_performance.csv").exists()
    assert (tmp_path / "b_performance.csv").exists()
    comparison = pd.read_csv(tmp_path / "comparison.csv")
    assert set(comparison["strategy"]) == {"a", "b"}

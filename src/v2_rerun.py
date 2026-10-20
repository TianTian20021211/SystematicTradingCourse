"""Run the v2 re-runs for A, D, C, C-hedge and B and save summary tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config, costs, report, simulate, v2_signals

STRATEGIES = ("a", "d", "c", "c_ols", "c_kalman", "b")


@dataclass(frozen=True)
class RerunSettings:
    """Fixed conventions from D-018."""

    capital: float = 10_000_000.0
    min_adv: float | None = 100.0
    d: int | None = 5
    k: int = 5
    resize: str = "on_change"
    rebalance_band: float = 0.25


def _config(name: str, settings: RerunSettings) -> simulate.SimConfig:
    # A stays on the v2-native 25% band; C/D/B are calendar-driven and use a
    # large band so only target/composition changes resize.
    band = settings.rebalance_band if name == "a" else 1e9
    execution = "legs" if name == "b" else "spread"
    return simulate.SimConfig(
        capital=settings.capital,
        resize=settings.resize,
        rebalance_band=band,
        cost=costs.CostParams(execution=execution),
    )


def run_strategy(
    name: str,
    rank: pd.DataFrame,
    settings: RerunSettings | None = None,
    inputs: v2_signals.V2Inputs | None = None,
) -> dict:
    """Run one strategy and return its legs, result and summary tables."""

    if name not in STRATEGIES:
        raise ValueError(f"name must be one of {STRATEGIES}, got {name!r}")
    settings = settings or RerunSettings()
    inputs = inputs or v2_signals.load_v2_inputs(
        rank, d=settings.d, k=settings.k, min_adv=settings.min_adv
    )
    if name == "a":
        legs = v2_signals.a_legs(inputs)
    elif name == "d":
        legs = v2_signals.d_legs(inputs)
    elif name == "c":
        legs = v2_signals.c_legs(inputs, "1:1")
    elif name == "c_ols":
        legs = v2_signals.c_legs(inputs, "ols")
    elif name == "c_kalman":
        legs = v2_signals.c_legs(inputs, "kalman")
    else:
        legs = v2_signals.b_legs(inputs, rank)

    result = simulate.simulate(legs, inputs.marks, _config(name, settings))
    performance = pd.concat(
        {
            "full": report.performance_table(result),
            "train 1986-2015": report.performance_table(result, end="2015-12-31"),
            "test 2016-2026": report.performance_table(result, start="2016-01-01"),
        },
        names=["period"],
    )
    return {
        "name": name,
        "legs": legs,
        "result": result,
        "performance": performance,
        "root": report.root_table(result),
    }


def run_all(
    names: tuple[str, ...] | list[str],
    rank: pd.DataFrame,
    settings: RerunSettings | None = None,
) -> dict[str, dict]:
    """Run several strategies on the same v2 panels."""

    settings = settings or RerunSettings()
    inputs = v2_signals.load_v2_inputs(
        rank, d=settings.d, k=settings.k, min_adv=settings.min_adv
    )
    return {
        name: run_strategy(name, rank, settings, inputs=inputs)
        for name in names
    }


def save_strategy(
    item: dict,
    out_dir: str | Path | None = None,
) -> Path:
    """Write one strategy's performance and root tables.

    The idea notebooks call this instead of ``save_results`` so a single
    strategy cannot overwrite the cross-strategy ``comparison.csv``.
    """

    out = Path(out_dir) if out_dir is not None else config.ROOT / "output" / "v2_rerun"
    out.mkdir(parents=True, exist_ok=True)
    item["performance"].to_csv(out / f"{item['name']}_performance.csv")
    item["root"].to_csv(out / f"{item['name']}_root.csv")
    return out


def save_results(
    results: dict[str, dict],
    out_dir: str | Path | None = None,
) -> Path:
    """Write per-strategy tables and a tidy comparison CSV."""

    out = Path(out_dir) if out_dir is not None else config.ROOT / "output" / "v2_rerun"
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for name, item in results.items():
        save_strategy(item, out)
        frame = item["performance"].reset_index()
        frame.insert(0, "strategy", name)
        frames.append(frame)
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(out / "comparison.csv", index=False)
    return out

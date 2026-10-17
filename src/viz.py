"""Small matplotlib helpers used by the notebooks.

The notebooks should show only a few selected figures; heavy exploratory
plotting belongs here or in throwaway analysis.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd

from . import config


plt.rcParams.update(
    {
        "figure.dpi": 110,
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 9,
    }
)


def _save(fig: plt.Figure, name: str, output_dir: Path | None = None) -> Path | None:
    if output_dir is None:
        return None
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.png"
    fig.savefig(path, bbox_inches="tight")
    return path


def plot_coverage_heatmap(
    rank_panel: pd.DataFrame,
    output_dir: Path | None = None,
) -> plt.Figure:
    frame = rank_panel.assign(
        year=rank_panel["date"].dt.year,
        valid=rank_panel["settle"].notna(),
    )
    coverage = frame.pivot_table(
        index="commodity", columns="year", values="valid", aggfunc="mean"
    ).sort_index()
    fig, ax = plt.subplots(figsize=(12, 6))
    image = ax.imshow(
        coverage.values, aspect="auto", cmap="magma", vmin=0, vmax=1,
        interpolation="nearest",
    )
    ax.set_yticks(range(len(coverage.index)))
    ax.set_yticklabels(coverage.index)
    ax.set_xticks(range(len(coverage.columns)))
    ax.set_xticklabels(coverage.columns, rotation=90)
    ax.set_title("Settlement coverage by commodity and year")
    fig.colorbar(image, ax=ax, label="fraction of days with settle")
    _save(fig, "coverage_heatmap", output_dir)
    return fig


def plot_liquidity_heatmap(
    rank_panel: pd.DataFrame,
    rank: int = 1,
    value: str = "volume",
    output_dir: Path | None = None,
) -> plt.Figure:
    frame = rank_panel.loc[rank_panel["rank"].eq(rank)].assign(
        year=rank_panel["date"].dt.year
    )
    pivot = frame.pivot_table(
        index="commodity", columns="year", values=value, aggfunc="median"
    ).sort_index()
    values = pivot.values.astype(float)
    finite = values[np.isfinite(values) & (values > 0)]
    vmin = max(1.0, float(np.nanpercentile(finite, 5))) if finite.size else 1.0
    vmax = max(vmin * 10, float(np.nanmax(finite))) if finite.size else 10.0

    fig, ax = plt.subplots(figsize=(12, 6))
    image = ax.imshow(
        values, aspect="auto", cmap="viridis", norm=LogNorm(vmin=vmin, vmax=vmax),
        interpolation="nearest",
    )
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=90)
    ax.set_title(f"M{rank} annual median {value}")
    fig.colorbar(image, ax=ax, label=value)
    _save(fig, f"liquidity_m{rank}_{value}", output_dir)
    return fig


def _threshold_slug(value: int) -> str:
    return f"{value // 1_000}k" if value % 1_000 == 0 else str(value)


def plot_universe_counts(
    universe: pd.DataFrame,
    thresholds: tuple[int, ...] = (1_000, 5_000, 10_000),
    output_dir: Path | None = None,
) -> plt.Figure:
    frame = universe.assign(year=universe["date"].dt.year)
    fig, ax = plt.subplots(figsize=(9, 4))
    for threshold in thresholds:
        column = f"pass_vol_{_threshold_slug(threshold)}"
        counts = frame.groupby("year").apply(
            lambda group, col=column: group.loc[group[col], "root"].nunique(),
            include_groups=False,
        )
        ax.plot(counts.index, counts.values, marker="o", ms=2, label=f"volume >= {threshold:,}")
    ax.set_title("Commodities with at least one passing pair-day")
    ax.set_xlabel("year")
    ax.set_ylabel("number of commodities")
    ax.legend(frameon=False)
    _save(fig, "universe_counts", output_dir)
    return fig


def plot_pair_mix(
    pairs: pd.DataFrame,
    output_dir: Path | None = None,
) -> plt.Figure:
    frame = pairs.assign(year=pairs["date"].dt.year)
    mix = (
        frame.groupby(["year", "pair_rank_mix"]).size().unstack(fill_value=0)
    )
    share = mix.div(mix.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(9, 4))
    share.plot(kind="area", stacked=True, ax=ax, alpha=0.8)
    ax.set_title("Selected pair mix over time")
    ax.set_xlabel("year")
    ax.set_ylabel("share of pair-days")
    ax.legend(frameon=False, loc="upper left")
    _save(fig, "pair_mix", output_dir)
    return fig


def plot_spread_distribution(
    spread_panel: pd.DataFrame,
    root: str = "CL",
    output_dir: Path | None = None,
) -> plt.Figure:
    frame = spread_panel.loc[spread_panel["root"].eq(root)]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    axes[0].hist(frame["spread_dollar"].dropna(), bins=50, color="#4c72b0")
    axes[0].set_title(f"{root}: dollar spread")
    axes[0].set_xlabel("near - far")
    axes[1].hist(frame["spread_log"].dropna(), bins=50, color="#55a868")
    axes[1].set_title(f"{root}: log spread")
    axes[1].set_xlabel("log(near / far)")
    fig.tight_layout()
    _save(fig, f"spread_distribution_{root}", output_dir)
    return fig

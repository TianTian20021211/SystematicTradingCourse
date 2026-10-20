#!/usr/bin/env python
"""Regenerate the C1 deck figures in the simple A/B/D presentation style.

The deck's A/B/D position pages use a single-panel year-end signed-position
heatmap and one cumulative gross P&L line. The original C figures were the
notebook's two-panel ``F.positions`` diagnostic and the four-line cost-layer
path; this script draws the same C1 weekly v2 run as the D-019 table in the
simpler deck style.

Usage:
    python scripts/make_c_deck_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

from src import config, figures as F, plotstyle as ps, v2_rerun, v2_signals  # noqa: E402

OUT = ROOT / "presentations" / "final" / "figures"


def heatmap(res, root_order, path: Path, freq: str = "YE") -> None:
    """Single-panel signed gross position heatmap (blue = long nearest leg)."""

    panel = F.position_panel(res, root_order=root_order, freq=freq)
    fig, ax = plt.subplots(figsize=(4.8, 4.0))
    values = panel.to_numpy(dtype=float)
    vmax = float(np.nanpercentile(np.abs(values), 99))
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    x0 = mdates.date2num(panel.columns[0])
    x1 = mdates.date2num(panel.columns[-1])
    im = ax.imshow(
        values, aspect="auto", interpolation="nearest",
        cmap=LinearSegmentedColormap.from_list(
            "signed_positions", [ps.ORANGE, "#f7f6f3", ps.BLUE]
        ),
        norm=norm, extent=[x0, x1, len(panel) - 0.5, -0.5],
    )
    ax.set_yticks(np.arange(len(panel.index)))
    ax.set_yticklabels(panel.index, fontsize=5.5)
    ax.tick_params(axis="x", labelsize=6, length=2)
    ax.set_xlim(x0, x1)
    ax.axvline(pd.Timestamp("2016-01-01"), color=ps.INK_2, lw=0.8, ls="--")
    cb = fig.colorbar(im, ax=ax, fraction=0.028, pad=0.015)
    cb.set_label("Signed gross position (% of capital)", fontsize=6)
    cb.ax.tick_params(labelsize=5.5)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(ax.xaxis.get_major_locator())
    )
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.savefig(path, bbox_inches="tight", dpi=220)
    plt.close(fig)


def gross_pnl(res, path: Path) -> None:
    """One cumulative gross-return line, dashed 2016 test marker."""

    d = res.daily.set_index("date")
    fig, ax = plt.subplots(figsize=(4.8, 2.9))
    ax.plot(d.index, d["ret_gross"].cumsum() * 100.0, color=ps.BLUE, lw=1.1)
    ax.axvline(pd.Timestamp("2016-01-01"), color=ps.INK_2, lw=0.8, ls="--")
    ax.axhline(0, color=ps.INK_2, lw=0.6)
    ax.set_ylabel("Cumulative gross return (% of capital)", fontsize=6.5)
    ax.tick_params(labelsize=6)
    ax.grid(True, color=ps.GRID, lw=0.5, alpha=0.6)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(ax.xaxis.get_major_locator())
    )
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.savefig(path, bbox_inches="tight", dpi=220)
    plt.close(fig)


def main() -> None:
    ps.use()
    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    root_order = (
        rank[["root", "sector"]]
        .drop_duplicates()
        .sort_values(["sector", "root"])["root"]
        .tolist()
    )
    settings = v2_rerun.RerunSettings()
    inputs = v2_signals.load_v2_inputs(
        rank, d=settings.d, k=settings.k, min_adv=settings.min_adv
    )
    item = v2_rerun.run_strategy("c", rank, settings, inputs=inputs)
    res = item["result"]
    full = item["performance"].xs("full", level="period").set_index("layer")
    print(
        "C1 full sample: gross {:+.3f}%/yr, all-in net {:+.3f}%/yr, "
        "turnover {:.2f}x/yr".format(
            full.loc["gross", "ann_ret_pct"],
            full.loc["- impact (all)", "ann_ret_pct"],
            full.loc["gross", "turnover_x"],
        )
    )

    OUT.mkdir(parents=True, exist_ok=True)
    heatmap(res, root_order, OUT / "c_mean_reversion_positions.pdf")
    gross_pnl(res, OUT / "c_mean_reversion_pnl.pdf")
    print(f"Wrote {OUT / 'c_mean_reversion_positions.pdf'}")
    print(f"Wrote {OUT / 'c_mean_reversion_pnl.pdf'}")


if __name__ == "__main__":
    main()

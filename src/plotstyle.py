"""Publication style for all backtest figures (journal-grade, LaTeX text).

Conventions:
- Text is set by LaTeX (Computer Modern) when a TeX installation is found,
  otherwise by matplotlib mathtext with the Computer Modern font set; labels
  are written once in LaTeX and ``tex`` makes them safe for either renderer.
- Single-column width 3.4 in, full width 7.0 in; 8-9 pt text.
- Ink is near-black; series colours never colour text.
- Categorical colours follow a fixed, colour-blind-validated order (blue,
  orange, aqua, yellow); ordered quantities (cumulative cost layers) use one
  blue ramp from light to dark.
- Axes: left/bottom spines only, outward ticks, solid hairline y-grid, a
  darker solid zero line where zero is meaningful.
- Figures are saved as vector PDF plus 600 dpi PNG.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

from . import config

INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
ZERO = "#8a8984"
SURFACE = "#ffffff"

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
CATEGORICAL = [BLUE, ORANGE, AQUA, YELLOW]
# Ordinal blue ramp (steps 250, 400, 550, 700): light = least, dark = most.
ORDINAL_BLUE = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]

SINGLE_COL = 3.4
FULL_WIDTH = 7.0
FIG_DIR = config.ROOT / "output" / "figures"

_USETEX = False


def use(usetex: bool | None = None, display_dpi: int = 200) -> bool:
    """Apply the publication style globally.

    Args:
        usetex: Force LaTeX on/off; ``None`` uses LaTeX if ``latex`` and
            ``dvipng`` are on the PATH.
        display_dpi: Resolution of inline notebook figures.

    Returns:
        Whether LaTeX text rendering is active.
    """

    global _USETEX
    _USETEX = bool(shutil.which("latex") and shutil.which("dvipng")) if usetex is None else usetex
    mpl.rcParams.update({
        "text.usetex": _USETEX,
        "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
        "font.family": "serif",
        "font.serif": ["Computer Modern Roman", "CMU Serif", "DejaVu Serif"],
        "mathtext.fontset": "cm",
        "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7.5,
        "axes.titlelocation": "left", "axes.titlepad": 6,
        "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": INK_2,
        "xtick.color": INK_2, "ytick.color": INK_2,
        "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.major.size": 3, "ytick.major.size": 3,
        "xtick.direction": "out", "ytick.direction": "out",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID,
        "grid.linewidth": 0.5, "grid.linestyle": "-", "axes.axisbelow": True,
        "lines.linewidth": 1.1, "lines.markersize": 3.5,
        "legend.frameon": False, "legend.handlelength": 1.6,
        "axes.prop_cycle": mpl.cycler(color=CATEGORICAL),
        "figure.dpi": display_dpi, "savefig.dpi": 600,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    return _USETEX


def tex(s: str) -> str:
    """Make a LaTeX-authored label safe for the active renderer.

    Labels are written with LaTeX escapes (``\\%``, ``\\&``, ``\\,``); without
    usetex those escapes are rendered literally, so they are undone.
    """

    if _USETEX:
        return s
    for a, b in ((r"\%", "%"), (r"\&", "&"), (r"\,", " "), (r"\;", " "), ("~", " "), (r"\textendash", "-")):
        s = s.replace(a, b)
    return s


def zero_line(ax, axis: str = "y") -> None:
    """Solid reference line at zero, darker than the grid."""

    (ax.axhline if axis == "y" else ax.axvline)(0, color=ZERO, lw=0.7, zorder=1)


def panel_label(ax, letter: str) -> None:
    """Bold panel tag, e.g. (a), at the top-left outside the axes."""

    ax.text(-0.02, 1.02, tex(rf"\textbf{{({letter})}}") if _USETEX else f"({letter})",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9, fontweight="bold")


def end_label(ax, x, y, text: str, color: str = INK, dy: float = 0.0) -> None:
    """Direct label at the right end of a line (text in ink, not series colour)."""

    ax.annotate(tex(text), xy=(x, y), xytext=(4, dy), textcoords="offset points",
                va="center", ha="left", fontsize=7.5, color=color)


def save(fig, name: str, directory: str | Path | None = None, formats=("pdf", "png")) -> list[Path]:
    """Save a figure as vector PDF and 600 dpi PNG under ``output/figures``."""

    out = Path(directory or FIG_DIR)
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / f"{name}.{ext}" for ext in formats]
    for p in paths:
        fig.savefig(p)
    return paths


def finalize(fig, title: str | None = None, legend_from=None, ncol: int = 4):
    """Lay out a figure: optional figure title, one shared legend below.

    Space for the title and legend is reserved in inches, so the result does
    not depend on the figure height.

    Args:
        fig: Figure to lay out.
        title: Figure-level title (left aligned), already LaTeX-safe.
        legend_from: Axes (or list of axes) whose labelled artists form one
            legend under the panels; duplicate labels are dropped.
        ncol: Columns of the shared legend.
    """

    height = fig.get_size_inches()[1]
    top = 1.0 - (0.24 / height if title else 0.0)
    bottom = 0.0
    if legend_from is not None:
        axes = legend_from if isinstance(legend_from, (list, tuple)) else [legend_from]
        seen, handles, labels = set(), [], []
        for ax in axes:
            for h, lab in zip(*ax.get_legend_handles_labels()):
                if lab not in seen:
                    seen.add(lab), handles.append(h), labels.append(lab)
            if ax.get_legend() is not None:
                ax.get_legend().remove()
        rows = -(-len(labels) // ncol)
        bottom = (0.04 + 0.15 * rows) / height
        fig.legend(handles, labels, loc="lower center", ncol=ncol, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, bottom, 1, top))
    if title:
        fig.suptitle(title, x=0.01, y=0.995, ha="left", va="top", fontsize=9.5)
    return fig

"""Vector figures for the final deck (presentations/final/figures/*.pdf).

Each figure is sized for a slide column (width in cm below) so that the
fonts print at about 7 pt on the slide; ``\\includegraphics[width=\\linewidth]``
then needs almost no rescaling. Captions live in LaTeX, not in the figure.

Usage:
    python scripts/make_slide_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.dates  # noqa: F401  (mpl.dates used in e_nav_timing)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config, nelson_siegel as ns, panel, plotstyle as ps  # noqa: E402

OUT = ROOT / "presentations" / "final" / "figures"
CM = 1 / 2.54
SLIDE_FONT = {"font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
              "legend.fontsize": 6.2, "lines.linewidth": 1.0, "lines.markersize": 3.6}


def cl_fits() -> pd.DataFrame:
    """Daily Nelson-Siegel fits of WTI crude oil (rolling-SSR lambda, D-022)."""

    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    contract = panel.build_backtest_panel(rank.loc[rank["root"].eq("CL")], d=5, k=5)["contract"]
    wide = ns.wide_curve(ns.eligible_curve(contract))
    fits = ns.fit_ns(wide, ns.lambda_series(wide, "rolling_ssr"))
    return fits.merge(wide, on=["date", "root"])


def e_curve_snapshots(fits: pd.DataFrame, dates: dict[str, str], width_cm: float = 6.4,
                      height_cm: float = 5.6) -> Path:
    """Four contract prices and the fitted NS curve on a few dates, relative to the nearest contract."""

    fig, ax = plt.subplots(figsize=(width_cm * CM, height_cm * CM))
    colors = [ps.BLUE, ps.ORANGE, ps.AQUA]
    grid = np.linspace(0.05, 4.2, 200)
    for color, (date, label) in zip(colors, dates.items()):
        r = fits.loc[fits["date"].eq(pd.Timestamp(date))].iloc[0]
        m = np.array([r[f"M{k}"] for k in range(4)])
        f = np.array([r[f"F{k}"] for k in range(4)])
        curve = ns.loadings(grid, np.array(r["lam"])) @ np.array([r["bL"], r["bS"], r["bC"]])
        base = f[0]
        ax.plot(grid, (curve / base - 1) * 100, color=color, lw=1.0)
        ax.plot(m, (f / base - 1) * 100, "o", color=color, mec=ps.SURFACE, mew=0.6,
                label=ps.tex(rf"{label}: $\beta_L={r['bL']:.1f}$, $\beta_S={r['bS']:+.1f}$, $\beta_C={r['bC']:+.1f}$"))
    ps.zero_line(ax)
    ax.set_xlim(0, 4.3)
    ax.set_xlabel(ps.tex(r"Months to last trading day, $M$"))
    ax.set_ylabel(ps.tex(r"$F_t(M)/F_t(M_1)-1$ (\%)"))
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.24), ncol=1, handletextpad=0.3,
              borderaxespad=0.0, labelspacing=0.25)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "e_curve_snapshots.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def stylized_curves(width_cm: float = 6.4, height_cm: float = 4.8) -> Path:
    """Stylized contango and backwardation curves with the calendar spread C_t marked."""

    from scipy.interpolate import PchipInterpolator

    t = np.arange(1, 7)
    curves = {"Contango": (np.array([62, 67, 69.8, 71.5, 72.6, 73.3]), ps.BLUE),
              "Backwardation": (np.array([80, 75.5, 73.4, 72.1, 71.3, 70.8]), ps.ORANGE)}
    fig, ax = plt.subplots(figsize=(width_cm * CM, height_cm * CM))
    grid = np.linspace(1, 6, 200)
    for label, (y, color) in curves.items():
        ax.plot(grid, PchipInterpolator(t, y)(grid), color=color, lw=1.1)
        ax.plot(t, y, "o", color=color, mec=ps.SURFACE, mew=0.6, label=label)
    x0 = 0.62
    for (y1, y2), va, txt in (((62, 67), "top", r"$C_t<0$"), ((80, 75.5), "bottom", r"$C_t>0$")):
        for y in (y1, y2):
            ax.plot([x0 - 0.12, 1 if y == y1 else 2], [y, y], color=ps.INK_2, lw=0.5, ls=(0, (2, 2)))
        ax.annotate("", xy=(x0, y1), xytext=(x0, y2),
                    arrowprops=dict(arrowstyle="<->", color=ps.INK, lw=0.7, shrinkA=0, shrinkB=0))
        ax.text(x0 + 0.06, y1 + (-0.6 if va == "top" else 0.6), ps.tex(txt), ha="left", va=va, fontsize=6.8)
    ax.set_xlim(0.4, 6.3)
    ax.set_ylim(58.5, 82.5)
    ax.set_xticks(t, [ps.tex(rf"$T_{k}$") for k in t])
    ax.set_yticks([])
    ax.grid(False)
    ax.set_xlabel(ps.tex("Delivery month (maturity)"))
    ax.set_ylabel(ps.tex("Futures price"))
    ax.legend(loc="lower right", handletextpad=0.3, borderaxespad=0.1)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "stylized_curves.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def ns_r2_gains(block: int = 21, n_boot: int = 2000,
                holdout: tuple[int, ...] | None = (1, 2)) -> dict[str, tuple[pd.DataFrame, dict]]:
    """Block-bootstrap medians of the daily leave-one-contract-out R^2 gains, per root.

    ``slope`` = LOO R^2(L+S) - LOO R^2(L); ``curvature`` = LOO R^2(L+S+C) - LOO R^2(L+S).
    ``holdout=(1, 2)`` holds out only the 2nd and 3rd contracts (interpolation);
    ``None`` holds out all four, including the end points (extrapolation).
    Medians, because LOO R^2 has very heavy left tails.
    """

    from src import horizon

    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    contract = panel.build_backtest_panel(rank, d=5, k=5)["contract"]
    wide = ns.wide_curve(ns.eligible_curve(contract))
    q = ns.fit_quality(wide, ns.lambda_series(wide, "rolling_ssr"), holdout=holdout)
    q["slope"] = q["loo_LS"] - q["loo_L"]
    q["curvature"] = q["loo_LSC"] - q["loo_LS"]
    return {c: horizon.block_bootstrap_mean(q, c, block=block, n_boot=n_boot, stat="median")
            for c in ("slope", "curvature")}


def e_r2_gain_distributions(gains: dict, width_cm: float = 14.0, height_cm: float = 4.6,
                            alpha: float = 0.05) -> Path:
    """Back-to-back bootstrap histograms of the two R^2 gains for every commodity."""

    (s_sum, s_draws), (c_sum, c_draws) = gains["slope"], gains["curvature"]
    order = s_sum.sort_values("mean")["root"].tolist()
    s_sum, c_sum = s_sum.set_index("root"), c_sum.set_index("root")
    allv = np.concatenate([d for d in s_draws.values()] + [d for d in c_draws.values()])
    lo, hi = min(np.quantile(allv, 0.0005), 0.0), np.quantile(allv, 0.9995)
    bins = np.linspace(lo, hi, 90)
    fig, ax = plt.subplots(figsize=(width_cm * CM, height_cm * CM))
    grey = "#b9b8b3"
    for i, root in enumerate(order):
        for side, summ, draws, color in ((-1, s_sum, s_draws, ps.BLUE), (1, c_sum, c_draws, ps.ORANGE)):
            r = summ.loc[root]
            dens, edges = np.histogram(draws[root], bins=bins)
            w = dens / max(dens.max(), 1) * 0.42
            fill = color if r["p_value"] < alpha else grey
            nz = w > 0
            ax.barh(edges[:-1][nz], side * w[nz], height=np.diff(edges)[nz], left=i, align="edge",
                    color=fill, lw=0)
            ax.plot([i + side * 0.06] * 2, [r["ci_lo"], r["ci_hi"]], color=ps.INK, lw=0.7)
            ax.plot(i + side * 0.06, r["mean"], "o", color=ps.INK, ms=1.8)
    ps.zero_line(ax)
    ax.set_xticks(range(len(order)), order)
    ax.tick_params(axis="x", length=0, labelsize=5.8)
    ax.set_xlim(-0.6, len(order) - 0.4)
    ax.set_ylabel(ps.tex(r"Median gain in interior LOO $R^2$"))
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    handles = [Patch(color=ps.BLUE, label=ps.tex(r"Left: adding $\beta_S$ to $\beta_L$")),
               Patch(color=ps.ORANGE, label=ps.tex(r"Right: adding $\beta_C$ to $\beta_L+\beta_S$")),
               Patch(color=grey, label=ps.tex(rf"Not significant, $p\geq{alpha:g}$")),
               Line2D([], [], color=ps.INK, marker="o", ms=1.8, lw=0.7, label=ps.tex(r"Median and 95\% CI"))]
    ax.legend(handles=handles, loc="lower left", ncol=4, bbox_to_anchor=(0.0, 1.0), borderaxespad=0.2,
              handletextpad=0.4, columnspacing=1.2)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "e_r2_gains.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


PAPER_SAMPLE = ("1992-01-02", "2019-06-28")


def e_paper_strategy() -> tuple[dict, pd.DataFrame]:
    """NS slope strategy on the paper universe with the paper lambda, and the marks."""

    from src import marks, specs

    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    contract = panel.build_backtest_panel(rank, d=5, k=5)["contract"]
    mk = marks.build_marks(contract, specs.load_contract_specs())
    return ns.build_slope_strategy(contract, mk, rule="paper", roots=ns.PAPER_ROOTS), mk


def e_horizon_decay(st: dict, mk: pd.DataFrame, max_lead: int = 10,
                    width_cm: float = 6.6, height_cm: float = 4.8) -> Path:
    """Mean signed one-day spread return over [t+a, t+a+1] for a = 0..max_lead, 95% NW CI."""

    from src import horizon

    fwd = horizon.forward_returns(st["pairs"], mk, [(a, a + 1) for a in range(max_lead + 1)])
    keep = fwd["date"].between(*PAPER_SAMPLE)
    prof = horizon.horizon_profile(fwd.loc[keep], st["signal"])
    x = np.arange(len(prof))
    ci = 1.96 * prof["mean_bps"] / prof["t_nw"]
    fig, ax = plt.subplots(figsize=(width_cm * CM, height_cm * CM))
    colors = [ps.ORANGE] + [ps.BLUE] * (len(prof) - 1)
    ax.bar(x, prof["mean_bps"], width=0.68, color=colors, edgecolor=ps.SURFACE, lw=0.4)
    ax.errorbar(x, prof["mean_bps"], yerr=ci, fmt="none", ecolor=ps.INK, elinewidth=0.6, capsize=1.5)
    ps.zero_line(ax)
    ax.set_xticks(x, [str(a) for a in range(max_lead + 1)])
    ax.tick_params(axis="x", length=0)
    ax.set_xlabel(ps.tex(r"Lag $a$ in days, window $[t+a,\,t+a+1]$"))
    ax.set_ylabel(ps.tex(r"Signed spread return (bp)"))
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=ps.ORANGE, label=ps.tex(r"$a=0$: not tradable")),
                       Patch(color=ps.BLUE, label=ps.tex(r"$a\geq1$: tradable"))], loc="upper right",
              bbox_to_anchor=(1.0, 1.02))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "e_horizon_decay.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def e_nav_timing(st: dict, mk: pd.DataFrame, width_cm: float = 6.6, height_cm: float = 4.8) -> Path:
    """Cumulative return at the paper timing and at the tradable t+1 fill, gross and net of TC1."""

    from src import costs, simulate, sizing

    legs = sizing.legs_from_signal(st["signal"], st["pairs"])
    tc1 = costs.paper_scenarios()["TC1"]
    runs = {
        "paper": simulate.same_settle(legs, mk),
        "tradable": legs,
    }
    fig, ax = plt.subplots(figsize=(width_cm * CM, height_cm * CM))
    style = {"paper": ps.ORANGE, "tradable": ps.BLUE}
    names = {"paper": r"Paper", "tradable": r"Tradable"}
    for key, lg in runs.items():
        res = simulate.simulate(lg, mk, simulate.SimConfig(capital=1e6, cost=tc1))
        d = res.daily.set_index("date").loc[PAPER_SAMPLE[0]:PAPER_SAMPLE[1]]
        for col, ls, tag in (("ret_gross", "-", "gross"), ("ret_net_all", (0, (3, 1.5)), "net of TC1")):
            ann = d[col].mean() * 252 * 100
            ax.plot(d.index, d[col].cumsum() * 100, color=style[key], ls=ls, lw=1.0,
                    label=ps.tex(rf"{names[key]}, {tag}, ${ann:+.2f}\%$"))
    ps.zero_line(ax)
    ax.set_ylabel(ps.tex(r"Cumulative return (\%)"))
    ax.xaxis.set_major_locator(mpl.dates.YearLocator(5))
    ax.xaxis.set_major_formatter(mpl.dates.DateFormatter("%Y"))
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.13), ncol=2, fontsize=5.8, handlelength=2.2,
              labelspacing=0.25, columnspacing=1.0)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "e_nav_timing.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


SECTOR_ORDER = ["Energy", "Metals", "Grains", "Oilseeds", "Softs", "Livestock", "Industrials"]


def e_root_data(block: int = 21, n_boot: int = 2000) -> tuple[pd.DataFrame, dict]:
    """Per-commodity gross Sharpe at both timings and the bootstrap of the median interior LOO R^2.

    All 24 commodities, paper lambda, 1986-2026, USD 1m.
    """

    from src import horizon, marks, simulate, sizing, specs

    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    contract = panel.build_backtest_panel(rank, d=5, k=5)["contract"]
    mk = marks.build_marks(contract, specs.load_contract_specs())
    st = ns.build_slope_strategy(contract, mk, rule="paper")
    legs = sizing.legs_from_signal(st["signal"], st["pairs"])
    out = {}
    for name, lg in (("paper", simulate.same_settle(legs, mk)), ("tradable", legs)):
        res = simulate.simulate(lg, mk, simulate.SimConfig(capital=1e6))
        g = res.by_root.assign(date=lambda d: pd.to_datetime(d["date"])).pivot_table(
            index="date", columns="root", values="pnl_gross", aggfunc="sum") / 1e6
        out[name] = g.mean() / g.std() * np.sqrt(252)
    wide = ns.wide_curve(ns.eligible_curve(contract))
    q = ns.fit_quality(wide, ns.lambda_series(wide, "paper"), holdout=(1, 2))
    summ, draws = horizon.block_bootstrap_mean(q, "loo_LSC", block=block, n_boot=n_boot, stat="median")
    table = pd.DataFrame(out).join(summ.set_index("root")[["mean", "ci_lo", "ci_hi"]].rename(
        columns={"mean": "loo", "ci_lo": "loo_lo", "ci_hi": "loo_hi"}))
    table["sector"] = rank.groupby("root")["sector"].first()
    return table, draws


def e_root_discussion(table: pd.DataFrame, draws: dict, width_cm: float = 14.0, height_cm: float = 5.0) -> Path:
    """(a) Gross Sharpe by commodity at both timings, (b) bootstrap of the median interior LOO R^2."""

    t = table.assign(sec=pd.Categorical(table["sector"], SECTOR_ORDER, ordered=True))
    t = t.sort_values(["sec", "paper"], ascending=[True, False])
    roots = t.index.tolist()
    x = np.arange(len(roots))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(width_cm * CM, height_cm * CM), sharex=True,
                                 gridspec_kw={"height_ratios": [1.0, 1.0], "hspace": 0.12})
    a1.bar(x - 0.19, t["paper"], 0.38, color=ps.ORANGE, edgecolor=ps.SURFACE, lw=0.3,
           label=ps.tex(r"Paper timing $[t,\,t+1]$"))
    a1.bar(x + 0.19, t["tradable"], 0.38, color=ps.BLUE, edgecolor=ps.SURFACE, lw=0.3,
           label=ps.tex(r"Tradable $[t+1,\,t+2]$"))
    ps.zero_line(a1)
    a1.set_ylabel(ps.tex("Gross Sharpe"))
    a1.legend(loc="lower left", ncol=2, borderaxespad=0.1, fontsize=5.6, handlelength=1.2, columnspacing=0.8)
    lo = min(np.quantile(d, 0.001) for d in draws.values())
    bins = np.linspace(lo, 1.0, 70)
    for i, root in enumerate(roots):
        dens, edges = np.histogram(draws[root], bins=bins)
        w = dens / max(dens.max(), 1) * 0.42
        nz = w > 0
        a2.barh(edges[:-1][nz], w[nz], height=np.diff(edges)[nz], left=i, align="edge", color=ps.BLUE, lw=0)
        a2.plot([i - 0.06] * 2, [t.loc[root, "loo_lo"], t.loc[root, "loo_hi"]], color=ps.INK, lw=0.7)
        a2.plot(i - 0.06, t.loc[root, "loo"], "o", color=ps.INK, ms=1.8)
    a2.set_ylabel(ps.tex(r"Interior LOO $R^2$"))
    a2.set_xticks(x, roots)
    a2.tick_params(axis="x", length=0, labelsize=5.8)
    a2.set_xlim(-0.6, len(roots) - 0.4)
    bounds = t["sector"].ne(t["sector"].shift()).to_numpy().nonzero()[0]
    for k, start in enumerate(bounds):
        end = bounds[k + 1] if k + 1 < len(bounds) else len(roots)
        for ax in (a1, a2):
            if start:
                ax.axvline(start - 0.5, color=ps.GRID, lw=0.8)
        label = {"Industrials": "Ind."}.get(t["sector"].iloc[start], t["sector"].iloc[start])
        a1.text((start + end - 1) / 2, 1.02, label, transform=a1.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=6.0, color=ps.INK_2)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "e_root_discussion.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    ps.use()
    mpl.rcParams.update(SLIDE_FONT)
    print(stylized_curves())
    gains = ns_r2_gains()
    for name, (summ, _) in gains.items():
        sig = summ["p_value"] < 0.05
        print(f"{name}: significant +{int((sig & (summ['mean'] > 0)).sum())} "
              f"-{int((sig & (summ['mean'] < 0)).sum())} of {len(summ)}")
    print(e_r2_gain_distributions(gains))
    st, mk = e_paper_strategy()
    print(e_horizon_decay(st, mk))
    print(e_nav_timing(st, mk))
    print(e_root_discussion(*e_root_data()))
    fits = cl_fits()
    print(e_curve_snapshots(fits, {
        "2020-04-17": "2020-04-17",
        "2003-04-04": "2003-04-04",
        "2026-04-09": "2026-04-09",
    }))


if __name__ == "__main__":
    main()

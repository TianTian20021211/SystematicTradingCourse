"""Publication figures for the alpha-combination study (D-030).

Same conventions as ``figures``: call ``plotstyle.use()`` first; titles say
what is measured and how; 95% intervals are bootstrap percentile intervals
unless stated; blue = primary series, orange = contrast/negative.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D

from . import plotstyle as ps
from .figures import BAR, MARKER, _date_axis, _shade_test

DIVERGING = LinearSegmentedColormap.from_list("ic", [ps.ORANGE, "#f7f6f2", ps.BLUE])
RULE_LABELS = {"sign": "TS sign", "linear": "TS linear", "band": "TS cost band", "xs": "XS top/bottom 5"}
RULE_COLORS = {"sign": ps.BLUE, "linear": ps.AQUA, "band": ps.YELLOW, "xs": ps.ORANGE}


def horizon_label(target: str) -> str:
    """``fwd_1_6`` -> ``[t+1, t+6]`` (``[t, t+1]`` for the paper timing)."""

    a, b = (int(x) for x in target.split("_")[1:])
    lo = "t" if a == 0 else f"t+{a}"
    return rf"$[{lo},\,t+{b}]$"


def block_sensitivity(sens: pd.DataFrame, chosen: int):
    """(a) Bootstrap SE and (b) bootstrap mean of the cross-root mean IC vs block length."""

    allr = sens.loc[sens["root"].eq("ALL")]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH, 3.0))
    for score, g in allr.groupby("score"):
        a1.plot(g["block"], g["se"], color="#b9b8b3", lw=0.7)
        a2.plot(g["block"], g["boot_mean"], color="#b9b8b3", lw=0.7)
    med = allr.groupby("block")["se"].median()
    a1.plot(med.index, med, color=ps.BLUE, lw=1.6, label=ps.tex("Median over factors"), **MARKER)
    a1.plot([], [], color="#b9b8b3", lw=0.7, label=ps.tex("One factor"))
    for ax in (a1, a2):
        ax.axvline(chosen, color=ps.ORANGE, lw=1.0, ls="--")
        ax.set_xscale("log")
        ax.set_xticks(sorted(allr["block"].unique()), [str(b) for b in sorted(allr["block"].unique())])
        ax.set_xlabel(ps.tex("Block length (trading days)"))
    a1.plot([], [], color=ps.ORANGE, lw=1.0, ls="--", label=ps.tex(rf"Chosen block: {chosen} days"))
    a1.set_ylim(bottom=0)
    a1.set_ylabel(ps.tex("Bootstrap s.e. of mean IC"))
    a1.set_title(ps.tex("Standard error rises, then plateaus"))
    ps.zero_line(a2)
    a2.set_ylabel(ps.tex("Bootstrap mean of mean IC"))
    a2.set_title(ps.tex("Point estimate does not depend on the block"))
    ps.panel_label(a1, "a"), ps.panel_label(a2, "b")
    title = ps.tex(r"Choosing the day-block length: cross-commodity mean time-series IC of each factor"
                   + "\n" + r"with the $[t+1,\,t+6]$ spread return, train 1986--2005, joint moving-block bootstrap")
    return ps.finalize(fig, title, legend_from=a1, ncol=3)


def screen_heatmap(screen: pd.DataFrame, factor_order: list[str]):
    """Mean IC of every factor at every horizon; markers show the screen outcome."""

    targets = list(dict.fromkeys(screen["target"]))
    ic = screen.pivot(index="score", columns="target", values="mean_ic").reindex(index=factor_order, columns=targets)
    rule = screen.pivot(index="score", columns="target", values="rule").reindex(index=factor_order, columns=targets)
    nsig = screen.pivot(index="score", columns="target", values="n_sig").reindex(index=factor_order, columns=targets)
    lim = np.nanmax(np.abs(ic.to_numpy()))
    fig, ax = plt.subplots(figsize=(ps.FULL_WIDTH, 4.2))
    im = ax.imshow(ic.to_numpy(), cmap=DIVERGING, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    for i in range(ic.shape[0]):
        for j in range(ic.shape[1]):
            mark = {"primary": r"$\bullet$", "fallback": r"$\circ$"}.get(rule.iat[i, j], "")
            ax.text(j, i, ps.tex(rf"{ic.iat[i, j]:+.3f} ({int(nsig.iat[i, j])}) {mark}"), ha="center", va="center",
                    fontsize=6.5, color=ps.INK)
    ax.set_xticks(range(len(targets)), [ps.tex(horizon_label(t)) for t in targets])
    ax.set_yticks(range(len(factor_order)), [ps.tex(f.replace("_", r"\_")) for f in factor_order])
    ax.tick_params(length=0)
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label(ps.tex("Mean time-series IC"))
    ax.set_xlabel(ps.tex("Forecast horizon (signal at the $t$ settle)"))
    handles = [Line2D([], [], ls="", marker="o", color=ps.INK, ms=3, label=ps.tex(r"Primary: significant on $\geq$ half of commodities")),
               Line2D([], [], ls="", marker="o", mfc="none", color=ps.INK, ms=3, label=ps.tex(r"Fallback: mean-IC CI excludes 0, $\geq 2/3$ same sign"))]
    ax.legend(handles=handles)
    title = ps.tex(r"Factor screen, train 1986--2005: mean time-series IC across commodities" + "\n"
                   + r"(number of commodities with bootstrap $p<0.05$ and the mean's sign in parentheses)")
    return ps.finalize(fig, title, legend_from=ax, ncol=2)


def factor_correlation(panel: pd.DataFrame, factors: list[str]):
    """Pooled Spearman correlation between factors (train rows)."""

    c = panel[factors].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(ps.SINGLE_COL + 1.6, 4.0))
    im = ax.imshow(c.to_numpy(), cmap=DIVERGING, norm=TwoSlopeNorm(0, -1, 1))
    for i in range(len(factors)):
        for j in range(len(factors)):
            ax.text(j, i, f"{c.iat[i, j]:.2f}", ha="center", va="center", fontsize=5.5, color=ps.INK)
    labels = [ps.tex(f.replace("_", r"\_")) for f in factors]
    ax.set_xticks(range(len(factors)), labels, rotation=90)
    ax.set_yticks(range(len(factors)), labels)
    ax.tick_params(length=0, labelsize=6.5)
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    return ps.finalize(fig, ps.tex(r"Spearman correlation between factors, pooled train rows 1986--2005"))


def model_ic_by_horizon(summary: pd.DataFrame, chosen: dict):
    """Validation mean IC (95% bootstrap CI) of every model at every horizon."""

    targets = list(dict.fromkeys(summary["target"]))
    models = list(dict.fromkeys(summary["model"]))
    fig, axes = plt.subplots(1, len(targets), figsize=(ps.FULL_WIDTH, 3.0), sharey=True)
    for ax, tgt in zip(axes, targets):
        s = summary.loc[summary["target"].eq(tgt)].set_index("model").reindex(models)
        x = np.arange(len(models))
        colors = [ps.ORANGE if m == chosen[tgt] else ps.BLUE for m in models]
        ax.bar(x, s["mean_ic"], color=colors, width=0.7, **BAR)
        ax.errorbar(x, s["mean_ic"], yerr=1.96 * s["se"], fmt="none", ecolor=ps.INK, elinewidth=0.6, capsize=1.2)
        ax.set_xticks(x, [ps.tex(m.replace("_", r"\_")) for m in models], rotation=90, fontsize=5.8)
        ax.tick_params(axis="x", length=0)
        ax.set_title(ps.tex(horizon_label(tgt)), fontsize=8)
        ps.zero_line(ax)
    axes[0].set_ylabel(ps.tex("Mean time-series IC, validation"))
    handles = [plt.Rectangle((0, 0), 1, 1, color=ps.ORANGE, label=ps.tex("Selected: most paired-bootstrap wins")),
               plt.Rectangle((0, 0), 1, 1, color=ps.BLUE, label=ps.tex("Other models"))]
    axes[0].legend(handles=handles)
    title = ps.tex(r"Model zoo out of sample: cross-commodity mean IC of the forecast with the realised spread return,"
                   + "\n" + r"fitted 1986--2005, evaluated 2006--2015, 95\% joint day-block bootstrap CI")
    return ps.finalize(fig, title, legend_from=axes[0], ncol=2)


def model_win_matrix(pairs: pd.DataFrame, target: str):
    """Paired IC differences (row minus column) with significance markers."""

    p = pairs.loc[pairs["target"].eq(target)]
    models = list(dict.fromkeys(p["m1"]))
    d = p.pivot(index="m1", columns="m2", values="diff").reindex(index=models, columns=models)
    w = p.pivot(index="m1", columns="m2", values="win").reindex(index=models, columns=models)
    lim = np.nanmax(np.abs(d.to_numpy()))
    fig, ax = plt.subplots(figsize=(ps.SINGLE_COL + 1.6, 3.8))
    im = ax.imshow(d.to_numpy(), cmap=DIVERGING, norm=TwoSlopeNorm(0, -lim, lim))
    for i in range(len(models)):
        for j in range(len(models)):
            if i != j:
                star = "*" if w.iat[i, j] is True else ""
                ax.text(j, i, f"{d.iat[i, j] * 100:+.1f}{star}", ha="center", va="center", fontsize=5.6, color=ps.INK)
    labels = [ps.tex(m.replace("_", r"\_")) for m in models]
    ax.set_xticks(range(len(models)), labels, rotation=90)
    ax.set_yticks(range(len(models)), labels)
    ax.tick_params(length=0, labelsize=6.5)
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02).set_label(ps.tex("IC(row) $-$ IC(column)"))
    title = ps.tex(rf"Paired model comparison, {horizon_label(target)}, validation 2006--2015:" + "\n"
                   + r"IC difference $\times 100$; * = 95\% paired bootstrap CI above 0 (a win)")
    return ps.finalize(fig, title)


def model_diff_distributions(draws: dict, chosen: str, target: str):
    """Bootstrap distributions of IC(chosen) - IC(other) for every other model."""

    others = [m for m in draws if m != chosen]
    fig, ax = plt.subplots(figsize=(ps.FULL_WIDTH, 2.9))
    for i, m in enumerate(others):
        d = draws[chosen] - draws[m]
        dens, edges = np.histogram(d, bins=40, density=True)
        lo, hi = np.quantile(d, [0.025, 0.975])
        color = ps.BLUE if lo > 0 else (ps.ORANGE if hi < 0 else "#a9a8a4")
        ax.barh(edges[:-1], dens / dens.max() * 0.42, height=np.diff(edges), left=i, align="edge", color=color, lw=0)
        ax.plot([i - 0.08] * 2, [lo, hi], color=ps.INK, lw=0.8)
        ax.plot(i - 0.08, d.mean(), "o", color=ps.INK, ms=2.6)
    ps.zero_line(ax)
    ax.set_xticks(range(len(others)), [ps.tex(m.replace("_", r"\_")) for m in others])
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel(ps.tex(rf"IC({chosen.replace('_', chr(92) + '_')}) $-$ IC(model)"))
    handles = [plt.Rectangle((0, 0), 1, 1, color=ps.BLUE, label=ps.tex("Selected model significantly better")),
               plt.Rectangle((0, 0), 1, 1, color="#a9a8a4", label=ps.tex("Not significant")),
               plt.Rectangle((0, 0), 1, 1, color=ps.ORANGE, label=ps.tex("Significantly worse"))]
    ax.legend(handles=handles)
    title = ps.tex(rf"Is the selected model better? Paired day-block bootstrap of the IC difference, {horizon_label(target)}, validation")
    return ps.finalize(fig, title, legend_from=ax, ncol=3)


def forecast_bins(bins: dict[str, pd.DataFrame], period: str):
    """Mean realised spread return by own-history forecast decile, one panel per horizon."""

    fig, axes = plt.subplots(1, len(bins), figsize=(ps.FULL_WIDTH, 2.7))
    for ax, (tgt, b) in zip(np.atleast_1d(axes), bins.items()):
        x = b["bin"].to_numpy()
        ax.bar(x, b["mean_bps"], color=ps.BLUE, width=0.75, **BAR)
        ax.errorbar(x, b["mean_bps"], yerr=1.96 * b["mean_bps"] / b["t_nw"].replace(0, np.nan), fmt="none",
                    ecolor=ps.INK, elinewidth=0.6, capsize=1.2)
        ps.zero_line(ax)
        ax.set_xticks([1, len(x)], ["low", "high"])
        ax.tick_params(axis="x", length=0)
        ax.set_title(ps.tex(horizon_label(tgt)), fontsize=8)
    np.atleast_1d(axes)[0].set_ylabel(ps.tex("Realised spread return (bp)"))
    title = ps.tex(rf"Binned forecast vs realised target, {period}: mean spread return by the forecast's own-history"
                   + "\n" + r"decile per commodity (ex ante), averaged across commodities, 95\% NW CI")
    return ps.finalize(fig, title)


def rolling_ic(series: dict[str, pd.Series], test_start: str | None = None):
    """Rolling 252-day mean time-series IC of the forecasts, one line per horizon."""

    fig, ax = plt.subplots(figsize=(ps.FULL_WIDTH, 2.9))
    colors = ps.ORDINAL_BLUE + [ps.ORANGE]
    for color, (tgt, s) in zip(colors, series.items()):
        ax.plot(s.index, s, color=color, lw=0.9, label=ps.tex(horizon_label(tgt)))
    ps.zero_line(ax)
    _date_axis(ax)
    _shade_test(ax, test_start)
    ax.set_ylabel(ps.tex("Rolling 252-day IC"))
    title = ps.tex(r"Forecast IC through time: rolling 252-day time-series IC with the realised spread return,"
                   + "\n" + r"mean across commodities (1986--2005 in sample, 2006--2015 validation)")
    return ps.finalize(fig, title, legend_from=ax, ncol=len(series))


def yearly_root_ic(table: pd.DataFrame, target: str, root_order: list[str]):
    """Commodity x year heatmap of the time-series IC of one forecast."""

    w = table.pivot(index="root", columns="year", values="ic").reindex(root_order)
    lim = np.nanquantile(np.abs(w.to_numpy()), 0.98)
    fig, ax = plt.subplots(figsize=(ps.FULL_WIDTH, 4.0))
    im = ax.imshow(w.to_numpy(), cmap=DIVERGING, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.set_yticks(range(len(w)), w.index, fontsize=6.5)
    yrs = list(w.columns)
    step = max(1, len(yrs) // 15)
    ax.set_xticks(range(0, len(yrs), step), [str(y) for y in yrs[::step]], fontsize=6.5)
    ax.tick_params(length=0)
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02).set_label(ps.tex("Spearman IC within the year"))
    title = ps.tex(rf"Forecast IC by commodity and year, {horizon_label(target)} (blue = forecast right, orange = wrong)")
    return ps.finalize(fig, title)


def ic_vs_characteristics(table: pd.DataFrame, chars: dict[str, str], target: str):
    """Scatter of per-commodity IC against commodity characteristics."""

    fig, axes = plt.subplots(1, len(chars), figsize=(ps.FULL_WIDTH, 2.6), sharey=True)
    for ax, (col, label) in zip(axes, chars.items()):
        ax.scatter(table[col], table["ic"], s=14, color=ps.BLUE, edgecolor=ps.SURFACE, lw=0.5, zorder=3)
        for _, r in table.iterrows():
            ax.annotate(r["root"], (r[col], r["ic"]), fontsize=5, color=ps.INK_2, xytext=(2, 2), textcoords="offset points")
        rho = table[[col, "ic"]].corr(method="spearman").iat[0, 1]
        ax.set_xlabel(ps.tex(label), fontsize=7)
        ax.set_title(ps.tex(rf"Spearman $\rho={rho:+.2f}$"), fontsize=7.5)
        ps.zero_line(ax)
    axes[0].set_ylabel(ps.tex("Time-series IC (validation)"))
    title = ps.tex(rf"Where does the forecast work? Per-commodity IC, {horizon_label(target)}, vs liquidity and trading costs")
    return ps.finalize(fig, title)


def strategy_grid(perf: pd.DataFrame, period: str = "valid"):
    """Gross and all-in net Sharpe of every horizon x rule (validation)."""

    p = perf.loc[perf["period"].eq(period)]
    targets = list(dict.fromkeys(p["target"]))
    rules = list(dict.fromkeys(p["rule"]))
    fig, axes = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH, 2.9), sharey=True)
    width = 0.8 / len(rules)
    for ax, layer, name in zip(axes, ("gross", "- impact (all)"), ("Gross", "Net of all costs")):
        for i, rule in enumerate(rules):
            s = p.loc[p["layer"].eq(layer) & p["rule"].eq(rule)].set_index("target").reindex(targets)
            ax.bar(np.arange(len(targets)) + (i - (len(rules) - 1) / 2) * width, s["sharpe"], width,
                   color=RULE_COLORS[rule], label=ps.tex(RULE_LABELS[rule]), **BAR)
        ax.set_xticks(range(len(targets)), [ps.tex(horizon_label(t)) for t in targets], fontsize=6.5)
        ax.tick_params(axis="x", length=0)
        ax.set_title(ps.tex(name))
        ps.zero_line(ax)
    axes[0].set_ylabel(ps.tex("Annualised Sharpe ratio"))
    ps.panel_label(axes[0], "a"), ps.panel_label(axes[1], "b")
    title = ps.tex(r"Monetising the combined forecast, validation 2006--2015, \$1m: Sharpe by forecast horizon"
                   + "\n" + r"(holding $k$ = horizon length in overlapping sleeves) and portfolio rule")
    return ps.finalize(fig, title, legend_from=axes[0], ncol=4)


def forecast_ic_periods(table: pd.DataFrame):
    """Cross-root mean IC of the selected forecasts by horizon and period (95% CI)."""

    periods = [("train", "Train 1986--2005 (in sample)", "#b9b8b3"), ("valid", "Validation 2006--2015", ps.BLUE),
               ("test", "Test 2016--2026 (read once)", ps.ORANGE)]
    targets = list(dict.fromkeys(table["target"]))
    fig, ax = plt.subplots(figsize=(ps.FULL_WIDTH, 2.9))
    width = 0.26
    for i, (per, label, color) in enumerate(periods):
        s = table.loc[table["period"].eq(per)].set_index("target").reindex(targets)
        x = np.arange(len(targets)) + (i - 1) * width
        ax.bar(x, s["ic"], width, color=color, label=ps.tex(label), **BAR)
        ax.errorbar(x, s["ic"], yerr=[s["ic"] - s["ci_lo"], s["ci_hi"] - s["ic"]], fmt="none",
                    ecolor=ps.INK, elinewidth=0.6, capsize=1.2)
    ps.zero_line(ax)
    ax.set_xticks(range(len(targets)), [ps.tex(horizon_label(t)) for t in targets])
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel(ps.tex("Mean time-series IC"))
    title = ps.tex(r"Does the combined forecast survive out of sample? Cross-commodity mean IC with the realised"
                   + "\n" + r"spread return by horizon and period, 95\% joint day-block bootstrap CI")
    return ps.finalize(fig, title, legend_from=ax, ncol=3)


def root_contribution(contrib: pd.DataFrame, strategy: str):
    """Gross P&L contribution per commodity (bp of capital per year), validation vs test."""

    c = contrib.sort_values("test")
    y = np.arange(len(c))
    fig, ax = plt.subplots(figsize=(ps.FULL_WIDTH, 3.8))
    ax.barh(y + 0.2, c["valid"], 0.4, color=ps.BLUE, label=ps.tex("Validation 2006--2015"), **BAR)
    ax.barh(y - 0.2, c["test"], 0.4, color=ps.ORANGE, label=ps.tex("Test 2016--2026"), **BAR)
    ps.zero_line(ax, "x")
    ax.set_yticks(y, c["root"], fontsize=6.5)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(ps.tex("Gross P\\&L contribution (bp of capital per year)"))
    title = ps.tex(rf"{strategy}: where the gross P\&L comes from, by commodity (equal 1/N budget)")
    return ps.finalize(fig, title, legend_from=ax, ncol=2)

"""Publication figures for the backtest framework (call ``plotstyle.use()`` first).

Every figure states in its title what is measured and how, labels axes with
units, shows 95% Newey-West confidence intervals for estimated means, and
keeps one colour per cost component across all figures: gross P&L blue,
half-spread orange, fees aqua, impact yellow. Cumulative net layers use one
ordinal blue ramp (darker = more costs deducted). Reference values (gross,
sample means) are named in the legend rather than written over the data.
"""

from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from . import plotstyle as ps
from .report import root_table

LAYER_LABELS = {
    "ret_gross": r"Gross",
    "ret_net_spread": r"Net of half-spread",
    "ret_net_fee": r"Net of half-spread and fees",
    "ret_net_all": r"Net of all costs (incl.\ impact)",
}
LAYER_KEYS = {"ret_gross": "gross", "ret_net_spread": "- half-spread",
              "ret_net_fee": "- fees", "ret_net_all": "- impact (all)"}
COST_COLORS = {"gross": ps.BLUE, "half_spread": ps.ORANGE, "fee": ps.AQUA, "impact": ps.YELLOW}
COST_LABELS = {"half_spread": r"Half-spread", "fee": r"Exchange and broker fees", "impact": r"Market impact"}
Z95 = 1.96
MARKER = dict(marker="o", ms=3.5, mec=ps.SURFACE, mew=0.6)
BAR = dict(edgecolor=ps.SURFACE, lw=0.4)
ERR = dict(fmt="none", ecolor=ps.INK, elinewidth=0.7, capsize=2, capthick=0.7)


def _ci(mean: pd.Series, t: pd.Series) -> np.ndarray:
    """95% half-width implied by a mean and its Newey-West t-statistic."""

    se = (mean / t).abs().replace([np.inf, -np.inf], np.nan)
    return (Z95 * se).fillna(0.0).to_numpy()


def _usd(x: float, _pos=None) -> str:
    """Tick formatter: 1e6 -> $1m, 1e9 -> $1bn."""

    s = f"{x / 1e9:g}bn" if x >= 1e9 else f"{x / 1e6:g}m" if x >= 1e6 else f"{x / 1e3:g}k"
    return ps.tex(r"\$" + s)


def _date_axis(ax) -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator(5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlabel("")


def _shade_test(ax, start: str | None) -> None:
    """Light band over the out-of-sample period (named in the legend)."""

    if start is not None:
        lo, hi = mdates.date2num(pd.Timestamp(start)), ax.get_xlim()[1]
        ax.axvspan(lo, hi, color="#f0efec", lw=0, zorder=0,
                   label=ps.tex(rf"Test sample ({pd.Timestamp(start).year}\textendash)"))
        ax.set_xlim(right=hi)


def _log_x(ax, ticks=None, usd: bool = False) -> None:
    """Log x-axis without minor tick clutter."""

    ax.set_xscale("log")
    ax.xaxis.set_minor_locator(mticker.NullLocator())
    if ticks is not None:
        ax.set_xticks(ticks, [str(v) for v in ticks])
    if usd:
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_usd))
        ax.set_xlabel(ps.tex(r"Strategy capital (USD, log scale)"))


def nav_by_cost_layer(res, strategy: str, test_start: str | None = "2016-01-01"):
    """Cumulative return of the strategy after each successive cost layer."""

    d = res.daily.set_index("date")
    fig, ax = plt.subplots(figsize=(ps.FULL_WIDTH, 3.0))
    for color, (col, label) in zip(ps.ORDINAL_BLUE, LAYER_LABELS.items()):
        ann = d[col].mean() * 252 * 100
        ax.plot(d.index, d[col].cumsum() * 100, color=color, lw=1.1,
                label=ps.tex(rf"{label}: ${ann:+.2f}\%$ p.a."))
    _date_axis(ax)
    _shade_test(ax, test_start)
    ps.zero_line(ax)
    ax.set_ylabel(ps.tex(r"Cumulative return (\% of capital)"))
    cap = _usd(res.config.capital)
    title = ps.tex(rf"{strategy}: cumulative return after each cost layer, {cap} capital, "
                   r"sum of daily returns")
    return ps.finalize(fig, title, legend_from=ax, ncol=3)


def turnover(res, strategy: str, window: int = 63):
    """(a) Portfolio turnover through time; (b) turnover of each commodity's book."""

    d = res.daily.set_index("date")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH, 3.2), gridspec_kw={"width_ratios": [1.9, 1]})
    roll = d["turnover"].rolling(window).mean() * 252
    mean = d["turnover"].mean() * 252
    a1.plot(roll.index, roll, color=ps.BLUE, lw=0.8, label=ps.tex(rf"{window}-day rolling mean"))
    a1.axhline(mean, color=ps.INK_2, lw=0.8, label=ps.tex(rf"Full-sample mean ({mean:.1f}$\times$ per year)"))
    _date_axis(a1)
    a1.set_ylim(bottom=0)
    a1.set_ylabel(ps.tex(r"Traded notional / capital, per year"))
    a1.set_title(ps.tex(r"Portfolio turnover, annualised"))
    rt = root_table(res)["turnover_x"].sort_values()
    a2.barh(rt.index, rt.to_numpy(), color=ps.BLUE, height=0.7, **BAR)
    a2.grid(axis="x"), a2.grid(axis="y", visible=False)
    a2.tick_params(axis="y", labelsize=6.5, length=0)
    a2.set_xlabel(ps.tex(r"Book turnover per year ($\times$)"))
    a2.set_title(ps.tex(r"Turnover by commodity"))
    ps.panel_label(a1, "a"), ps.panel_label(a2, "b")
    return ps.finalize(fig, ps.tex(rf"{strategy}: trading intensity"), legend_from=a1, ncol=2)


def commodity_pnl_and_costs(res, strategy: str):
    """Annual gross P&L and each cost component by commodity, net marked."""

    rt = root_table(res).sort_values("net_pct_yr")
    x = np.arange(len(rt))
    fig, ax = plt.subplots(figsize=(ps.FULL_WIDTH, 3.2))
    ax.bar(x, rt["gross_pct_yr"], width=0.72, color=COST_COLORS["gross"], label=ps.tex(r"Gross P\&L"), **BAR)
    bottom = np.minimum(rt["gross_pct_yr"].to_numpy(), 0.0)
    for key in ("half_spread", "fee", "impact"):
        cost = rt[f"{key}_pct_yr"].to_numpy()
        ax.bar(x, -cost, bottom=bottom, width=0.72, color=COST_COLORS[key], label=ps.tex(COST_LABELS[key]), **BAR)
        bottom = bottom - cost
    ax.scatter(x, rt["net_pct_yr"], s=14, color=ps.INK, edgecolor=ps.SURFACE, lw=0.8, zorder=4,
               label=ps.tex(r"Net P\&L"))
    ps.zero_line(ax)
    ax.set_xticks(x, rt.index)
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.6, len(rt) - 0.4)
    ax.set_ylabel(ps.tex(r"Per year (\% of total capital)"))
    cap = _usd(res.config.capital)
    title = ps.tex(rf"{strategy}: gross P\&L and transaction costs by commodity, {cap} capital")
    return ps.finalize(fig, title, legend_from=ax, ncol=5)


def _horizon_ticks(labels: pd.Series) -> list[str]:
    """'t+1->t+6' -> '$[t{+}1,\\,t{+}6]$'."""

    out = []
    for s in labels:
        a, b = s.replace("t+", "").split("->")
        out.append(ps.tex(rf"$[t{{+}}{a},\,t{{+}}{b}]$"))
    return out


def horizon_profile(profile: pd.DataFrame, strategy: str):
    """Signed forward spread return by holding window, with 95% NW intervals.

    (a) total return over the window; (b) the same per day held, which shows
    whether the signal's edge decays or accumulates with the horizon.
    """

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH, 3.0))
    x = np.arange(len(profile))
    ci = _ci(profile["mean_bps"], profile["t_nw"])
    panels = ((a1, profile["mean_bps"], ci, r"Basis points over the window", r"Return over the window"),
              (a2, profile["bps_per_day"], ci / profile["days"].to_numpy(), r"Basis points per day",
               r"Return per day held (window return / length)"))
    for ax, y, err, ylab, title in panels:
        ax.bar(x, y, width=0.62, color=ps.BLUE, **BAR)
        ax.errorbar(x, y, yerr=err, **ERR)
        ps.zero_line(ax)
        ax.set_xticks(x, _horizon_ticks(profile["horizon"]), rotation=35, ha="right")
        ax.tick_params(axis="x", length=0)
        ax.set_ylabel(ps.tex(ylab))
        ax.set_title(ps.tex(title))
    ps.panel_label(a1, "a"), ps.panel_label(a2, "b")
    title = ps.tex(rf"{strategy}: mean of sign$(s_t)\times(r_{{\mathrm{{near}}}}-r_{{\mathrm{{far}}}})$ "
                   r"on the pair fixed at $t$, by window; 95\% Newey\textendash West CI")
    return ps.finalize(fig, title)


def time_series_ic(table: pd.DataFrame, rolling: pd.Series, strategy: str, score: str, window_label: str):
    """(a) Per-commodity time-series rank IC with 95% CI; (b) rolling mean IC."""

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH, 3.4), gridspec_kw={"width_ratios": [1, 1.6]})
    per = table.loc[table["root"] != "ALL"].sort_values("ic")
    y = np.arange(len(per))
    mean_ic = table.loc[table["root"] == "ALL", "ic"].item()
    a1.barh(y, per["ic"], height=0.7, color=ps.BLUE, **BAR)
    a1.errorbar(per["ic"], y, xerr=_ci(per["ic"], per["t_nw"]), fmt="none", ecolor=ps.INK, elinewidth=0.6, capsize=1.5)
    a1.axvline(mean_ic, color=ps.ORANGE, lw=1.0, label=ps.tex(rf"Mean across commodities (${mean_ic:.3f}$)"))
    ps.zero_line(a1, "x")
    a1.set_yticks(y, per["root"])
    a1.tick_params(axis="y", labelsize=6.5, length=0)
    a1.grid(axis="y", visible=False), a1.grid(axis="x")
    a1.set_xlabel(ps.tex(r"Spearman correlation over time"))
    a1.set_title(ps.tex(r"Full-sample IC by commodity, 95\% NW CI"))
    a2.plot(rolling.index, rolling, color=ps.BLUE, lw=0.8, label=ps.tex(r"Rolling 252-day IC, mean across commodities"))
    ps.zero_line(a2)
    _date_axis(a2)
    a2.set_ylabel(ps.tex(r"Spearman correlation"))
    a2.set_title(ps.tex(r"IC through time"))
    ps.panel_label(a1, "a"), ps.panel_label(a2, "b")
    title = ps.tex(rf"{strategy}: time-series IC of {score} at $t$ with the spread return over {window_label}")
    return ps.finalize(fig, title, legend_from=[a1, a2], ncol=2)


def quintile_returns(bins: pd.DataFrame, strategy: str, score: str, window_label: str):
    """Mean forward spread return by each commodity's own-history score quintile."""

    fig, ax = plt.subplots(figsize=(ps.SINGLE_COL + 1.0, 2.8))
    x = np.arange(len(bins))
    ax.bar(x, bins["mean_bps"], width=0.62, color=ps.BLUE, **BAR)
    ax.errorbar(x, bins["mean_bps"], yerr=_ci(bins["mean_bps"], bins["t_nw"]), **ERR)
    ps.zero_line(ax)
    labels = [rf"Q{int(b)}" for b in bins["bin"]]
    labels[0], labels[-1] = "Q1\n(low)", f"Q{len(bins)}\n(high)"
    ax.set_xticks(x, labels)
    ax.tick_params(axis="x", length=0)
    ax.set_xlabel(ps.tex(rf"Own-history quintile of {score} (ex ante)"))
    ax.set_ylabel(ps.tex(rf"Spread return over {window_label} (bp)"))
    title = ps.tex(rf"{strategy}: forward spread return by {score} quintile," + "\n"
                   + r"mean across commodities, 95\% NW CI")
    return ps.finalize(fig, title)


def k_sweep(table: pd.DataFrame, strategy: str):
    """(a) Turnover and (b) annual return per cost layer vs number of sleeves k."""

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH, 3.0))
    k = table["k"]
    a1.plot(k, table["turnover_x"], color=ps.BLUE, **MARKER)
    a1.set_ylim(bottom=0)
    a1.set_ylabel(ps.tex(r"Traded notional / capital, per year"))
    a1.set_title(ps.tex(r"Turnover"))
    for color, (col, label) in zip(ps.ORDINAL_BLUE, LAYER_LABELS.items()):
        ret = table[f"ret_{LAYER_KEYS[col]}"]
        a2.plot(k, ret, color=color, label=ps.tex(label), **MARKER)
        if col in ("ret_gross", "ret_net_all"):
            half = _ci(ret, table[f"t_{LAYER_KEYS[col]}"])
            a2.fill_between(k, ret - half, ret + half, color=color, alpha=0.18, lw=0)
    ps.zero_line(a2)
    a2.set_ylabel(ps.tex(r"Annual return (\% of capital)"))
    a2.set_title(ps.tex(r"Annual return after each cost layer (bands: 95\% NW CI)"))
    for ax in (a1, a2):
        _log_x(ax, ticks=list(k))
        ax.set_xlabel(ps.tex(r"Sleeves $k$ (position = mean of the last $k$ daily targets)"))
    ps.panel_label(a1, "a"), ps.panel_label(a2, "b")
    title = ps.tex(rf"{strategy}: trading $1/k$ of the book per day (overlapping portfolios)")
    return ps.finalize(fig, title, legend_from=a2, ncol=4)


def capacity(table: pd.DataFrame, strategy: str):
    """(a) Cost components and (b) net return as the strategy's capital grows."""

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH, 3.1))
    x = table["capital"]
    keys = ("half_spread", "fee", "impact")
    a1.stackplot(x, *[table[f"{k}_bps_yr"] for k in keys], colors=[COST_COLORS[k] for k in keys],
                 labels=[ps.tex(COST_LABELS[k]) for k in keys], edgecolor=ps.SURFACE, lw=0.6)
    a1.set_ylabel(ps.tex(r"Cost drag (bp of capital per year)"))
    a1.set_title(ps.tex(r"Transaction costs by component"))
    gross = table["gross_bps_yr"].iat[0] / 100
    a2.axhline(gross, color=ps.INK_2, lw=0.9, label=ps.tex(rf"Gross (${gross:+.2f}\%$ p.a., size-invariant)"))
    a2.plot(x, table["ann_ret_pct"], color=ps.ORDINAL_BLUE[-1], label=ps.tex(r"Net of all costs"), **MARKER)
    ps.zero_line(a2)
    a2.set_ylabel(ps.tex(r"Annual return (\% of capital)"))
    a2.set_title(ps.tex(r"Annual return"))
    for ax in (a1, a2):
        _log_x(ax, usd=True)
    ps.panel_label(a1, "a"), ps.panel_label(a2, "b")
    title = ps.tex(rf"{strategy}: transaction costs vs strategy size "
                   r"(spread and fee drag constant, impact drag $\propto\sqrt{\text{capital}}$)")
    return ps.finalize(fig, title, legend_from=[a1, a2], ncol=3)


def capacity_compare(tables: dict, strategy: str):
    """Impact drag and net return vs capital for alternative sizing schemes."""

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH, 3.0))
    for color, (name, t) in zip(ps.CATEGORICAL, tables.items()):
        a1.plot(t["capital"], t["impact_bps_yr"], color=color, label=ps.tex(name), **MARKER)
        a2.plot(t["capital"], t["ann_ret_pct"], color=color, label=ps.tex(name), **MARKER)
    a1.set_ylabel(ps.tex(r"Impact cost (bp of capital per year)"))
    a1.set_title(ps.tex(r"Market impact"))
    a2.set_ylabel(ps.tex(r"Net annual return (\% of capital)"))
    a2.set_title(ps.tex(r"Annual return net of all costs"))
    ps.zero_line(a2)
    for ax in (a1, a2):
        _log_x(ax, usd=True)
    ps.panel_label(a1, "a"), ps.panel_label(a2, "b")
    title = ps.tex(rf"{strategy}: capacity under alternative position sizing")
    return ps.finalize(fig, title, legend_from=[a1, a2], ncol=2)


def horizon_decay(marginal: pd.DataFrame, cumulative: pd.DataFrame, strategy: str):
    """(a) Gross signed return on each day ahead; (b) cumulative over the holding period.

    ``marginal`` is ``horizon_profile`` on windows [t+h, t+h+1]; ``cumulative``
    on windows [t+1, t+1+h]. Both are gross (no costs) and execution free.
    """

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH, 3.0))
    h = np.arange(1, len(marginal) + 1)
    a1.errorbar(h, marginal["mean_bps"], yerr=_ci(marginal["mean_bps"], marginal["t_nw"]),
                color=ps.BLUE, ecolor=ps.BLUE, elinewidth=0.7, capsize=1.5, **MARKER)
    ps.zero_line(a1)
    a1.set_xlabel(ps.tex(r"Day ahead $h$ (return from settle $t{+}h$ to $t{+}h{+}1$)"))
    a1.set_ylabel(ps.tex(r"Basis points on that day"))
    a1.set_title(ps.tex(r"Marginal return by day ahead, 95\% NW CI"))
    hc = np.arange(1, len(cumulative) + 1)
    y, half = cumulative["mean_bps"].to_numpy(), _ci(cumulative["mean_bps"], cumulative["t_nw"])
    a2.fill_between(hc, y - half, y + half, color=ps.BLUE, alpha=0.18, lw=0, label=ps.tex(r"95\% NW CI"))
    a2.plot(hc, y, color=ps.BLUE, label=ps.tex(r"Mean cumulative return"), **MARKER)
    ps.zero_line(a2)
    a2.set_xlabel(ps.tex(r"Holding period $h$ (fill at $t{+}1$, exit at $t{+}1{+}h$)"))
    a2.set_ylabel(ps.tex(r"Basis points over the holding period"))
    a2.set_title(ps.tex(r"Cumulative return by holding period"))
    for ax in (a1, a2):
        ax.set_xticks([1, 5, 10, 15, 20])
    ps.panel_label(a1, "a"), ps.panel_label(a2, "b")
    title = ps.tex(rf"{strategy}: gross signed spread return by horizon, "
                   r"sign$(s_t)\times(r_{\mathrm{near}}-r_{\mathrm{far}})$, mean across commodities")
    return ps.finalize(fig, title, legend_from=a2, ncol=2)


def bootstrap_ic_distribution(summary: pd.DataFrame, draws: dict, strategy: str, score: str,
                              window_label: str, block: int, alpha: float = 0.05):
    """Per-commodity block-bootstrap distribution of the time-series IC.

    One vertical histogram per commodity (sorted by IC), its point estimate,
    95% percentile interval and two-sided bootstrap p-value. Commodities with
    p < alpha are drawn in blue, the rest in grey.
    """

    s = summary.sort_values("ic").reset_index(drop=True)
    lo = min(np.quantile(d, 0.001) for d in draws.values())
    hi = max(np.quantile(d, 0.999) for d in draws.values())
    bins = np.linspace(lo, hi, 41)
    fig, ax = plt.subplots(figsize=(ps.FULL_WIDTH, 3.6))
    for i, r in s.iterrows():
        dens, edges = np.histogram(draws[r["root"]], bins=bins, density=True)
        color = ps.BLUE if r["p_value"] < alpha else "#a9a8a4"
        ax.barh(edges[:-1], dens / dens.max() * 0.42, height=np.diff(edges), left=i,
                align="edge", color=color, lw=0)
        ax.plot([i - 0.08, i - 0.08], [r["ci_lo"], r["ci_hi"]], color=ps.INK, lw=0.8)
        ax.plot(i - 0.08, r["ic"], "o", color=ps.INK, ms=2.6)
        p = r["p_value"]
        ptxt = r"$p<0.001$" if p < 0.001 else rf"$p={p:.3f}$"
        ax.text(i + 0.1, hi + 0.03 * (hi - lo), ps.tex(ptxt), rotation=90, ha="center", va="bottom",
                fontsize=6.3, color=ps.INK_2)
    ps.zero_line(ax)
    ax.set_xticks(range(len(s)), s["root"])
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.6, len(s) - 0.3)
    ax.set_ylim(lo, hi + 0.42 * (hi - lo))
    ax.set_ylabel(ps.tex(r"Time-series Spearman IC"))
    handles = [Patch(color=ps.BLUE, label=ps.tex(rf"Bootstrap distribution, $p<{alpha:g}$")),
               Patch(color="#a9a8a4", label=ps.tex(rf"Bootstrap distribution, $p\geq{alpha:g}$")),
               Line2D([], [], color=ps.INK, marker="o", ms=2.6, lw=0.8, label=ps.tex(r"Estimate and 95\% interval"))]
    ax.legend(handles=handles)
    title = ps.tex(rf"{strategy}: is each commodity's time-series IC different from zero?" + "\n"
                   + rf"IC of {score} at $t$ with the spread return over {window_label}; "
                   + rf"{block}-day moving-block bootstrap, two-sided $p$-values")
    return ps.finalize(fig, title, legend_from=ax, ncol=3)

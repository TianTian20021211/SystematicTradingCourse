"""Performance tables for ``simulate.SimResult`` (figures live in ``src/figures.py``)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import costs as cost_model
from . import horizon, simulate, sizing

LAYERS = {
    "ret_gross": "gross",
    "ret_net_spread": "- half-spread",
    "ret_net_fee": "- fees",
    "ret_net_all": "- impact (all)",
}


def _slice(daily: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    d = daily.set_index("date")
    return d.loc[start:end]


def performance_table(res: simulate.SimResult, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Annualised statistics per cost layer (non-compounding NAV).

    Returns:
        One row per layer: ``ann_ret_%, ann_vol_%, sharpe, t_nw, max_dd_%,
        turnover_x`` (annual traded notional / capital) and ``cost_bps_yr``
        (drag relative to gross).
    """

    d = _slice(res.daily, start, end)
    rows = []
    for col, label in LAYERS.items():
        r = d[col]
        nav = r.cumsum()
        rows.append(dict(layer=label, ann_ret_pct=r.mean() * 252 * 100, ann_vol_pct=r.std() * np.sqrt(252) * 100,
                         sharpe=r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan,
                         t_nw=horizon.newey_west_t(r, 5), max_dd_pct=(nav - nav.cummax()).min() * 100,
                         turnover_x=d["turnover"].mean() * 252,
                         cost_bps_yr=(d["ret_gross"].mean() - r.mean()) * 252 * 1e4))
    return pd.DataFrame(rows).round(3)


def root_table(res: simulate.SimResult) -> pd.DataFrame:
    """Per-root contribution, costs and turnover (annualised, % of capital).

    ``turnover_x`` = annual traded notional / average gross notional held, the
    number of times the root's book is traded per year; ``impact_bps_of_book``
    is the annual impact cost relative to that root's own average book.
    """

    b = res.by_root
    years = b["date"].nunique() / 252
    cap = res.config.capital
    g = b.groupby("root")
    out = pd.DataFrame({
        "gross_pct_yr": g["pnl_gross"].sum() / cap / years * 100,
        "half_spread_pct_yr": g["cost_half_spread"].sum() / cap / years * 100,
        "fee_pct_yr": g["cost_fee"].sum() / cap / years * 100,
        "impact_pct_yr": g["cost_impact"].sum() / cap / years * 100,
        "turnover_x": g["traded_notional"].sum() / years / g["gross_notional"].mean().replace(0, np.nan),
        "median_participation": res.trades.groupby("root")["participation"].median(),
    })
    out["impact_bps_of_book"] = g["cost_impact"].sum() / years / g["gross_notional"].mean().replace(0, np.nan) * 1e4
    out["net_pct_yr"] = out["gross_pct_yr"] - out[["half_spread_pct_yr", "fee_pct_yr", "impact_pct_yr"]].sum(axis=1)
    return out.sort_values("net_pct_yr").round(4)


def k_sweep(signal, pairs, marks, ks, config: simulate.SimConfig | None = None, **sizing_kw) -> pd.DataFrame:
    """Rerun the strategy with k overlapping sleeves (trade 1/k per day).

    Returns:
        One row per k: annualised return, Sharpe and Newey-West t-stat per
        cost layer, and turnover.
    """

    rows = []
    for k in ks:
        res = simulate.simulate(sizing.legs_from_signal(signal, pairs, k=k, **sizing_kw), marks, config)
        perf = performance_table(res).set_index("layer")
        row = {"k": k, "turnover_x": perf["turnover_x"].iat[0]}
        for layer in perf.index:
            row[f"ret_{layer}"] = perf.loc[layer, "ann_ret_pct"]
            row[f"sr_{layer}"] = perf.loc[layer, "sharpe"]
            row[f"t_{layer}"] = perf.loc[layer, "t_nw"]
        rows.append(row)
    return pd.DataFrame(rows)


def capacity_curve(res: simulate.SimResult, capitals) -> pd.DataFrame:
    """Gross and cost layers as a function of capital, without re-simulating.

    Holdings and trade sizes scale linearly with capital (fractional
    contracts), so each trade is rescaled and re-costed: half-spread and fees
    stay constant in % of capital, impact grows roughly with sqrt(capital).
    """

    d = res.daily.set_index("date")
    years = len(d) / 252
    gross = d["ret_gross"].mean() * 252 * 1e4
    rows = []
    for cap in capitals:
        scale = cap / res.config.capital
        t = res.trades.assign(dn=res.trades["dn"] * scale)
        t = cost_model.trade_costs(t, res.config.cost)
        daily_cost = t.groupby("date")[["cost_half_spread", "cost_fee", "cost_impact"]].sum().sum(axis=1)
        net = d["ret_gross"] - daily_cost.reindex(d.index).fillna(0.0) / cap
        layer = {c: t[c].sum() / cap / years * 1e4 for c in ("cost_half_spread", "cost_fee", "cost_impact")}
        rows.append(dict(capital=cap, gross_bps_yr=gross, half_spread_bps_yr=layer["cost_half_spread"],
                         fee_bps_yr=layer["cost_fee"], impact_bps_yr=layer["cost_impact"],
                         ann_ret_pct=net.mean() * 252 * 100, sharpe=net.mean() / net.std() * np.sqrt(252)))
    return pd.DataFrame(rows)

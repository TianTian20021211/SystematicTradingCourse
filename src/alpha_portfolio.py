"""Monetising a combined spread-return forecast with the v2 simulator (D-030).

The forecast ``pred`` is in vol-scaled units (``y_fwd_a_b``); the expected
spread return over the horizon is ``pred x sigma x sqrt(b - a)``. Rules:

- ``sign``: time-series, target = sign(pred), k overlapping sleeves.
- ``linear``: time-series, target = clip(pred / (2 s), -1, 1), s = train std.
- ``band``: time-series, trade sign(pred) only when the expected return beats
  the estimated round-trip cost; otherwise emit no row (the simulator holds).
- ``xs``: cross-sectional experiment, long the top-n / short the bottom-n
  roots by pred each day (settle times differ across exchanges; labelled as a
  comparison, not a main result).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import costs, simulate, sizing, specs

RULES = ("sign", "linear", "band", "xs")


def round_trip_cost(pairs: pd.DataFrame, p: costs.CostParams = costs.CostParams()) -> pd.Series:
    """Estimated round-trip cost of one spread unit, as a return on one leg's notional.

    One spread order crosses one half-spread (thinner leg's lagged ADV) and pays
    the fee on both legs; the round trip doubles it. Impact is ignored (the
    band is meant for small books).
    """

    sp = specs.load_contract_specs()
    tick_val = pairs["root"].map(sp["tick_value_usd"])
    point_val = pairs["root"].map(sp["point_value_usd"])
    adv = pairs[["adv_near", "adv_far"]].min(axis=1)
    one_way = costs.half_spread_ticks(adv, p) * tick_val + 2 * p.fee_per_contract
    return 2 * one_way / (pairs["settle_near"].abs() * point_val)


def forecast_frame(panel: pd.DataFrame, pred: pd.Series, target: str) -> pd.DataFrame:
    """``date, root, pred, exp_ret`` for usable rows with a forecast."""

    a, b = (int(x) for x in target.split("_")[1:])
    f = panel[["date", "root", "sigma", "usable"]].assign(pred=np.asarray(pred))
    f["exp_ret"] = f["pred"] * f["sigma"] * np.sqrt(b - a)
    return f.loc[f["usable"] & f["pred"].notna()].drop(columns="usable")


def make_signal(fc: pd.DataFrame, rule: str, scale: float = 1.0, cost: pd.Series | None = None,
                n_xs: int = 5) -> pd.DataFrame:
    """Target table ``date, root, target`` for one monetisation rule."""

    f = fc[["date", "root", "pred", "exp_ret"]].copy()
    if rule == "sign":
        f["target"] = np.sign(f["pred"])
    elif rule == "linear":
        f["target"] = (f["pred"] / (2 * scale)).clip(-1, 1)
    elif rule == "band":
        # Hysteresis state: update to sign(pred) only when the expected return
        # beats the round-trip cost, otherwise keep the previous state. Every
        # usable row is emitted so the 1/N budget counts all held roots.
        passed = f["exp_ret"].abs() > cost.reindex(f.index)
        f = f.sort_values(["root", "date"])
        f["target"] = np.sign(f["pred"]).where(passed.reindex(f.index))
        f["target"] = f.groupby("root")["target"].ffill().fillna(0.0)
    elif rule == "xs":
        r = f.groupby("date")["pred"].rank(method="first")
        n = f.groupby("date")["pred"].transform("size")
        f["target"] = np.where(r > n - n_xs, 1.0, np.where(r <= n_xs, -1.0, 0.0))
        f.loc[n < 2 * n_xs, "target"] = 0.0
    else:
        raise ValueError(f"unknown rule {rule!r}")
    return f[["date", "root", "target"]].reset_index(drop=True)


def run_rule(fc: pd.DataFrame, rule: str, pairs: pd.DataFrame, marks: pd.DataFrame, k: int,
             capital: float = 1e6, scale: float = 1.0, round_lots: bool = False) -> simulate.SimResult:
    """Build legs for one rule and run the v2 simulator (equal 1/N budget)."""

    cost = None
    if rule == "band":
        c = round_trip_cost(pairs)
        c.index = pd.MultiIndex.from_frame(pairs[["date", "root"]])
        cost = pd.Series(c.reindex(pd.MultiIndex.from_frame(fc[["date", "root"]])).to_numpy(), index=fc.index)
    sig = make_signal(fc, rule, scale=scale, cost=cost)
    legs = sizing.legs_from_signal(sig, pairs, scheme="equal", n_mode="active", k=1 if rule == "band" else k)
    cfg = simulate.SimConfig(capital=capital, round_lots=round_lots)
    return simulate.simulate(legs, marks, cfg)


def root_characteristics(panel: pd.DataFrame, pairs: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Median liquidity and cost characteristics per root over ``[start, end]``.

    Returns:
        ``root, log10_dollar_adv, rel_tick_bp`` (tick / near price),
        ``round_trip_bp`` (``round_trip_cost``) and ``vol_bp`` (daily pair vol).
    """

    sp = specs.load_contract_specs()
    p = pairs.loc[pairs["date"].between(start, end)].copy()
    p["round_trip_bp"] = round_trip_cost(p) * 1e4
    p["rel_tick_bp"] = p["root"].map(sp["tick_size"]) / p["settle_near"].abs() * 1e4
    p["log10_dollar_adv"] = np.log10(p["dollar_adv"].where(p["dollar_adv"] > 0))
    vol = panel.loc[panel["date"].between(start, end)].groupby("root")["sigma"].median() * 1e4
    out = p.groupby("root")[["log10_dollar_adv", "rel_tick_bp", "round_trip_bp"]].median()
    return out.assign(vol_bp=vol).reset_index()


def root_contribution(res: simulate.SimResult, periods: dict[str, tuple[str, str]]) -> pd.DataFrame:
    """Gross P&L per root in bp of capital per year for each named period."""

    b = res.by_root.assign(date=lambda d: pd.to_datetime(d["date"]))
    out = {}
    for name, (lo, hi) in periods.items():
        x = b.loc[b["date"].between(lo, hi)]
        years = x["date"].nunique() / 252
        out[name] = x.groupby("root")["pnl_gross"].sum() / res.config.capital / years * 1e4
    return pd.DataFrame(out).fillna(0.0).reset_index()

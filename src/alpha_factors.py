"""Continuous alpha factors for the main calendar spread (D-030).

Each trading idea (A carry, B adjacent carry, C mean reversion, D curve
momentum, E Nelson-Siegel) is abstracted into one or more continuous scores on
the v2 main pair (``v2_signals.load_v2_inputs``). Every factor at date t uses
only settles up to and including t, so a forecast made at the t settle and
filled at t+1 is causal. Targets are the fixed-pair forward spread returns of
``horizon.forward_returns``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import continuous, horizon, nelson_siegel as ns, signals, v2_signals

FACTORS = {
    "a_carry": "A", "a_carry_dev": "A",
    "b_curve_carry": "B", "b_rel_carry": "B",
    "c_z20": "C", "c_z60": "C", "c_rev5": "C",
    "d_mom21": "D", "d_mom63": "D", "d_mom252": "D",
    "e_dslope": "E", "e_dcurv": "E",
}
HORIZONS = [(0, 1), (1, 2), (1, 3), (1, 6), (1, 11), (1, 22)]
TARGETS = [f"fwd_{a}_{b}" for a, b in HORIZONS]
KEYS = ["date", "root"]


def pair_daily_returns(pairs: pd.DataFrame, marks: pd.DataFrame) -> pd.Series:
    """Equal-notional return of the date-t main pair over (previous settle, t].

    Both legs of a main pair exist on the previous settle (M1-M4 slots), so the
    series is roll-safe without back-adjustment.
    """

    ret = marks.set_index(["date", "root", "contract_code"])["ret"]
    out = []
    for leg in ("near", "far"):
        idx = pd.MultiIndex.from_arrays([pairs["date"], pairs["root"], pairs[f"contract_{leg}"]])
        out.append(ret.reindex(idx).to_numpy())
    return pd.Series(out[0] - out[1], index=pairs.index, name="r")


def _rolling(frame: pd.DataFrame, col: str, window: int, how: str, min_frac: float = 0.8) -> pd.Series:
    """Per-root trailing rolling statistic of ``col`` (rows sorted by root, date)."""

    g = frame.groupby("root", sort=False)[col]
    minp = max(2, int(np.ceil(min_frac * window)))
    return g.transform(lambda s: getattr(s.rolling(window, min_periods=minp), how)())


def carry_factors(pairs: pd.DataFrame) -> pd.DataFrame:
    """Idea A: annualised main-pair carry and its deviation from a 252-day mean."""

    sig = signals.carry_signal(pairs, signals.CarryParams(signal="annualized"))
    out = pairs[KEYS].assign(a_carry=sig["carry_ann"].to_numpy())
    out = out.sort_values(KEYS[::-1])
    out["a_carry_dev"] = out["a_carry"] - _rolling(out, "a_carry", 252, "mean", 0.5)
    return out.sort_index()


def adjacent_carry_factors(pairs: pd.DataFrame, adjacent: pd.DataFrame) -> pd.DataFrame:
    """Idea B: curve-shape carry factors from the eligible adjacent spreads.

    Args:
        pairs: Main-pair panel (provides ``a_carry`` via ``carry_factors``).
        adjacent: Eligible adjacent carries (``v2_signals.load_b_adjacent``),
            one row per ``date, root, rank_near`` with ``carry_ann``.

    Returns:
        ``date, root, b_curve_carry, b_rel_carry``: front-minus-back adjacent
        carry (needs >= 2 adjacent spreads) and main-pair carry minus the mean
        adjacent carry.
    """

    adj = adjacent.dropna(subset=["carry_ann"]).sort_values(KEYS + ["rank_near"])
    g = adj.groupby(KEYS)["carry_ann"]
    shape = pd.DataFrame({"front": g.first(), "back": g.last(), "mean": g.mean(), "n": g.size()})
    shape["b_curve_carry"] = (shape["front"] - shape["back"]).where(shape["n"] >= 2)
    main = carry_factors(pairs).set_index(KEYS)["a_carry"]
    shape = shape.reindex(main.index)
    shape["b_rel_carry"] = main - shape["mean"]
    return shape[["b_curve_carry", "b_rel_carry"]].reset_index()


def reversion_momentum_factors(
    pairs: pd.DataFrame, marks: pd.DataFrame, contract_panel: pd.DataFrame
) -> pd.DataFrame:
    """Ideas C and D: spread z-scores, short-term reversal and spread momentum.

    ``c_z*`` is minus the z-score of the continuous spread index (D-010) over
    20/60 days; ``c_rev5`` is minus the 5-day pair return; ``d_mom*`` is the
    21/63/252-day cumulative pair return (basis momentum on the traded pair).
    Windows need 80% valid observations.
    """

    f = pairs[KEYS].copy()
    f["r"] = pair_daily_returns(pairs, marks)
    leg = continuous.build_continuous_leg_prices(pairs, contract_panel)
    idx = continuous.build_spread_index(leg)[KEYS + ["spread_index"]]
    f = f.merge(idx, on=KEYS, how="left").sort_values(KEYS[::-1])
    for w in (20, 60):
        mu, sd = _rolling(f, "spread_index", w, "mean"), _rolling(f, "spread_index", w, "std")
        f[f"c_z{w}"] = -((f["spread_index"] - mu) / sd.where(sd > 0))
    f["c_rev5"] = -_rolling(f, "r", 5, "sum")
    for w in (21, 63, 252):
        f[f"d_mom{w}"] = _rolling(f, "r", w, "sum")
    return f.drop(columns="spread_index").sort_values(KEYS).reset_index(drop=True)


def ns_factors(contract_panel: pd.DataFrame, rule: str = "rolling_ssr") -> pd.DataFrame:
    """Idea E: one-day Nelson-Siegel slope and curvature changes.

    Uses the D-022 selected causal lambda rule. Changes are divided by the
    mean fitted price of the four contracts so the factor is scale-free.
    """

    curve = ns.eligible_curve(contract_panel)
    wide = ns.wide_curve(curve)
    fits = ns.fit_ns(wide, ns.lambda_series(wide, rule))
    sig = ns.ns_signals(fits, wide, curve)
    level = sig[[f"F{k}" for k in range(4)]].mean(axis=1)
    level = level.where(level > 0)
    return sig[KEYS].assign(e_dslope=sig["dbS"] / level, e_dcurv=sig["dbC"] / level)


def scale_factors(panel: pd.DataFrame, cols: list[str], min_obs: int = 252, clip: float = 4.0) -> pd.DataFrame:
    """Per-root causal scaling: divide by the expanding RMS, then winsorise.

    No demeaning, so the sign of level factors (e.g. contango vs
    backwardation carry) is preserved. Rows before ``min_obs`` valid
    observations are NaN.
    """

    f = panel.sort_values(KEYS[::-1])
    g = f.groupby("root", sort=False)
    out = f[KEYS].copy()
    for c in cols:
        sq = g[c].transform(lambda s: (s ** 2).expanding(min_periods=min_obs).mean())
        out[f"z_{c}"] = (f[c] / np.sqrt(sq.where(sq > 0))).clip(-clip, clip)
    return out.sort_index()


def scale_targets(panel: pd.DataFrame, vol_window: int = 60, clip: float = 10.0) -> pd.DataFrame:
    """Divide each forward return by the lagged daily pair vol x sqrt(length).

    The vol uses pair returns up to the previous settle, so it is known at t.
    """

    f = panel.sort_values(KEYS[::-1])
    sigma = _rolling(f, "r", vol_window, "std").groupby(f["root"]).shift()
    out = f[KEYS].assign(sigma=sigma)
    for col in TARGETS:
        a, b = (int(x) for x in col.split("_")[1:])
        out[f"y_{col}"] = (f[col] / (sigma * np.sqrt(b - a))).clip(-clip, clip)
    return out.sort_index()


def build_factor_panel(inputs: v2_signals.V2Inputs, rank: pd.DataFrame) -> pd.DataFrame:
    """Assemble factors, raw and scaled targets for every main-pair date.

    Returns:
        One row per ``date, root`` with ``sector, liquid, dollar_adv,
        settle_near, settle_far, r``, the raw factors in ``FACTORS``, their
        scaled ``z_*`` versions, raw targets ``fwd_*``, scaled targets
        ``y_fwd_*`` and the lagged pair vol ``sigma``. ``usable`` marks
        liquid rows with positive leg prices (the rows the v2 sizing trades).
    """

    pairs = inputs.pairs.reset_index(drop=True)
    _, adjacent = v2_signals.load_b_adjacent(inputs, rank, d=5, min_adv=None)
    base = pairs[KEYS + ["sector", "liquid", "dollar_adv", "settle_near", "settle_far"]]
    parts = [
        carry_factors(pairs),
        adjacent_carry_factors(pairs, adjacent),
        reversion_momentum_factors(pairs, inputs.marks, inputs.bt["contract"]),
        ns_factors(inputs.bt["contract"]),
        horizon.forward_returns(pairs, inputs.marks, HORIZONS),
    ]
    panel = base.copy()
    for part in parts:
        panel = panel.merge(part, on=KEYS, how="left", validate="one_to_one")
    panel["usable"] = panel["liquid"].fillna(False).astype(bool) & panel["settle_near"].gt(0) & panel["settle_far"].gt(0)
    panel = panel.merge(scale_factors(panel, list(FACTORS)), on=KEYS)
    panel = panel.merge(scale_targets(panel), on=KEYS)
    return panel.sort_values(KEYS).reset_index(drop=True)

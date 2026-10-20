"""Signal diagnostics across horizons, independent of execution and costs.

For a signal at the t settle, the forward spread return over (a, b) is
``r_near(t+a -> t+b) - r_far(t+a -> t+b)`` on the pair chosen at t, held fixed
(no roll inside the window; NaN if a leg expires first). ``(1, 2)`` is the
first day of P&L of a position filled at the t+1 settle.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_HORIZONS = [(1, 2), (1, 3), (1, 4), (1, 6), (1, 11), (1, 21), (11, 21)]


def marginal_horizons(max_lead: int = 20) -> list[tuple[int, int]]:
    """One-day windows [t+h, t+h+1] for h = 1..max_lead (return on day h ahead)."""

    return [(h, h + 1) for h in range(1, max_lead + 1)]


def cumulative_horizons(max_hold: int = 20) -> list[tuple[int, int]]:
    """Holding windows [t+1, t+1+h] for h = 1..max_hold (fill at t+1, hold h days)."""

    return [(1, 1 + h) for h in range(1, max_hold + 1)]


def _cum_marks(marks: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """Cumulative settle change per contract, indexed by calendar position."""

    m = marks[["date", "root", "contract_code", "dprice", "mark"]].copy()
    m["key"] = m["root"] + "|" + m["contract_code"]
    m["pos"] = calendar.searchsorted(m["date"])
    m = m.sort_values(["key", "pos"])
    m["cum"] = m.groupby("key")["dprice"].cumsum()
    m["last_pos"] = m.groupby("key")["pos"].transform("max")
    return m[["key", "pos", "cum", "mark", "last_pos"]].sort_values("pos")


def _lookup(cm: pd.DataFrame, key: pd.Series, pos: np.ndarray) -> pd.DataFrame:
    """As-of (cum, mark) of contract ``key`` at calendar position ``pos``."""

    q = pd.DataFrame({"key": key.to_numpy(), "pos": pos, "row": np.arange(len(key))})
    q = q.sort_values("pos")
    out = pd.merge_asof(q, cm, on="pos", by="key", direction="backward")
    out.loc[out["pos"] > out["last_pos"], ["cum", "mark"]] = np.nan
    return out.sort_values("row")[["cum", "mark"]].reset_index(drop=True)


def forward_returns(
    pairs: pd.DataFrame,
    marks: pd.DataFrame,
    horizons: list[tuple[int, int]] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    """Forward fixed-pair spread returns for every pair-date.

    Returns:
        ``date, root`` plus one column ``fwd_a_b`` per horizon (decimal
        return of a long-near / short-far position, equal notional legs).
    """

    calendar = pd.DatetimeIndex(sorted(marks["date"].unique()))
    cm = _cum_marks(marks, calendar)
    p0 = calendar.searchsorted(pd.DatetimeIndex(pairs["date"]))
    out = pairs[["date", "root"]].reset_index(drop=True).copy()
    keys = {leg: pairs["root"] + "|" + pairs[f"contract_{leg}"] for leg in ("near", "far")}
    for a, b in horizons:
        leg_ret = {}
        for leg, key in keys.items():
            start, end = _lookup(cm, key, p0 + a), _lookup(cm, key, p0 + b)
            leg_ret[leg] = ((end["cum"] - start["cum"]) / start["mark"]).where(start["mark"] > 0)
        out[f"fwd_{a}_{b}"] = (leg_ret["near"] - leg_ret["far"]).to_numpy()
    return out


def newey_west_t(x: pd.Series, lag: int) -> float:
    """Newey-West t-statistic of the mean of ``x`` with Bartlett weights."""

    x = x.dropna().to_numpy(float)
    n = len(x)
    if n < 3:
        return np.nan
    e = x - x.mean()
    var = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        var += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(var / n) if var > 0 else np.nan


def _merge_score(fwd: pd.DataFrame, signal: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """Join a signal column onto forward returns by ``date, root``."""

    return fwd.merge(signal[["date", "root", score_col]], on=["date", "root"], how="inner")


def horizon_profile(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    score_col: str = "target",
) -> pd.DataFrame:
    """Mean signed forward return per horizon (the signal's decay profile).

    Each date's equal-weight average of ``score x fwd`` across roots forms a
    time series; its mean is tested with Newey-West using lag = b - a to
    absorb the overlap of multi-day windows.

    Returns:
        One row per horizon: ``mean_bps`` (per window), ``bps_per_day``,
        ``t_nw``, ``hit_rate`` and number of dates.
    """

    f = _merge_score(fwd, signal, score_col)
    rows = []
    for col in [c for c in fwd.columns if c.startswith("fwd_")]:
        a, b = (int(x) for x in col.split("_")[1:])
        x = (f[score_col] * f[col]).where(f[score_col].ne(0))
        daily = x.groupby(f["date"]).mean().dropna()
        hit = (np.sign(f[score_col]) == np.sign(f[col])).where(x.notna()).mean()
        rows.append(dict(horizon=f"t+{a}->t+{b}", days=b - a, mean_bps=daily.mean() * 1e4,
                         bps_per_day=daily.mean() * 1e4 / (b - a), t_nw=newey_west_t(daily, b - a),
                         hit_rate=hit, n_dates=len(daily)))
    return pd.DataFrame(rows)


def ts_ic(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    col: str = "fwd_1_6",
    score_col: str = "score",
    min_obs: int = 252,
) -> pd.DataFrame:
    """Time-series rank IC per root: corr(score_t, fwd_t) over the root's own history.

    All strategies here are time series; commodities settle at different times,
    so no cross-sectional comparison is made. The IC is the mean of the product
    of standardised ranks, so its Newey-West t-stat (lag = window length)
    accounts for overlapping forward windows.

    Returns:
        One row per root (``ic, t_nw, n``) plus an ``ALL`` row averaging the
        root ICs with equal weight.
    """

    f = _merge_score(fwd, signal, score_col).dropna(subset=[score_col, col])
    lag = int(col.split("_")[2]) - int(col.split("_")[1])
    rows = []
    for root, g in f.groupby("root"):
        if len(g) < min_obs:
            continue
        rs, rf = g[score_col].rank(), g[col].rank()
        x = ((rs - rs.mean()) / rs.std(ddof=0)) * ((rf - rf.mean()) / rf.std(ddof=0))
        rows.append(dict(root=root, ic=x.mean(), t_nw=newey_west_t(x, lag), n=len(g)))
    out = pd.DataFrame(rows)
    mean_row = dict(root="ALL", ic=out["ic"].mean(), t_nw=np.nan, n=int(out["n"].sum()))
    return pd.concat([out, pd.DataFrame([mean_row])], ignore_index=True)


def rolling_ts_ic(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    col: str = "fwd_1_6",
    score_col: str = "score",
    window: int = 252,
) -> pd.Series:
    """Rolling time-series correlation per root, averaged across roots by date.

    The window uses past pairs (score_s, fwd_s) whose forward return is fully
    observed only after t + b, so the series is descriptive (for stability over
    time), not a tradable quantity.
    """

    f = _merge_score(fwd, signal, score_col).dropna(subset=[score_col, col])
    f = f.sort_values(["root", "date"])
    corr = f.groupby("root", group_keys=False).apply(
        lambda g: g[score_col].rolling(window, min_periods=window).corr(g[col])
    )
    # Date x root, carried over market holidays (e.g. ICE open on US holidays)
    # so a date is never averaged over one or two commodities.
    wide = corr.groupby([f["date"], f["root"]]).last().unstack().sort_index().ffill(limit=5)
    enough = wide.notna().sum(axis=1) >= wide.notna().sum(axis=1).max() / 2
    return wide.mean(axis=1).where(enough).dropna().rename("rolling_ic")


def bin_returns(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    col: str = "fwd_1_6",
    score_col: str = "score",
    n_bins: int = 5,
    min_history: int = 252,
) -> pd.DataFrame:
    """Average forward return by each root's own ex-ante score quantile.

    A score is binned by its expanding percentile within the root's history up
    to t (no look-ahead); the first ``min_history`` observations per root are
    skipped. Bin returns are averaged across roots by date, then over time.

    Returns:
        ``bin, mean_bps, t_nw, n`` with bin 1 = lowest score.
    """

    f = _merge_score(fwd, signal, score_col).dropna(subset=[score_col, col])
    f = f.sort_values(["root", "date"]).copy()
    g = f.groupby("root")[score_col]
    f["pct"] = g.transform(lambda s: s.expanding().rank(pct=True))
    f = f.loc[g.cumcount() >= min_history].copy()
    f["bin"] = np.ceil(f["pct"] * n_bins).clip(1, n_bins).astype(int)
    lag = int(col.split("_")[2]) - int(col.split("_")[1])
    rows = []
    for k, b in f.groupby("bin"):
        daily = b.groupby("date")[col].mean()
        rows.append(dict(bin=k, mean_bps=daily.mean() * 1e4, t_nw=newey_west_t(daily, lag), n=len(b)))
    return pd.DataFrame(rows)


def _block_indices(n: int, block: int, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """Moving-block bootstrap row indices, shape (n_boot, n)."""

    n_blocks = -(-n // block)
    starts = rng.integers(0, n - block + 1, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)
    return idx[:, :n].astype(np.int32)


def _pearson_rows(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Row-wise Pearson correlation of two (B, n) arrays."""

    xc = x - x.mean(axis=1, keepdims=True)
    yc = y - y.mean(axis=1, keepdims=True)
    return (xc * yc).sum(axis=1) / np.sqrt((xc**2).sum(axis=1) * (yc**2).sum(axis=1))


def block_bootstrap_ic(
    fwd: pd.DataFrame,
    signal: pd.DataFrame,
    col: str = "fwd_1_6",
    score_col: str = "score",
    block: int = 21,
    n_boot: int = 2000,
    min_obs: int = 252,
    seed: int = 0,
) -> tuple[pd.DataFrame, dict]:
    """Per-commodity moving-block bootstrap of the time-series rank IC.

    Each root's (score_t, fwd_t) pairs are resampled in blocks of ``block``
    consecutive observations, which preserves the serial dependence created
    by overlapping forward windows and persistent scores. Ranks are taken on
    the full sample and the IC of a resample is the Pearson correlation of
    the resampled ranks (the standard Spearman bootstrap shortcut).

    Returns:
        ``summary`` (one row per root: ``ic, ci_lo, ci_hi, p_value, n``,
        two-sided p = 2 min(P(IC* <= 0), P(IC* >= 0))) and ``draws``
        (root -> array of bootstrap ICs).
    """

    f = _merge_score(fwd, signal, score_col).dropna(subset=[score_col, col]).sort_values(["root", "date"])
    rng = np.random.default_rng(seed)
    rows, draws = [], {}
    for root, g in f.groupby("root"):
        if len(g) < max(min_obs, 2 * block):
            continue
        rs, rf = g[score_col].rank().to_numpy(), g[col].rank().to_numpy()
        idx = _block_indices(len(g), block, n_boot, rng)
        boot = _pearson_rows(rs[idx], rf[idx])
        ic = np.corrcoef(rs, rf)[0, 1]
        p = min(1.0, 2 * min((boot <= 0).mean(), (boot >= 0).mean()))
        lo, hi = np.quantile(boot, [0.025, 0.975])
        rows.append(dict(root=root, ic=ic, ci_lo=lo, ci_hi=hi, p_value=p, n=len(g)))
        draws[root] = boot
    return pd.DataFrame(rows), draws


def block_bootstrap_mean(
    values: pd.DataFrame,
    col: str,
    block: int = 21,
    n_boot: int = 2000,
    min_obs: int = 252,
    seed: int = 0,
    null: float = 0.0,
    stat: str = "mean",
) -> tuple[pd.DataFrame, dict]:
    """Per-root moving-block bootstrap of the time-series mean (or median) of ``col``.

    Used for daily fit statistics (R², or a paired daily difference such as
    the R² gain from adding a component): each root's dates are resampled in
    blocks of ``block`` consecutive observations.

    Returns:
        ``summary`` (``root, mean, ci_lo, ci_hi, p_value, n``; ``mean`` holds
        the chosen statistic; two-sided p for statistic = ``null``) and
        ``draws`` (root -> bootstrap statistics). Use ``stat="median"`` for
        heavy-tailed series such as leave-one-out R².
    """

    f = values[["date", "root", col]].dropna().sort_values(["root", "date"])
    rng = np.random.default_rng(seed)
    rows, draws = [], {}
    for root, g in f.groupby("root"):
        x = g[col].to_numpy(float)
        if len(x) < max(min_obs, 2 * block):
            continue
        func = np.median if stat == "median" else np.mean
        boot = func(x[_block_indices(len(x), block, n_boot, rng)], axis=1)
        p = min(1.0, 2 * min((boot <= null).mean(), (boot >= null).mean()))
        lo, hi = np.quantile(boot, [0.025, 0.975])
        rows.append(dict(root=root, mean=func(x), ci_lo=lo, ci_hi=hi, p_value=p, n=len(x)))
        draws[root] = boot
    return pd.DataFrame(rows), draws

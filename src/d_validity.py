"""Signal-validity diagnostics for idea D (curve momentum / basis momentum).

The module is deliberately self-contained and uses gross, signal-level
returns. It does not call the v2 simulator and does not touch costs. The
main object is a monthly panel with one row per (root, signal date):

- D raw score and sign target;
- month-end A carry score and C mean-reversion z-score;
- rank-index forward returns at 1/3/6/12 months, t+1 timing;
- same-close forward returns for the timing diagnostic.

All statistics are per root, following the project's time-series rule
(D-016). Root ICs are aggregated with equal weight; roots are never treated
as independent observations.
"""

from __future__ import annotations

from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd

from . import continuous, horizon as hz, panel, signals

HORIZONS = (1, 3, 6, 12)
DEFAULT_BLOCK = 6
DEFAULT_N_BOOT = 2000
DEFAULT_MIN_OBS = 60
DEFAULT_MIN_HISTORY = 60

PERIODS: dict[str, tuple[str | None, str | None]] = {
    "full": (None, None),
    "1986-1999": (None, "1999-12-31"),
    "2000-2009": ("2000-01-01", "2009-12-31"),
    "2010-2026": ("2010-01-01", None),
    "validation 2006-2015": ("2006-01-01", "2015-12-31"),
    "test 2016-2026": ("2016-01-01", None),
}


# ---------------------------------------------------------------------------
# Monthly rank-index forward returns
# ---------------------------------------------------------------------------


def _trading_days(pair_panel: pd.DataFrame, returns_panel: pd.DataFrame) -> pd.DatetimeIndex:
    """Union calendar used by the D signal: pair dates plus return dates."""

    dates = pd.Index(pd.to_datetime(pair_panel["date"])).append(
        pd.Index(pd.to_datetime(returns_panel["date"]))
    )
    return pd.DatetimeIndex(sorted(pd.to_datetime(dates).unique()))


def _root_month_ends(pair_panel: pd.DataFrame) -> pd.Series:
    """Root-specific month-end date, indexed by (root, Period)."""

    p = pair_panel[["date", "root"]].copy()
    p["date"] = pd.to_datetime(p["date"])
    p["period"] = p["date"].dt.to_period("M")
    return p.groupby(["root", "period"], sort=False)["date"].max()


def _root_dates(pair_panel: pd.DataFrame) -> dict[str, pd.DatetimeIndex]:
    p = pair_panel[["date", "root"]].copy()
    p["date"] = pd.to_datetime(p["date"])
    return {
        root: pd.DatetimeIndex(group["date"].sort_values().unique())
        for root, group in p.groupby("root", sort=False)
    }


def forward_rank_returns(
    signal: pd.DataFrame,
    pair_panel: pd.DataFrame,
    returns_panel: pd.DataFrame,
    horizons: tuple[int, ...] = HORIZONS,
    timing: str = "t+1",
    min_valid_frac: float = 0.80,
) -> pd.DataFrame:
    """Forward roll-adjusted rank-slot return for long near / short far.

    Parameters
    ----------
    signal:
        D signal rows. Must contain ``date, root, rank_near, rank_far, score``;
        rows with missing score are ignored.
    pair_panel:
        Pair panel used to define root-specific month ends and pair dates.
    returns_panel:
        Contract-level return panel mapped to ranks (``ret_rank``).
    timing:
        ``"t+1"`` starts at the first root trading day after the signal date;
        ``"same_close"`` starts at the signal date itself.
    min_valid_frac:
        Minimum share of valid return observations inside the forward window;
        a window with a negative-price/broken day is always invalid.

    Returns
    -------
    One row per signal date/root with ``fwd_{h}m``, ``fwd_{h}m_same_close``,
    and the corresponding ``end_{h}m`` dates. The return is
    ``near_rank_return - far_rank_return`` on the rank-slot indices.
    """

    if timing not in {"t+1", "same_close"}:
        raise ValueError("timing must be 't+1' or 'same_close'")

    required = {"date", "root", "rank_near", "rank_far", "score"}
    missing = required.difference(signal.columns)
    if missing:
        raise ValueError(f"signal missing columns: {sorted(missing)}")

    sig = signal.loc[signal["score"].notna(), ["date", "root", "rank_near", "rank_far"]].copy()
    sig["date"] = pd.to_datetime(sig["date"])
    sig["rank_near"] = sig["rank_near"].astype(int)
    sig["rank_far"] = sig["rank_far"].astype(int)
    sig = sig.drop_duplicates(["date", "root"]).reset_index(drop=True)

    trading_days = _trading_days(pair_panel, returns_panel)
    positions = pd.Series(np.arange(len(trading_days), dtype=int), index=trading_days)
    index_panel = signals._rank_return_index(returns_panel, trading_days)
    index_panel["date"] = pd.to_datetime(index_panel["date"])

    lookup = index_panel.set_index(["root", "rank", "date"])[
        ["rank_index", "valid_cum", "bad_cum"]
    ]
    month_ends = _root_month_ends(pair_panel)
    root_dates = _root_dates(pair_panel)

    out = sig.copy()
    for h in horizons:
        out[f"fwd_{h}m"] = np.nan
        out[f"end_{h}m"] = pd.NaT
        for timing_col in ("same_close",):
            out[f"fwd_{h}m_{timing_col}"] = np.nan
            out[f"end_{h}m_{timing_col}"] = pd.NaT

    for i, row in sig.iterrows():
        root = row["root"]
        t = pd.Timestamp(row["date"])
        dates = root_dates.get(root)
        if dates is None or len(dates) == 0:
            continue

        if timing == "t+1":
            later = dates[dates > t]
            if len(later) == 0:
                start = pd.NaT
            else:
                start = later[0]
        else:
            start = t

        period = t.to_period("M")
        for h in horizons:
            end = month_ends.get((root, period + h), pd.NaT)
            out.at[i, f"end_{h}m"] = end
            if pd.isna(start) or pd.isna(end):
                continue
            pos_start = positions.get(start)
            pos_end = positions.get(end)
            if pos_start is None or pos_end is None or pos_end <= pos_start:
                continue
            expected = int(pos_end - pos_start)
            values = {}
            valid = True
            for leg in ("near", "far"):
                rank = int(row[f"rank_{leg}"])
                try:
                    a = lookup.loc[(root, rank, start)]
                    b = lookup.loc[(root, rank, end)]
                except KeyError:
                    valid = False
                    break
                if not np.isfinite(a["rank_index"]) or not np.isfinite(b["rank_index"]):
                    valid = False
                    break
                if b["bad_cum"] - a["bad_cum"] != 0:
                    valid = False
                    break
                if (b["valid_cum"] - a["valid_cum"]) < ceil(min_valid_frac * expected):
                    valid = False
                    break
                values[leg] = b["rank_index"] / a["rank_index"] - 1.0
            if valid:
                out.at[i, f"fwd_{h}m"] = values["near"] - values["far"]

        # Same-close diagnostic: start at the signal date.
        for h in horizons:
            end = month_ends.get((root, period + h), pd.NaT)
            out.at[i, f"end_{h}m_same_close"] = end
            if pd.isna(end):
                continue
            pos_start = positions.get(t)
            pos_end = positions.get(end)
            if pos_start is None or pos_end is None or pos_end <= pos_start:
                continue
            expected = int(pos_end - pos_start)
            values = {}
            valid = True
            for leg in ("near", "far"):
                rank = int(row[f"rank_{leg}"])
                try:
                    a = lookup.loc[(root, rank, t)]
                    b = lookup.loc[(root, rank, end)]
                except KeyError:
                    valid = False
                    break
                if not np.isfinite(a["rank_index"]) or not np.isfinite(b["rank_index"]):
                    valid = False
                    break
                if b["bad_cum"] - a["bad_cum"] != 0:
                    valid = False
                    break
                if (b["valid_cum"] - a["valid_cum"]) < ceil(min_valid_frac * expected):
                    valid = False
                    break
                values[leg] = b["rank_index"] / a["rank_index"] - 1.0
            if valid:
                out.at[i, f"fwd_{h}m_same_close"] = values["near"] - values["far"]

    return out


# ---------------------------------------------------------------------------
# Panel construction
# ---------------------------------------------------------------------------


def _daily_spread_vol(pair_panel: pd.DataFrame, returns_panel: pd.DataFrame,
                      window: int = 126, min_periods: int = 90) -> pd.DataFrame:
    """Trailing daily near-minus-far rank return volatility, by root/date."""

    base = pair_panel[["date", "root", "rank_near", "rank_far"]].copy()
    base["date"] = pd.to_datetime(base["date"])
    ret = returns_panel[["date", "root", "rank", "ret_rank"]].copy()
    ret["date"] = pd.to_datetime(ret["date"])

    near = base.merge(
        ret.rename(columns={"rank": "rank_near", "ret_rank": "near_ret"}),
        on=["date", "root", "rank_near"],
        how="left",
    )
    near = near.merge(
        ret.rename(columns={"rank": "rank_far", "ret_rank": "far_ret"}),
        on=["date", "root", "rank_far"],
        how="left",
    )
    near["spread_ret"] = near["near_ret"] - near["far_ret"]
    near = near.sort_values(["root", "date"])
    near["spread_vol_6m"] = near.groupby("root", sort=False)["spread_ret"].transform(
        lambda s: s.rolling(window, min_periods=min_periods).std()
    )
    return near[["date", "root", "spread_vol_6m"]]


def build_d_panel(
    rank: pd.DataFrame,
    d: int = 5,
    k: int = 5,
    params: signals.CurveMomentumParams = signals.CurveMomentumParams(),
    min_valid_frac: float = 0.80,
) -> pd.DataFrame:
    """Build the monthly D signal-validity panel from the raw rank panel."""

    bt = panel.build_backtest_panel(rank, d=d, k=k)
    returns = panel.build_return_panel(bt["rank"], bt["contract"])
    trading_days = _trading_days(bt["pairs"], returns)

    signal = signals.curve_momentum_signal(
        bt["spread"], returns, params=params, trading_days=trading_days
    )
    sig = signal.loc[
        signal["is_signal_date"] & signal["score"].notna(),
        ["date", "root", "commodity", "sector", "score", "target", "rank_near", "rank_far"],
    ].copy()
    sig["date"] = pd.to_datetime(sig["date"])

    fwd = forward_rank_returns(
        sig, bt["pairs"], returns, timing="t+1", min_valid_frac=min_valid_frac
    )

    a = signals.carry_signal(bt["spread"])[["date", "root", "score"]].rename(
        columns={"score": "a_carry"}
    )
    a["date"] = pd.to_datetime(a["date"])

    leg = continuous.build_continuous_leg_prices(bt["pairs"], bt["contract"])
    spread_index = continuous.build_spread_index(leg)
    c = signals.mean_reversion_signal(
        spread_index,
        trading_days=trading_days,
        pair_grid=bt["pairs"][["date", "root"]],
    )[["date", "root", "score"]].rename(columns={"score": "c_z"})
    c["date"] = pd.to_datetime(c["date"])

    vol = _daily_spread_vol(bt["pairs"], returns)
    vol["date"] = pd.to_datetime(vol["date"])

    out = (
        sig.merge(fwd, on=["date", "root"], how="left", validate="one_to_one")
        .merge(a, on=["date", "root"], how="left", validate="one_to_one")
        .merge(c, on=["date", "root"], how="left", validate="one_to_one")
        .merge(vol, on=["date", "root"], how="left", validate="many_to_one")
    )
    out["static"] = 1.0
    return out.sort_values(["date", "root"]).reset_index(drop=True)


def slice_period(
    frame: pd.DataFrame, start: str | None, end: str | None
) -> pd.DataFrame:
    """Rows whose ``date`` lies inside ``[start, end]`` (inclusive)."""

    dates = pd.to_datetime(frame["date"])
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= dates >= pd.Timestamp(start)
    if end is not None:
        mask &= dates <= pd.Timestamp(end)
    return frame.loc[mask].copy()


def period_panel(
    frame: pd.DataFrame,
    horizon: int,
    start: str | None,
    end: str | None,
    timing: str = "t+1",
) -> pd.DataFrame:
    """Slice a panel and require the forward endpoint to lie inside the period."""

    out = slice_period(frame, start, end).copy()
    end_col = f"end_{horizon}m" if timing == "t+1" else f"end_{horizon}m_same_close"
    if end_col in out.columns:
        endpoint = pd.to_datetime(out[end_col])
        if start is not None:
            out = out.loc[endpoint >= pd.Timestamp(start)]
        if end is not None:
            out = out.loc[endpoint <= pd.Timestamp(end)]
    return out


# ---------------------------------------------------------------------------
# Basic statistics
# ---------------------------------------------------------------------------


def _fwd_col(horizon: int, timing: str = "t+1") -> str:
    return f"fwd_{horizon}m" if timing == "t+1" else f"fwd_{horizon}m_same_close"


def _rank_ic_series(score: pd.Series, fwd: pd.Series) -> pd.Series:
    rs = score.rank()
    rf = fwd.rank()
    return ((rs - rs.mean()) / rs.std(ddof=0)) * ((rf - rf.mean()) / rf.std(ddof=0))


def fdr_bh(pvalues: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (numpy only)."""

    p = np.asarray(pvalues, dtype=float)
    out = np.full(p.shape, np.nan, dtype=float)
    mask = np.isfinite(p)
    if not mask.any():
        return out
    values = p[mask]
    order = np.argsort(values)
    ranked = values[order]
    n = len(ranked)
    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)
    result = np.empty(n, dtype=float)
    result[order] = adjusted
    out[mask] = result
    return out


def per_root_ic(
    frame: pd.DataFrame,
    horizon: int = 1,
    score_col: str = "score",
    timing: str = "t+1",
    block: int = DEFAULT_BLOCK,
    n_boot: int = DEFAULT_N_BOOT,
    min_obs: int = DEFAULT_MIN_OBS,
    seed: int = 0,
) -> pd.DataFrame:
    """Per-root time-series rank IC with NW t and block-bootstrap CI/p."""

    col = _fwd_col(horizon, timing)
    f = frame[["date", "root", score_col, col]].dropna().sort_values(["root", "date"])
    summary, _draws = hz.block_bootstrap_ic(
        f[["date", "root", col]],
        f[["date", "root", score_col]],
        col=col,
        score_col=score_col,
        block=block,
        n_boot=n_boot,
        min_obs=min_obs,
        seed=seed,
    )
    if summary.empty:
        return summary.assign(t_nw=np.nan, p_fdr=np.nan, median_ic=np.nan, frac_positive=np.nan)

    t_stats = []
    contrib = []
    for root, g in f.groupby("root", sort=False):
        x = _rank_ic_series(g[score_col], g[col])
        t_stats.append({"root": root, "t_nw": hz.newey_west_t(x, horizon)})
        contrib.append(pd.DataFrame({"date": g["date"].to_numpy(), "x": x.to_numpy()}))
    summary = summary.merge(pd.DataFrame(t_stats), on="root", how="left")
    summary["p_fdr"] = fdr_bh(summary["p_value"].to_numpy())
    summary["median_ic"] = np.nan
    summary["frac_positive"] = np.nan

    daily = (
        pd.concat(contrib, ignore_index=True).groupby("date")["x"].mean()
        if contrib else pd.Series(dtype=float)
    )
    if len(daily) >= max(min_obs, 2 * block):
        rng = np.random.default_rng(seed)
        idx = hz._block_indices(len(daily), block, n_boot, rng)
        boot = daily.to_numpy()[idx].mean(axis=1)
        all_lo, all_hi = np.quantile(boot, [0.025, 0.975])
    else:
        all_lo, all_hi = np.nan, np.nan
    all_row = {
        "root": "ALL",
        "ic": summary["ic"].mean(),
        "ci_lo": all_lo,
        "ci_hi": all_hi,
        "p_value": np.nan,
        "n": int(summary["n"].sum()),
        "t_nw": hz.newey_west_t(daily, horizon) if len(daily) else np.nan,
        "p_fdr": np.nan,
        "median_ic": summary["ic"].median(),
        "frac_positive": float((summary["ic"] > 0).mean()),
    }
    return pd.concat([summary, pd.DataFrame([all_row])], ignore_index=True)


def hit_rate(
    frame: pd.DataFrame,
    horizon: int = 1,
    score_col: str = "target",
    timing: str = "t+1",
    block: int = DEFAULT_BLOCK,
    n_boot: int = DEFAULT_N_BOOT,
    min_obs: int = DEFAULT_MIN_OBS,
    seed: int = 0,
) -> pd.DataFrame:
    """Per-root sign hit rate with block-bootstrap CI and p vs 0.5."""

    col = _fwd_col(horizon, timing)
    f = frame[["date", "root", score_col, col]].dropna()
    f = f.loc[f[score_col].ne(0)].copy()
    f["hit"] = (np.sign(f[score_col]) == np.sign(f[col])).astype(float)
    summary, _draws = hz.block_bootstrap_mean(
        f[["date", "root", "hit"]],
        "hit",
        block=block,
        n_boot=n_boot,
        min_obs=min_obs,
        seed=seed,
        null=0.5,
    )
    if summary.empty:
        return summary
    summary = summary.rename(columns={"mean": "hit_rate"})
    daily = f.groupby("date")["hit"].mean().dropna()
    if len(daily) >= max(min_obs, 2 * block):
        rng = np.random.default_rng(seed)
        idx = hz._block_indices(len(daily), block, n_boot, rng)
        boot = daily.to_numpy()[idx].mean(axis=1)
        all_p = min(1.0, 2 * min((boot <= 0.5).mean(), (boot >= 0.5).mean()))
        all_lo, all_hi = np.quantile(boot, [0.025, 0.975])
    else:
        all_p, all_lo, all_hi = np.nan, np.nan, np.nan
    all_row = {
        "root": "ALL",
        "hit_rate": summary["hit_rate"].mean(),
        "ci_lo": all_lo,
        "ci_hi": all_hi,
        "p_value": all_p,
        "n": int(summary["n"].sum()),
    }
    return pd.concat([summary, pd.DataFrame([all_row])], ignore_index=True)


def quantile_profile(
    frame: pd.DataFrame,
    horizon: int = 1,
    score_col: str = "score",
    timing: str = "t+1",
    n_bins: int = 5,
    min_history: int = DEFAULT_MIN_HISTORY,
) -> pd.DataFrame:
    """Mean forward return by each root's expanding score quantile."""

    col = _fwd_col(horizon, timing)
    f = frame[["date", "root", score_col, col]].dropna().sort_values(["root", "date"]).copy()
    f["pct"] = f.groupby("root", sort=False)[score_col].transform(
        lambda s: s.expanding().rank(pct=True)
    )
    f["count"] = f.groupby("root", sort=False).cumcount()
    f = f.loc[f["count"] >= min_history].copy()
    f["bin"] = np.ceil(f["pct"] * n_bins).clip(1, n_bins).astype(int)

    rows = []
    for b, group in f.groupby("bin", sort=True):
        daily = group.groupby("date")[col].mean().dropna()
        rows.append(
            {
                "bin": int(b),
                "mean_bps": daily.mean() * 1e4,
                "t_nw": hz.newey_west_t(daily, horizon),
                "n": len(group),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Predictive regressions and incremental information
# ---------------------------------------------------------------------------


def _ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, float, float]:
    """OLS with intercept; returns beta, R2, adjusted R2."""

    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ beta
    resid = y - fitted
    sst = float(((y - y.mean()) ** 2).sum())
    ssr = float((resid ** 2).sum())
    r2 = 1.0 - ssr / sst if sst > 0 else np.nan
    n, p = X.shape
    adj = 1.0 - (1.0 - r2) * (n - 1) / (n - p) if np.isfinite(r2) and n > p else np.nan
    return beta, r2, adj


def _design(g: pd.DataFrame, columns: list[str]) -> np.ndarray:
    return np.column_stack([np.ones(len(g)), g[columns].to_numpy(float)])


def _bootstrap_ols(
    g: pd.DataFrame,
    y_col: str,
    columns: list[str],
    block: int,
    n_boot: int,
    rng: np.random.Generator,
    stat: str = "adj_r2",
) -> tuple[np.ndarray, np.ndarray]:
    """Block bootstrap of an OLS statistic and the score coefficient."""

    y = g[y_col].to_numpy(float)
    X = _design(g, columns)
    _beta, _r2, adj = _ols(y, X)
    idx = hz._block_indices(len(g), block, n_boot, rng)
    coef = np.empty(n_boot)
    stats = np.empty(n_boot)
    for i in range(n_boot):
        pos = idx[i]
        beta, r2, adj_i = _ols(y[pos], X[pos])
        coef[i] = beta[1] if len(beta) > 1 else np.nan
        stats[i] = adj_i if stat == "adj_r2" else r2
    return coef, stats


def predictive_regression(
    frame: pd.DataFrame,
    horizon: int = 1,
    controls: tuple[str, ...] = (),
    score_col: str = "score",
    timing: str = "t+1",
    block: int = DEFAULT_BLOCK,
    n_boot: int = DEFAULT_N_BOOT,
    min_obs: int = DEFAULT_MIN_OBS,
    seed: int = 0,
) -> pd.DataFrame:
    """Per-root OLS of the forward return on score plus controls."""

    col = _fwd_col(horizon, timing)
    columns = [score_col, *controls]
    f = frame[["date", "root", col, *columns]].dropna().sort_values(["root", "date"])
    rng = np.random.default_rng(seed)
    rows = []
    for root, g in f.groupby("root", sort=False):
        if len(g) < max(min_obs, 2 * block):
            continue
        y = g[col].to_numpy(float)
        X = _design(g, columns)
        beta, r2, adj = _ols(y, X)
        coef, stats = _bootstrap_ols(g, col, columns, block, n_boot, rng)
        p = min(1.0, 2 * min((coef <= 0).mean(), (coef >= 0).mean()))
        lo, hi = np.quantile(coef, [0.025, 0.975])
        rows.append(
            {
                "root": root,
                "beta_score": beta[1],
                "beta_lo": lo,
                "beta_hi": hi,
                "p_value": p,
                "r2": r2,
                "adj_r2": adj,
                "n": len(g),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    all_row = {
        "root": "ALL",
        "beta_score": out["beta_score"].mean(),
        "beta_lo": np.nan,
        "beta_hi": np.nan,
        "p_value": np.nan,
        "r2": out["r2"].mean(),
        "adj_r2": out["adj_r2"].mean(),
        "n": int(out["n"].sum()),
    }
    return pd.concat([out, pd.DataFrame([all_row])], ignore_index=True)


def _nested_models(controls: tuple[str, ...]) -> list[tuple[str, list[str]]]:
    base: list[str] = []
    models = [("static", list(base))]
    base = ["score"]
    models.append(("+D", list(base)))
    if "a_carry" in controls:
        base = ["score", "a_carry"]
        models.append(("+A", list(base)))
    if "c_z" in controls:
        base = ["score", "a_carry", "c_z"]
        models.append(("+C", list(base)))
    return models


def incremental_information(
    frame: pd.DataFrame,
    horizon: int = 1,
    controls: tuple[str, ...] = ("a_carry", "c_z"),
    score_col: str = "score",
    timing: str = "t+1",
    block: int = DEFAULT_BLOCK,
    n_boot: int = DEFAULT_N_BOOT,
    min_obs: int = DEFAULT_MIN_OBS,
    seed: int = 0,
) -> dict[str, pd.DataFrame]:
    """Nested adjusted-R2, incremental IC, and D vs static +1."""

    col = _fwd_col(horizon, timing)
    models = _nested_models(controls)
    columns = [score_col, *[c for c in controls if c in frame.columns]]
    f = frame[["date", "root", col, *columns]].dropna().sort_values(["root", "date"])
    rng = np.random.default_rng(seed)

    per_root_rows = []
    delta_rows = []
    for root, g in f.groupby("root", sort=False):
        if len(g) < max(min_obs, 2 * block):
            continue
        y = g[col].to_numpy(float)
        fits = {}
        for name, cols in models:
            if not set(cols).issubset(g.columns):
                continue
            X = _design(g, cols)
            beta, r2, adj = _ols(y, X)
            fits[name] = {"beta": beta, "r2": r2, "adj": adj, "cols": cols}
        if "static" not in fits or "+D" not in fits:
            continue
        per_root_rows.append(
            {
                "root": root,
                **{f"adj_{name}": fit["adj"] for name, fit in fits.items()},
                **{f"r2_{name}": fit["r2"] for name, fit in fits.items()},
                "n": len(g),
            }
        )
        names = [name for name, _ in models if name in fits]
        for prev, nxt in zip(names[:-1], names[1:]):
            delta = fits[nxt]["adj"] - fits[prev]["adj"]
            idx = hz._block_indices(len(g), block, n_boot, rng)
            draws = np.empty(n_boot)
            for i in range(n_boot):
                pos = idx[i]
                yb, gb = y[pos], g.iloc[pos]
                adj_prev = _ols(yb, _design(gb, fits[prev]["cols"]))[2]
                adj_next = _ols(yb, _design(gb, fits[nxt]["cols"]))[2]
                draws[i] = adj_next - adj_prev
            p = min(1.0, 2 * min((draws <= 0).mean(), (draws >= 0).mean()))
            delta_rows.append(
                {
                    "root": root,
                    "step": f"{prev} -> {nxt}",
                    "delta_adj_r2": delta,
                    "ci_lo": np.quantile(draws, 0.025),
                    "ci_hi": np.quantile(draws, 0.975),
                    "p_value": p,
                    "n": len(g),
                }
            )

    per_root = pd.DataFrame(per_root_rows)
    deltas = pd.DataFrame(delta_rows)
    if not per_root.empty:
        all_row = {"root": "ALL", "n": int(per_root["n"].sum())}
        for name, _ in models:
            for prefix in ("adj", "r2"):
                key = f"{prefix}_{name}"
                if key in per_root.columns:
                    all_row[key] = per_root[key].mean()
        per_root = pd.concat([per_root, pd.DataFrame([all_row])], ignore_index=True)
    if not deltas.empty:
        agg = (
            deltas.groupby("step", sort=False)
            .agg(
                delta_adj_r2=("delta_adj_r2", "mean"),
                ci_lo=("ci_lo", "mean"),
                ci_hi=("ci_hi", "mean"),
                p_value=("p_value", "median"),
                n=("n", "sum"),
            )
            .reset_index()
        )
        agg["root"] = "ALL"
        deltas = pd.concat(
            [deltas, agg[["root", "step", "delta_adj_r2", "ci_lo", "ci_hi", "p_value", "n"]]],
            ignore_index=True,
        )

    # Residualized-score IC after A/C/static.
    residual_rows = []
    raw_rows = []
    for root, g in f.groupby("root", sort=False):
        if len(g) < max(min_obs, 2 * block):
            continue
        controls_present = [c for c in controls if c in g.columns]
        X = _design(g, controls_present)
        beta, *_ = np.linalg.lstsq(X, g[score_col].to_numpy(float), rcond=None)
        resid = g[score_col].to_numpy(float) - X @ beta
        raw = _rank_ic_series(g[score_col], g[col]).mean()
        res = _rank_ic_series(pd.Series(resid, index=g.index), g[col]).mean()
        idx = hz._block_indices(len(g), block, n_boot, rng)
        gain_draws = np.empty(n_boot)
        for i in range(n_boot):
            pos = idx[i]
            gb = g.iloc[pos]
            raw_b = _rank_ic_series(gb[score_col], gb[col]).mean()
            res_b = _rank_ic_series(
                pd.Series(resid[pos], index=gb.index), gb[col]
            ).mean()
            gain_draws[i] = res_b - raw_b
        p = min(1.0, 2 * min((gain_draws <= 0).mean(), (gain_draws >= 0).mean()))
        raw_rows.append({"root": root, "ic_raw": raw})
        residual_rows.append(
            {
                "root": root,
                "ic_residual": res,
                "ic_gain": res - raw,
                "ci_lo": np.quantile(gain_draws, 0.025),
                "ci_hi": np.quantile(gain_draws, 0.975),
                "p_value": p,
            }
        )
    raw = pd.DataFrame(raw_rows)
    residual = pd.DataFrame(residual_rows)
    if not raw.empty:
        raw = pd.concat(
            [raw, pd.DataFrame([{"root": "ALL", "ic_raw": raw["ic_raw"].mean()}])],
            ignore_index=True,
        )
    if not residual.empty:
        residual = pd.concat(
            [
                residual,
                pd.DataFrame(
                    [{
                        "root": "ALL",
                        "ic_residual": residual["ic_residual"].mean(),
                        "ic_gain": residual["ic_gain"].mean(),
                        "ci_lo": np.nan,
                        "ci_hi": np.nan,
                        "p_value": np.nan,
                        "frac_positive_gain": float((residual["ic_gain"] > 0).mean()),
                    }]
                ),
            ],
            ignore_index=True,
        )

    # D vs static: always-long mean, long/short means, and the timing spread.
    static_rows = []
    for root, g in f.groupby("root", sort=False):
        if len(g) < max(min_obs, 2 * block):
            continue
        y = g[col].to_numpy(float)
        target = np.sign(g[score_col].to_numpy(float))
        X = np.column_stack([np.ones(len(g)), target])
        beta, r2, adj = _ols(y, X)
        long_mean = y[target > 0].mean() if (target > 0).any() else np.nan
        short_mean = y[target < 0].mean() if (target < 0).any() else np.nan
        static_rows.append(
            {
                "root": root,
                "static_mean_bps": y.mean() * 1e4,
                "long_mean_bps": long_mean * 1e4,
                "short_mean_bps": short_mean * 1e4,
                "timing_spread_bps": (long_mean - short_mean) * 1e4,
                "r2": r2,
                "n": len(g),
            }
        )
    static = pd.DataFrame(static_rows)
    if not static.empty:
        static = pd.concat(
            [
                static,
                pd.DataFrame(
                    [{
                        "root": "ALL",
                        "static_mean_bps": static["static_mean_bps"].mean(),
                        "long_mean_bps": static["long_mean_bps"].mean(),
                        "short_mean_bps": static["short_mean_bps"].mean(),
                        "timing_spread_bps": static["timing_spread_bps"].mean(),
                        "r2": static["r2"].mean(),
                        "n": int(static["n"].sum()),
                    }]
                ),
            ],
            ignore_index=True,
        )

    return {
        "per_root": per_root,
        "deltas": deltas,
        "raw_ic": raw,
        "residual_ic": residual,
        "static": static,
    }


# ---------------------------------------------------------------------------
# Stability and placebo
# ---------------------------------------------------------------------------


def _decade(dates: pd.Series) -> pd.Series:
    year = pd.to_datetime(dates).dt.year
    return pd.cut(
        year,
        bins=[1985, 1999, 2009, 2026],
        labels=["1986-1999", "2000-2009", "2010-2026"],
    ).astype(str)


def _rolling_ic(
    frame: pd.DataFrame,
    horizon: int,
    score_col: str = "score",
    timing: str = "t+1",
    window: int = 36,
) -> pd.Series:
    """Date-indexed mean rolling IC across roots (pandas-3 safe)."""

    col = _fwd_col(horizon, timing)
    f = frame[["date", "root", score_col, col]].dropna().sort_values(["root", "date"])
    parts = []
    for root, g in f.groupby("root", sort=False):
        if len(g) < window:
            continue
        corr = g[score_col].rolling(window, min_periods=window).corr(g[col])
        parts.append(
            pd.DataFrame(
                {"date": g["date"].to_numpy(), "root": root, "ic": corr.to_numpy()}
            )
        )
    if not parts:
        return pd.Series(dtype=float, name="rolling_ic")
    panel = pd.concat(parts, ignore_index=True)
    wide = panel.pivot_table(index="date", columns="root", values="ic")
    enough = wide.notna().sum(axis=1) >= max(1, wide.shape[1] // 2)
    return wide.mean(axis=1).where(enough).dropna().rename("rolling_ic")


def stability(
    frame: pd.DataFrame,
    horizon: int = 1,
    score_col: str = "score",
    timing: str = "t+1",
    min_obs: int = 20,
) -> dict[str, pd.DataFrame]:
    """IC/hit-rate by decade, carry state, and vol tercile; rolling IC."""

    col = _fwd_col(horizon, timing)
    f = frame[["date", "root", score_col, col, "a_carry", "spread_vol_6m"]].dropna(
        subset=["date", "root", score_col, col]
    ).copy()
    f["decade"] = _decade(f["date"])
    f["carry_state"] = pd.Series(pd.NA, index=f.index, dtype="object")
    carry_ok = f["a_carry"].notna()
    f.loc[carry_ok, "carry_state"] = np.where(
        f.loc[carry_ok, "a_carry"] > 0, "backwardation", "contango"
    )
    f["vol_pct"] = f.groupby("root", sort=False)["spread_vol_6m"].transform(
        lambda s: s.expanding(min_periods=24).rank(pct=True)
    )
    f["vol_state"] = pd.cut(
        f["vol_pct"],
        bins=[0.0, 1 / 3, 2 / 3, 1.0],
        labels=["low", "mid", "high"],
        include_lowest=True,
    ).astype("object")

    rows = []
    for group_type, group_col in (
        ("decade", "decade"),
        ("carry", "carry_state"),
        ("vol", "vol_state"),
    ):
        for group, g in f.dropna(subset=[group_col]).groupby(group_col, sort=True):
            root_ics = []
            for _root, gr in g.groupby("root", sort=False):
                if len(gr) < min_obs:
                    continue
                root_ics.append(_rank_ic_series(gr[score_col], gr[col]).mean())
            if not root_ics:
                continue
            rows.append(
                {
                    "group_type": group_type,
                    "group": group,
                    "ic_mean": float(np.mean(root_ics)),
                    "ic_median": float(np.median(root_ics)),
                    "frac_positive": float(np.mean(np.array(root_ics) > 0)),
                    "n_roots": len(root_ics),
                    "n_obs": len(g),
                }
            )
    table = pd.DataFrame(rows)

    # Per-root sign consistency.
    root_ics = []
    for _root, gr in f.groupby("root", sort=False):
        if len(gr) < DEFAULT_MIN_OBS:
            continue
        root_ics.append(_rank_ic_series(gr[score_col], gr[col]).mean())
    sign = pd.DataFrame(
        [
            {
                "n_roots": len(root_ics),
                "frac_positive": float(np.mean(np.array(root_ics) > 0)) if root_ics else np.nan,
                "ic_mean": float(np.mean(root_ics)) if root_ics else np.nan,
                "ic_median": float(np.median(root_ics)) if root_ics else np.nan,
            }
        ]
    )

    rolling = _rolling_ic(
        f, horizon=horizon, score_col=score_col, timing=timing, window=36
    )
    rolling_table = pd.DataFrame(
        [
            {
                "window_months": 36,
                "positive_share": float((rolling > 0).mean()) if len(rolling) else np.nan,
                "n_dates": len(rolling),
            }
        ]
    )
    return {"groups": table, "sign": sign, "rolling": rolling, "rolling_table": rolling_table}


def _block_shuffle(values: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    """Permute consecutive blocks of a 1-D array."""

    n = len(values)
    n_blocks = int(np.ceil(n / block))
    blocks = [values[i * block : (i + 1) * block] for i in range(n_blocks)]
    order = rng.permutation(n_blocks)
    return np.concatenate([blocks[i] for i in order])[:n]


def placebo(
    frame: pd.DataFrame,
    horizon: int = 1,
    score_col: str = "score",
    timing: str = "t+1",
    n_shuffle: int = 1000,
    block: int = DEFAULT_BLOCK,
    min_obs: int = DEFAULT_MIN_OBS,
    seed: int = 0,
) -> dict[str, object]:
    """Sign-flip, block-shuffle, lag, and future-score placebo tests."""

    col = _fwd_col(horizon, timing)
    f = frame[["date", "root", score_col, col]].dropna().sort_values(["root", "date"]).copy()
    rng = np.random.default_rng(seed)

    def root_ic(g: pd.DataFrame, values: np.ndarray) -> float:
        return _rank_ic_series(pd.Series(values, index=g.index), g[col]).mean()

    # Actual and sign flip.
    actual = []
    flipped = []
    for _root, g in f.groupby("root", sort=False):
        if len(g) < max(min_obs, 2 * block):
            continue
        actual.append(root_ic(g, g[score_col].to_numpy(float)))
        flipped.append(root_ic(g, -g[score_col].to_numpy(float)))
    actual_mean = float(np.mean(actual)) if actual else np.nan
    flipped_mean = float(np.mean(flipped)) if flipped else np.nan

    # Block shuffle null: aggregate mean IC and max |IC| across roots.
    roots = []
    for root, g in f.groupby("root", sort=False):
        if len(g) < max(min_obs, 2 * block):
            continue
        roots.append((root, g))
    null_mean = np.empty(n_shuffle)
    null_max = np.empty(n_shuffle)
    for i in range(n_shuffle):
        ics = []
        for _root, g in roots:
            shuffled = _block_shuffle(g[score_col].to_numpy(float), block, rng)
            ics.append(root_ic(g, shuffled))
        null_mean[i] = np.mean(ics) if ics else np.nan
        null_max[i] = np.max(np.abs(ics)) if ics else np.nan
    p_mean = float((null_mean >= actual_mean).mean()) if actual else np.nan
    actual_max = float(np.max(np.abs(actual))) if actual else np.nan
    p_max = float((null_max >= actual_max).mean()) if actual else np.nan

    # Lagged signal and future-score lead.
    lag_rows = []
    for lag in (1, 3, 6, 12, -24):
        ics = []
        for _root, g in f.groupby("root", sort=False):
            if len(g) < max(min_obs, 2 * block):
                continue
            shifted = g[score_col].shift(lag).to_numpy(float)
            mask = np.isfinite(shifted)
            if mask.sum() < min_obs:
                continue
            ics.append(root_ic(g.loc[mask], shifted[mask]))
        lag_rows.append(
            {
                "shift_months": lag,
                "label": "future_score_lead_24m" if lag == -24 else f"lag_{lag}m",
                "ic_mean": float(np.mean(ics)) if ics else np.nan,
                "n_roots": len(ics),
            }
        )

    summary = pd.DataFrame(
        [
            {"test": "actual", "ic_mean": actual_mean, "p_value": np.nan, "n_roots": len(actual)},
            {"test": "sign_flip", "ic_mean": flipped_mean, "p_value": np.nan, "n_roots": len(flipped)},
            {"test": "block_shuffle", "ic_mean": actual_mean, "p_value": p_mean, "n_roots": len(actual)},
            {"test": "max_abs_ic", "ic_mean": actual_max, "p_value": p_max, "n_roots": len(actual)},
        ]
    )
    return {
        "summary": summary,
        "lag": pd.DataFrame(lag_rows),
        "null_mean": null_mean,
        "null_max": null_max,
        "actual_mean": actual_mean,
        "actual_max": actual_max,
    }


# ---------------------------------------------------------------------------
# Horizon profile and convenience wrapper
# ---------------------------------------------------------------------------


def horizon_profile(
    frame: pd.DataFrame,
    horizons: tuple[int, ...] = HORIZONS,
    score_col: str = "score",
    timing: str = "t+1",
    block: int = DEFAULT_BLOCK,
    n_boot: int = DEFAULT_N_BOOT,
    min_obs: int = DEFAULT_MIN_OBS,
) -> pd.DataFrame:
    """IC, hit rate, and signed return by forward hz."""

    rows = []
    for h in horizons:
        ic = per_root_ic(
            frame, horizon=h, score_col=score_col, timing=timing,
            block=block, n_boot=n_boot, min_obs=min_obs,
        )
        hit = hit_rate(
            frame, horizon=h, timing=timing, block=block,
            n_boot=n_boot, min_obs=min_obs,
        )
        col = _fwd_col(h, timing)
        f = frame[["date", "root", "target", col]].dropna()
        f = f.loc[f["target"].ne(0)]
        signed = 0.5 * f["target"] * f[col]
        daily = signed.groupby(f["date"]).mean().dropna()
        all_ic = ic.loc[ic["root"].eq("ALL")].iloc[0] if ic["root"].eq("ALL").any() else None
        all_hit = hit.loc[hit["root"].eq("ALL")].iloc[0] if hit["root"].eq("ALL").any() else None
        rows.append(
            {
                "horizon_months": h,
                "ic_mean": all_ic["ic"] if all_ic is not None else np.nan,
                "ic_median": all_ic["median_ic"] if all_ic is not None else np.nan,
                "frac_positive": all_ic["frac_positive"] if all_ic is not None else np.nan,
                "hit_rate": all_hit["hit_rate"] if all_hit is not None else np.nan,
                "mean_bps": daily.mean() * 1e4,
                "t_nw": hz.newey_west_t(daily, h),
                "n_dates": len(daily),
            }
        )
    return pd.DataFrame(rows)


def save_tables(out: dict[str, object], directory: str | Path) -> Path:
    """Write the standard validity tables to ``directory`` as CSVs."""

    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)

    def write(name: str, frame: pd.DataFrame) -> None:
        frame.to_csv(path / f"{name}.csv", index=False)

    write("ic", out["ic"])
    write("hit", out["hit"])
    write("quantiles", out["quantiles"])
    write("regression", out["regression"])
    write("horizon", out["horizon"])
    inc = out["incremental"]
    for name in ("per_root", "deltas", "raw_ic", "residual_ic", "static"):
        write(f"incremental_{name}", inc[name])
    stab = out["stability"]
    write("stability_groups", stab["groups"])
    write("stability_sign", stab["sign"])
    write("stability_rolling_table", stab["rolling_table"])
    stab["rolling"].rename("rolling_ic").to_csv(path / "stability_rolling.csv")
    write("placebo_summary", out["placebo"]["summary"])
    write("placebo_lag", out["placebo"]["lag"])
    pd.DataFrame(
        {
            "null_mean": out["placebo"]["null_mean"],
            "null_max": out["placebo"]["null_max"],
        }
    ).to_csv(path / "placebo_null.csv", index=False)
    return path


def run_all(
    frame: pd.DataFrame,
    horizons: tuple[int, ...] = HORIZONS,
    block: int = DEFAULT_BLOCK,
    n_boot: int = DEFAULT_N_BOOT,
    min_obs: int = DEFAULT_MIN_OBS,
    n_shuffle: int = 1000,
    seed: int = 0,
) -> dict[str, object]:
    """Run the standard validity battery on a built panel."""

    core = {
        "ic": per_root_ic(frame, 1, block=block, n_boot=n_boot, min_obs=min_obs, seed=seed),
        "hit": hit_rate(frame, 1, block=block, n_boot=n_boot, min_obs=min_obs, seed=seed),
        "quantiles": quantile_profile(frame, 1),
        "regression": predictive_regression(
            frame, 1, block=block, n_boot=n_boot, min_obs=min_obs, seed=seed
        ),
        "incremental": incremental_information(
            frame, 1, block=block, n_boot=n_boot, min_obs=min_obs, seed=seed
        ),
        "stability": stability(frame, 1),
        "placebo": placebo(
            frame, 1, n_shuffle=n_shuffle, block=block, min_obs=min_obs, seed=seed
        ),
        "horizon": horizon_profile(
            frame, horizons, block=block, n_boot=n_boot, min_obs=min_obs
        ),
    }
    return core

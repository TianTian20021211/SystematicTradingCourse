"""Information diagnostics for the daily C audit (D-025).

The functions here are execution-independent where possible: event studies,
time-series IC, same-settle vs tradable timing, persistence, nested predictive
regressions and a circular-shift placebo. They take explicit period slices so
stage 1 can keep every artifact before 2016.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import c_daily, horizon, report, signals

HORIZONS: dict[int, tuple[int, int]] = {1: (1, 2), 5: (1, 6), 10: (1, 11), 20: (1, 21)}
MIN_OBS = 252


def _slice(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    if start is not None:
        out = out.loc[out["date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out.loc[out["date"] <= pd.Timestamp(end)]
    return out


def event_study(
    signal: pd.DataFrame,
    fwd: pd.DataFrame,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Signed forward returns after fresh entries and sign flips.

    Events are defined on the daily target path: a fresh entry is a nonzero
    target after a zero target; a flip is a sign change without going flat.
    Returns are aggregated across roots by date, then over dates; the NW lag is
    the horizon length. Overlapping events are kept and counted.
    """

    cols = ["date", "root", "target"]
    s = _slice(signal[cols], start, end).sort_values(["root", "date"])
    f = _slice(fwd[["date", "root", *[f"fwd_{a}_{b}" for a, b in HORIZONS.values()]]], start, end)
    data = s.merge(f, on=["date", "root"], how="inner").sort_values(["root", "date"])
    data["prev_target"] = data.groupby("root")["target"].shift().fillna(0.0)
    data["fresh"] = data["target"].ne(0) & data["prev_target"].eq(0)
    data["flip"] = (
        data["target"].ne(0)
        & data["prev_target"].ne(0)
        & np.sign(data["target"]).ne(np.sign(data["prev_target"]))
    )
    rows = []
    for event_name, mask in (("fresh", data["fresh"]), ("flip", data["flip"])):
        event = data.loc[mask].copy()
        for side_name, side_mask in (
            ("all", pd.Series(True, index=event.index)),
            ("long", event["target"] > 0),
            ("short", event["target"] < 0),
        ):
            sub = event.loc[side_mask]
            if sub.empty:
                continue
            for days, (a, b) in HORIZONS.items():
                col = f"fwd_{a}_{b}"
                x = (np.sign(sub["target"]) * sub[col]).dropna()
                if x.empty:
                    continue
                daily = (
                    pd.DataFrame({"date": sub.loc[x.index, "date"], "x": x})
                    .groupby("date")["x"]
                    .mean()
                )
                hit = float(
                    (np.sign(sub.loc[x.index, "target"]) == np.sign(sub.loc[x.index, col])).mean()
                )
                rows.append(
                    {
                        "event": event_name,
                        "side": side_name,
                        "horizon_days": days,
                        "mean_bps": float(x.mean() * 1e4),
                        "median_bps": float(x.median() * 1e4),
                        "hit_rate": hit,
                        "t_nw": float(horizon.newey_west_t(daily, days)),
                        "n_events": int(len(x)),
                        "n_dates": int(daily.size),
                    }
                )
    return pd.DataFrame(rows)


def ic_table(
    signal: pd.DataFrame,
    fwd: pd.DataFrame,
    start: str | None = None,
    end: str | None = None,
    block: int = 21,
    n_boot: int = 2_000,
    seed: int = 0,
) -> pd.DataFrame:
    """Per-root time-series IC of ``-z`` and its block-bootstrap CI."""

    s = _slice(signal[["date", "root", "score"]], start, end).copy()
    s["score"] = -s["score"]
    f = _slice(fwd, start, end)
    rows = []
    for days, (a, b) in HORIZONS.items():
        col = f"fwd_{a}_{b}"
        if col not in f.columns:
            continue
        point = horizon.ts_ic(f, s, col=col, score_col="score", min_obs=MIN_OBS)
        boot, _draws = horizon.block_bootstrap_ic(
            f,
            s,
            col=col,
            score_col="score",
            block=block,
            n_boot=n_boot,
            min_obs=MIN_OBS,
            seed=seed,
        )
        boot = boot.set_index("root")
        for row in point.itertuples(index=False):
            b = boot.loc[row.root] if row.root in boot.index else None
            rows.append(
                {
                    "horizon_days": days,
                    "root": row.root,
                    "ic": row.ic,
                    "t_nw": row.t_nw,
                    "n": row.n,
                    "ci_lo": float(b["ci_lo"]) if b is not None else np.nan,
                    "ci_hi": float(b["ci_hi"]) if b is not None else np.nan,
                    "p_value": float(b["p_value"]) if b is not None else np.nan,
                }
            )
    return pd.DataFrame(rows)


def timing_table(
    signal: pd.DataFrame,
    fwd: pd.DataFrame,
    periods: dict[str, tuple[str | None, str | None]],
) -> pd.DataFrame:
    """Execution-free gross returns for same-settle and tradable windows.

    ``[t, t+1]`` is the paper-style same-settle fill (not tradable);
    ``[t+1, t+2]`` is the first tradable day. Multi-day windows are reported
    as signal diagnostics, not as annualised strategy returns.
    """

    rows = []
    windows = {
        "same-settle [t,t+1]": "fwd_0_1",
        "tradable [t+1,t+2]": "fwd_1_2",
        "t+1..t+6": "fwd_1_6",
        "t+1..t+11": "fwd_1_11",
        "t+1..t+21": "fwd_1_21",
    }
    for period, (start, end) in periods.items():
        s = _slice(signal, start, end)
        f = _slice(fwd, start, end)
        for label, col in windows.items():
            if col not in f.columns:
                continue
            r = report.execution_free_returns(f, s, col)
            stats = report.return_summary(r)
            rows.append(
                {
                    "period": period,
                    "timing": label,
                    "window": col,
                    **stats,
                }
            )
    return pd.DataFrame(rows)


def _ar1(series: pd.Series) -> dict:
    """AR(1) coefficient, its t-stat and the half-life (constant included)."""

    x = series.dropna().to_numpy(float)
    if len(x) < MIN_OBS or np.ptp(x) == 0:
        return {"phi": np.nan, "t": np.nan, "half_life": np.nan, "n": len(x)}
    y = np.diff(x)
    X = np.column_stack([np.ones(len(y)), x[:-1]])
    beta, _resid, _rank, _sv = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    dof = len(y) - X.shape[1]
    if dof <= 0:
        return {"phi": np.nan, "t": np.nan, "half_life": np.nan, "n": len(x)}
    s2 = float(e @ e / dof)
    try:
        se = float(np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1]))
    except np.linalg.LinAlgError:
        return {"phi": np.nan, "t": np.nan, "half_life": np.nan, "n": len(x)}
    phi = 1.0 + float(beta[1])
    half_life = -np.log(2.0) / np.log(phi) if 0.0 < phi < 1.0 else np.nan
    return {
        "phi": phi,
        "t": float(beta[1] / se) if se > 0 else np.nan,
        "half_life": half_life,
        "n": len(x),
    }


def persistence_table(
    signal: pd.DataFrame,
    periods: dict[str, tuple[str | None, str | None]],
) -> pd.DataFrame:
    """Per-root AR(1) half-life of the spread level and of the z-score."""

    rows = []
    for period, (start, end) in periods.items():
        s = _slice(signal[["date", "root", "spread_index", "score"]], start, end)
        for root, g in s.sort_values(["root", "date"]).groupby("root"):
            level = _ar1(g["spread_index"])
            z = _ar1(g["score"])
            rows.append(
                {
                    "period": period,
                    "root": root,
                    "phi_level": level["phi"],
                    "t_level": level["t"],
                    "half_life_level": level["half_life"],
                    "phi_z": z["phi"],
                    "half_life_z": z["half_life"],
                    "n": level["n"],
                }
            )
    return pd.DataFrame(rows)


def _ols_r2(X: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    """OLS R2, adjusted R2 and n; NaNs if the design is singular."""

    n, p = X.shape
    if n <= p:
        return np.nan, np.nan, n
    beta, _resid, _rank, _sv = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0:
        return np.nan, np.nan, n
    r2 = 1.0 - float(resid @ resid) / sst
    adj = 1.0 - (1.0 - r2) * (n - 1) / (n - p - 1)
    return r2, adj, n


def nested_predictive_table(
    signal: pd.DataFrame,
    fwd: pd.DataFrame,
    carry: pd.DataFrame,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Nested per-root regressions of the 5-day forward return on -z and controls.

    Models: M0 = -z; M1 = -z + carry; M2 = -z + 20-day spread momentum;
    M3 = both. Reports in-sample R², adjusted R² and a simple 60/40 OOS R².
    """

    s = _slice(signal[["date", "root", "score", "spread_index"]], start, end).copy()
    s = s.sort_values(["root", "date"])
    s["z"] = -s["score"]
    s["mom20"] = s.groupby("root")["spread_index"].transform(lambda x: x - x.shift(20))
    s = s.merge(
        _slice(carry[["date", "root", "carry_ann"]], start, end),
        on=["date", "root"],
        how="left",
    )
    f = _slice(fwd[["date", "root", "fwd_1_6"]], start, end)
    data = s.merge(f, on=["date", "root"], how="inner")
    rows = []
    models = {
        "M0_z": ["z"],
        "M1_z_carry": ["z", "carry_ann"],
        "M2_z_mom": ["z", "mom20"],
        "M3_z_both": ["z", "carry_ann", "mom20"],
    }
    for root, g in data.groupby("root"):
        g = g.dropna(subset=["fwd_1_6", "z", "carry_ann", "mom20"])
        if len(g) < MIN_OBS:
            continue
        y = g["fwd_1_6"].to_numpy(float)
        for name, cols in models.items():
            X = np.column_stack([np.ones(len(g)), g[cols].to_numpy(float)])
            r2, adj, n = _ols_r2(X, y)
            split = int(0.6 * n)
            if split > X.shape[1] and n - split > X.shape[1]:
                beta, _resid, _rank, _sv = np.linalg.lstsq(
                    X[:split], y[:split], rcond=None
                )
                pred = X[split:] @ beta
                sst = float(((y[split:] - y[split:].mean()) ** 2).sum())
                oos = 1.0 - float(((y[split:] - pred) ** 2).sum()) / sst if sst > 0 else np.nan
            else:
                oos = np.nan
            rows.append(
                {
                    "root": root,
                    "model": name,
                    "r2": r2,
                    "adj_r2": adj,
                    "oos_r2": oos,
                    "n": n,
                }
            )
    return pd.DataFrame(rows)


def placebo_table(
    signal: pd.DataFrame,
    fwd: pd.DataFrame,
    start: str | None = None,
    end: str | None = None,
    n_draws: int = 1_000,
    min_shift: int = 63,
    seed: int = 0,
) -> tuple[dict, np.ndarray]:
    """Circular-shift placebo for the execution-free tradable SR.

    Each root's target series is rolled by a random offset of at least
    ``min_shift`` days. This preserves each root's target distribution and
    local serial dependence while destroying the cross-root and calendar
    alignment. It is a signal-level placebo, not a full-engine placebo.
    """

    s = _slice(signal[["date", "root", "target"]], start, end)
    f = _slice(fwd[["date", "root", "fwd_1_2"]], start, end)
    wide_target = (
        s.pivot(index="date", columns="root", values="target").fillna(0.0).sort_index()
    )
    wide_fwd = (
        f.pivot(index="date", columns="root", values="fwd_1_2")
        .reindex(index=wide_target.index, columns=wide_target.columns)
    )

    def _sr(target: pd.DataFrame) -> float:
        act = target.ne(0) & wide_fwd.notna()
        c = (0.5 * target * wide_fwd).where(act)
        daily = c.sum(axis=1) / act.sum(axis=1).replace(0, np.nan)
        r = daily.dropna()
        return c_daily.sharpe(r) if len(r) > 1 else np.nan

    actual = _sr(wide_target)
    rng = np.random.default_rng(seed)
    draws = np.full(n_draws, np.nan)
    n = len(wide_target)
    for i in range(n_draws):
        shifted = wide_target.copy()
        for j, root in enumerate(wide_target.columns):
            if n > 2 * min_shift:
                offset = int(rng.integers(min_shift, n - min_shift))
                shifted[root] = np.roll(wide_target[root].to_numpy(), offset)
        draws[i] = _sr(shifted)
    valid = draws[np.isfinite(draws)]
    p_one = float((valid >= actual).mean()) if len(valid) else np.nan
    summary = {
        "actual_sr": actual,
        "placebo_mean_sr": float(valid.mean()) if len(valid) else np.nan,
        "placebo_sd_sr": float(valid.std()) if len(valid) else np.nan,
        "placebo_p025_sr": float(np.quantile(valid, 0.025)) if len(valid) else np.nan,
        "placebo_p975_sr": float(np.quantile(valid, 0.975)) if len(valid) else np.nan,
        "p_one_sided": p_one,
        "p_two_sided": float(min(1.0, 2.0 * min(p_one, 1.0 - p_one))) if np.isfinite(p_one) else np.nan,
        "n_draws": int(len(valid)),
        "min_shift": min_shift,
    }
    return summary, draws


def jackknife_table(
    result,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Portfolio SR after dropping each root (no renormalisation)."""

    daily = result.daily.set_index("date")["ret_gross"].loc[start:end]
    by_root = (
        result.by_root.pivot_table(
            index="date", columns="root", values="pnl_gross", aggfunc="sum"
        )
        .reindex(daily.index)
        .fillna(0.0)
        / result.config.capital
    )
    all_sr = c_daily.sharpe(daily)
    rows = [{"dropped_root": "ALL", "sr": all_sr, "delta": 0.0}]
    for root in by_root.columns:
        sr = c_daily.sharpe(daily - by_root[root])
        rows.append({"dropped_root": root, "sr": sr, "delta": sr - all_sr})
    return pd.DataFrame(rows).sort_values("delta")

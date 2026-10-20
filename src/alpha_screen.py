"""Per-root time-series IC with a joint day-block bootstrap (D-030).

All statistics are time series: each root's score is correlated only with that
root's own forward returns. The bootstrap resamples blocks of *dates* on the
common calendar, and every root (and every score column) uses the same
resampled dates. That keeps cross-root dependence, so the cross-root mean IC
has a valid standard error, and it makes model-vs-model differences paired.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .horizon import _block_indices, newey_west_t

PERIODS = {
    "train": ("1986-01-01", "2005-12-31"),
    "valid": ("2006-01-01", "2015-12-31"),
    "test": ("2016-01-01", "2026-12-31"),
}
BLOCKS = (1, 5, 10, 21, 42, 63, 126)


def slice_period(frame: pd.DataFrame, period: str) -> pd.DataFrame:
    """Rows of ``frame`` whose date lies in a named period (``full`` = all)."""

    if period == "full":
        return frame
    lo, hi = PERIODS[period]
    return frame.loc[frame["date"].between(lo, hi)]


def rank_matrices(frame: pd.DataFrame, cols: list[str], target: str, min_obs: int = 252) -> dict:
    """Date x root matrices of within-root ranks for each score and the target.

    Ranks are taken over the rows where both the score and the target are
    valid (the Spearman IC is then the Pearson correlation of the ranks).
    Roots with fewer than ``min_obs`` valid rows are left all-NaN.

    Returns:
        dict with ``dates``, ``roots`` and, per score column, a pair of
        arrays ``(x_rank, y_rank)`` of shape (n_dates, n_roots).
    """

    dates = pd.DatetimeIndex(sorted(frame["date"].unique()))
    roots = sorted(frame["root"].unique())
    out = {"dates": dates, "roots": roots}
    for col in cols:
        f = frame.loc[frame[col].notna() & frame[target].notna(), ["date", "root", col, target]]
        n = f.groupby("root")["date"].transform("size")
        f = f.loc[n >= min_obs]
        g = f.groupby("root")
        f = f.assign(rx=g[col].rank(), ry=g[target].rank())
        mats = [f.pivot(index="date", columns="root", values=v).reindex(index=dates, columns=roots) for v in ("rx", "ry")]
        out[col] = (mats[0].to_numpy(float), mats[1].to_numpy(float))
    return out


def _masked_corr(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Pearson correlation along the last axis, ignoring NaN pairs."""

    m = np.isfinite(x) & np.isfinite(y)
    n = m.sum(-1)
    x0, y0 = np.where(m, x, 0.0), np.where(m, y, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mx, my = x0.sum(-1) / n, y0.sum(-1) / n
        xc = np.where(m, x0 - mx[..., None], 0.0)
        yc = np.where(m, y0 - my[..., None], 0.0)
        r = (xc * yc).sum(-1) / np.sqrt((xc**2).sum(-1) * (yc**2).sum(-1))
    return np.where(n > 2, r, np.nan)


def joint_bootstrap(mats: dict, cols: list[str], block: int, n_boot: int = 1000, seed: int = 0) -> dict:
    """Per-root IC draws for every score under one shared day-block resample.

    Returns:
        dict col -> (point IC per root, draws of shape (n_boot, n_roots)).
    """

    rng = np.random.default_rng(seed)
    idx = _block_indices(len(mats["dates"]), block, n_boot, rng)
    out = {}
    for col in cols:
        x, y = mats[col]
        point = _masked_corr(x.T, y.T)
        draws = np.stack([_masked_corr(x[idx, j], y[idx, j]) for j in range(x.shape[1])], axis=1)
        out[col] = (point, draws)
    return out


def _p_two_sided(draws: np.ndarray) -> np.ndarray:
    """Two-sided bootstrap p = 2 min(P(d <= 0), P(d >= 0)) per column."""

    ok = np.isfinite(draws)
    le = np.where(ok, draws <= 0, False).sum(0) / ok.sum(0).clip(1)
    ge = np.where(ok, draws >= 0, False).sum(0) / ok.sum(0).clip(1)
    return np.minimum(1.0, 2 * np.minimum(le, ge))


def ic_table(mats: dict, boot: dict, col: str) -> pd.DataFrame:
    """Per-root and cross-root (``ALL``) IC with bootstrap SE, CI and p-value."""

    point, draws = boot[col]
    mean_draws = np.nanmean(draws, axis=1)[:, None]
    allp = np.array([np.nanmean(point)])
    d = np.concatenate([draws, mean_draws], axis=1)
    lo, hi = np.nanquantile(d, [0.025, 0.975], axis=0)
    out = pd.DataFrame({
        "root": list(mats["roots"]) + ["ALL"],
        "ic": np.concatenate([point, allp]),
        "boot_mean": np.nanmean(d, axis=0),
        "se": np.nanstd(d, axis=0, ddof=1),
        "ci_lo": lo, "ci_hi": hi,
        "p_value": _p_two_sided(d),
    })
    out.insert(0, "score", col)
    return out.loc[out["ic"].notna()].reset_index(drop=True)


def block_sensitivity(frame: pd.DataFrame, cols: list[str], target: str,
                      blocks=BLOCKS, n_boot: int = 1000, seed: int = 0) -> pd.DataFrame:
    """IC, bootstrap mean and SE for every score, root and block length."""

    mats = rank_matrices(frame, cols, target)
    rows = []
    for b in blocks:
        boot = joint_bootstrap(mats, cols, b, n_boot, seed)
        rows += [ic_table(mats, boot, c).assign(block=b) for c in cols]
    return pd.concat(rows, ignore_index=True)


def choose_block(sens: pd.DataFrame, tol: float = 0.10) -> int:
    """Smallest block whose cross-root SE is within ``tol`` of the largest block's.

    Uses the median over scores of the ``ALL`` row SE, i.e. the point where
    the SE curve reaches its plateau.
    """

    se = sens.loc[sens["root"].eq("ALL")].groupby("block")["se"].median()
    ok = se.index[se >= (1 - tol) * se.iloc[-1]]
    return int(ok.min())


def screen(tables: pd.DataFrame, alpha: float = 0.05, frac: float = 0.5,
           fallback_min: int = 3, sign_frac: float = 2 / 3) -> pd.DataFrame:
    """Pre-registered factor screen (D-030).

    Primary rule: a score passes if it is significant (p < ``alpha``) with the
    sign of its cross-root mean IC on at least ``frac`` of roots. If fewer
    than ``fallback_min`` scores pass, scores whose cross-root mean-IC 95% CI
    excludes zero and whose sign is shared by >= ``sign_frac`` of roots also
    pass (``rule = "fallback"``).
    """

    rows = []
    for col, t in tables.groupby("score", sort=False):
        allr, per = t.loc[t["root"].eq("ALL")].iloc[0], t.loc[t["root"].ne("ALL")]
        sign = np.sign(allr["ic"])
        n_sig = int(((per["p_value"] < alpha) & (np.sign(per["ic"]) == sign)).sum())
        rows.append(dict(
            score=col, mean_ic=allr["ic"], se=allr["se"], ci_lo=allr["ci_lo"], ci_hi=allr["ci_hi"],
            p_all=allr["p_value"], n_roots=len(per), n_sig=n_sig,
            frac_sig=n_sig / len(per), frac_sign=(np.sign(per["ic"]) == sign).mean(),
        ))
    out = pd.DataFrame(rows)
    out["primary"] = out["frac_sig"] >= frac
    ci_ok = (out["ci_lo"] > 0) | (out["ci_hi"] < 0)
    out["fallback"] = ci_ok & (out["frac_sign"] >= sign_frac)
    use_fb = out["primary"].sum() < fallback_min
    out["selected"] = out["primary"] | (out["fallback"] if use_fb else False)
    out["rule"] = np.where(out["primary"], "primary", np.where(out["selected"], "fallback", ""))
    return out


def horizon_ic(frame: pd.DataFrame, cols: list[str], targets: list[str], block: int,
               n_boot: int = 500, seed: int = 0) -> pd.DataFrame:
    """Cross-root mean IC (with bootstrap CI) of every score at every horizon."""

    rows = []
    for tgt in targets:
        mats = rank_matrices(frame, cols, tgt)
        boot = joint_bootstrap(mats, cols, block, n_boot, seed)
        for c in cols:
            t = ic_table(mats, boot, c)
            rows.append(t.loc[t["root"].eq("ALL")].assign(target=tgt))
    return pd.concat(rows, ignore_index=True).drop(columns="root")


def yearly_ic(frame: pd.DataFrame, score: str, target: str, min_obs: int = 60) -> pd.DataFrame:
    """Spearman IC of ``score`` with ``target`` per root and calendar year."""

    f = frame.dropna(subset=[score, target]).assign(year=lambda d: d["date"].dt.year)
    g = f.groupby(["root", "year"])
    ic = g.apply(lambda d: d[score].corr(d[target], method="spearman") if len(d) >= min_obs else np.nan,
                 include_groups=False)
    return ic.rename("ic").reset_index()

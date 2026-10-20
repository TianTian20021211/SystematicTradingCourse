"""Dynamic Nelson–Siegel with a Kalman filter (D-016 item 10, extension).

State: beta_t = beta_{t-1} + eta_t (random walk; the filter shrinks each day's
fit toward yesterday's betas). Observation: F_t = X_t(lam_t) beta_t + eps_t on
the eligible contracts of the day (3 or 4; missing rows simply drop out).
Prices are in levels and drift over decades, so both noise covariances scale
with the previous day's mean price s_{t-1}: R_t = r s² I, Q_t = q s² I.

(r, q) are chosen per root by the one-step predictive log likelihood on a
selection sample that ends before the evaluation sample (causal). Outputs are
the one-step-ahead curve forecast, a leave-one-contract-out forecast and the
filtered betas, for an A/B test against the daily OLS snapshot.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .nelson_siegel import CURV_PEAK, loadings

R_GRID = np.array([1e-6, 1e-5, 1e-4])
Q_RATIO_GRID = np.array([0.01, 0.1, 1.0, 10.0, 100.0, 1e3, 1e4])


def daily_observations(curve: pd.DataFrame, root: str, min_contracts: int = 3, max_contracts: int = 4) -> list[tuple]:
    """Per-day (date, F, M, lam) for one root, nearest ``max_contracts`` eligible contracts.

    lam follows the paper rule 1.7933 / mean maturity of the day's contracts.
    """

    c = curve.loc[(curve["root"] == root) & (curve["slot"] < max_contracts)].sort_values(["date", "slot"])
    out = []
    for date, g in c.groupby("date", sort=True):
        if len(g) < min_contracts:
            continue
        F, M = g["settle"].to_numpy(float), g["maturity"].to_numpy(float)
        out.append((date, F, M, CURV_PEAK / M.mean()))
    return out


def _init(F: np.ndarray, X: np.ndarray, G: int) -> tuple[np.ndarray, np.ndarray]:
    """Initial state: OLS on the first day, diffuse covariance."""

    beta = np.linalg.lstsq(X, F, rcond=None)[0]
    s2 = np.mean(np.abs(F)) ** 2
    return np.tile(beta, (G, 1)), np.tile(np.eye(3) * s2, (G, 1, 1))


def run_filter(obs: list[tuple], r: np.ndarray, q: np.ndarray, loo: bool = False) -> dict:
    """Kalman filter for G parameter pairs at once (r, q arrays of length G).

    Returns:
        dict of arrays over days: ``loglik`` (days, G), ``sse_pred``, ``sst``,
        ``press_loo`` (days, G; NaN unless 4 contracts and ``loo``), and for
        G == 1 the prior/posterior betas ``beta_prior``, ``beta_post`` (days, 3).
    """

    G, T = len(r), len(obs)
    out = {k: np.full((T, G), np.nan) for k in ("loglik", "sse_pred", "press_loo")}
    out["sst"] = np.full(T, np.nan)
    out["beta_prior"], out["beta_post"] = np.full((T, 3), np.nan), np.full((T, 3), np.nan)
    _d, F0, M0, lam0 = obs[0]
    beta, P = _init(F0, loadings(M0[None, :], np.array([lam0]))[0], G)
    s_prev = np.mean(np.abs(F0))
    for t, (_date, F, M, lam) in enumerate(obs):
        X = loadings(M[None, :], np.array([lam]))[0]
        n, s2 = len(F), s_prev ** 2
        P = P + (q * s2)[:, None, None] * np.eye(3)
        if G == 1:
            out["beta_prior"][t] = beta[0]
        pred = beta @ X.T
        v = F[None, :] - pred
        S = X[None] @ P @ X.T[None] + (r * s2)[:, None, None] * np.eye(n)
        Sinv = np.linalg.inv(S)
        out["sse_pred"][t] = (v**2).sum(axis=1)
        out["sst"][t] = ((F - F.mean()) ** 2).sum()
        _sign, logdet = np.linalg.slogdet(S)
        out["loglik"][t] = -0.5 * (logdet + np.einsum("gi,gij,gj->g", v, Sinv, v) + n * np.log(2 * np.pi))
        if loo and n == 4:
            out["press_loo"][t] = _loo_press(beta, P, X, F, r * s2)
        K = P @ X.T[None] @ Sinv
        beta = beta + np.einsum("gij,gj->gi", K, v)
        P = P - K @ X[None] @ P
        if G == 1:
            out["beta_post"][t] = beta[0]
        s_prev = np.mean(np.abs(F))
    return out


def _loo_press(beta, P, X, F, rvar) -> np.ndarray:
    """Leave-one-contract-out PRESS: update the prior on 3 contracts, predict the 4th."""

    press = np.zeros(len(beta))
    for k in range(len(F)):
        keep = [j for j in range(len(F)) if j != k]
        Xk, Fk = X[keep], F[keep]
        S = Xk[None] @ P @ Xk.T[None] + rvar[:, None, None] * np.eye(len(keep))
        K = P @ Xk.T[None] @ np.linalg.inv(S)
        b = beta + np.einsum("gij,gj->gi", K, Fk[None, :] - beta @ Xk.T)
        press += (F[k] - b @ X[k]) ** 2
    return press


def select_params(obs: list[tuple], select_end: str) -> tuple[float, float]:
    """(r, q) maximising the one-step log likelihood on days up to ``select_end``."""

    rr, qq = np.meshgrid(R_GRID, Q_RATIO_GRID, indexing="ij")
    r, q = rr.ravel(), (rr * qq).ravel()
    res = run_filter(obs, r, q)
    dates = np.array([o[0] for o in obs])
    mask = dates <= np.datetime64(pd.Timestamp(select_end))
    ll = np.nansum(res["loglik"][mask], axis=0)
    best = int(np.nanargmax(ll))
    return float(r[best]), float(q[best])


def kalman_panel(curve: pd.DataFrame, roots: list[str] | None = None, select_end: str = "2005-12-31") -> pd.DataFrame:
    """Kalman DNS per root-day with causal (r, q) selection.

    Returns:
        ``date, root, n_obs, r, q, bL, bS, bC`` (filtered betas),
        ``r2_pred_kf`` (one-step-ahead R² of the curve forecast from
        beta_{t|t-1}) and ``loo_kf`` (leave-one-contract-out R², 4-contract
        days only).
    """

    frames = []
    for root in roots or sorted(curve["root"].unique()):
        obs = daily_observations(curve, root)
        if len(obs) < 300:
            continue
        r, q = select_params(obs, select_end)
        res = run_filter(obs, np.array([r]), np.array([q]), loo=True)
        sst = res["sst"]
        with np.errstate(divide="ignore", invalid="ignore"):
            frames.append(pd.DataFrame({
                "date": [o[0] for o in obs], "root": root, "n_obs": [len(o[1]) for o in obs], "r": r, "q": q,
                "bL": res["beta_post"][:, 0], "bS": res["beta_post"][:, 1], "bC": res["beta_post"][:, 2],
                "r2_pred_kf": np.where(sst > 0, 1 - res["sse_pred"][:, 0] / sst, np.nan),
                "loo_kf": np.where(sst > 0, 1 - res["press_loo"][:, 0] / sst, np.nan),
            }))
    return pd.concat(frames, ignore_index=True)


def ols_one_step(fits: pd.DataFrame, wide: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    """One-step-ahead R² of the OLS snapshot: yesterday's betas on today's curve.

    Defined when the root was fitted on its previous trading day; today's
    maturities and lambda are used for the loadings (as for the Kalman forecast).
    """

    from .nelson_siegel import _arrays, _previous_trading_day

    f = fits[["date", "root", "bL", "bS", "bC", "lam"]].merge(wide, on=["date", "root"])
    f = f.merge(_previous_trading_day(curve), on=["root", "date"], how="left").sort_values(["root", "date"])
    prev = f.groupby("root")[["date", "bL", "bS", "bC"]].shift()
    ok = prev["date"].eq(f["prev_day"]).to_numpy()
    F, M = _arrays(f)
    X = loadings(M, f["lam"].to_numpy(float))
    pred = np.einsum("bij,bj->bi", X, prev[["bL", "bS", "bC"]].to_numpy(float))
    sst = ((F - F.mean(axis=1, keepdims=True)) ** 2).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        r2 = np.where(ok & (sst > 0), 1 - ((F - pred) ** 2).sum(axis=1) / sst, np.nan)
    return f[["date", "root"]].assign(r2_pred_ols=r2).reset_index(drop=True)


def kalman_signal_sig(kf: pd.DataFrame, sig_ols: pd.DataFrame) -> pd.DataFrame:
    """Replace the OLS beta changes in ``sig_ols`` with Kalman filtered changes.

    The traded contracts (1st/4th of four eligible) are unchanged, so the S
    strategy can be compared one-for-one; changes are between consecutive
    filtered days of the same root.
    """

    k = kf.sort_values(["root", "date"]).copy()
    k["dbS_kf"] = k.groupby("root")["bS"].diff()
    k["dbC_kf"] = k.groupby("root")["bC"].diff()
    out = sig_ols.merge(k[["date", "root", "dbS_kf", "dbC_kf"]], on=["date", "root"], how="left")
    return out.assign(dbS=out["dbS_kf"], dbC=out["dbC_kf"]).drop(columns=["dbS_kf", "dbC_kf"])


def build_kalman_strategy(ols_strategy: dict, kf: pd.DataFrame, marks_: pd.DataFrame, min_adv: float = 100.0) -> dict:
    """S-strategy pair/signal tables using Kalman beta changes on the OLS contract set.

    Same traded contracts, liquidity flag and explicit flats as
    ``nelson_siegel.build_slope_strategy``; only the signal differs.
    """

    from . import nelson_siegel as ns
    from . import sizing

    sig = kalman_signal_sig(kf, ols_strategy["sig"])
    pairs, signal = ns.slope_pairs(sig, ols_strategy["curve"])
    pairs = sizing.attach_leg_liquidity(pairs, marks_)
    pairs["liquid"] = pairs[["adv_near", "adv_far"]].min(axis=1).ge(min_adv)
    signal = signal.assign(target=signal["target"].where(pairs["liquid"].to_numpy(), 0.0))
    return dict(curve=ols_strategy["curve"], sig=sig, pairs=pairs, signal=signal)


def ab_table(kf: pd.DataFrame, ols_pred: pd.DataFrame, quality: pd.DataFrame, start: str = "2006-01-01") -> pd.DataFrame:
    """Paired daily fit metrics for the Kalman vs OLS A/B test (days where both exist)."""

    ab = kf.merge(ols_pred, on=["date", "root"]).merge(quality[["date", "root", "loo_LSC"]], on=["date", "root"])
    ab = ab.loc[ab["date"] >= start].copy()
    ab["gain_pred"] = ab["r2_pred_kf"] - ab["r2_pred_ols"]
    ab["gain_loo"] = ab["loo_kf"] - ab["loo_LSC"]
    return ab

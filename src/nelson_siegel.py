"""Nelson–Siegel curve fits and signals for idea E (D-016).

Bianchi, Fan, Miffre & Zhang (2023) fit, each day and per commodity,

    F_t(M) = bL + bS * s(lam M) + bC * c(lam M),
    s(x) = (1 - e^-x) / x,   c(x) = s(x) - e^-x,

on the price levels of the nearest four contracts, with M in months, and
trade the sign of the one-day change in bS (slope spread 1st/4th) or bC
(butterfly 1st/2nd/4th). Here lambda is a hyperparameter chosen among causal
rules (``LAMBDA_RULES``); the paper's rule is ``"paper"``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MONTH_DAYS = 365.25 / 12
CURV_PEAK = 1.7933  # argmax_x of c(x)
LAMBDA_GRID = np.round(np.geomspace(0.05, 2.0, 16), 4)


def last_trading_days(contract_panel: pd.DataFrame) -> pd.Series:
    """Last trading day per (root, contract_code), ex ante by exchange calendar.

    Expired contracts: last appearance in the generic M1–M4 roll (Bloomberg
    rolls at expiry). Contracts still trading at the end of the extract
    (``is_censored``): delivery-month start plus the root's median historical
    offset between last trading day and delivery-month start.
    """

    c = contract_panel.drop_duplicates(["root", "contract_code"]).set_index(["root", "contract_code"])
    done = ~c["is_censored"].astype(bool)
    offset = (c["last_date"] - c["delivery_month_start"]).dt.days.where(done)
    med = offset.groupby(level="root").median()
    rule = c["delivery_month_start"] + pd.to_timedelta(c.index.get_level_values("root").map(med), unit="D")
    return c["last_date"].where(done, rule).rename("ltd")


def eligible_curve(contract_panel: pd.DataFrame, maturity: str = "ltd") -> pd.DataFrame:
    """Eligible contracts per root-day with maturities in months.

    Eligible: priced, not in the delivery month, and on or before the last
    trading day. ``maturity="ltd"`` measures time to the last trading day;
    ``"delivery"`` to the delivery-month start (robustness).

    Returns:
        ``date, root, contract_code, settle, maturity, slot`` with ``slot``
        0..n-1 ordered by maturity, and ``n_eligible`` per root-day.
    """

    cols = ["date", "root", "contract_code", "settle", "in_delivery_month", "delivery_month_start"]
    c = contract_panel[cols].copy()
    ltd = last_trading_days(contract_panel)
    c["ltd"] = ltd.reindex(pd.MultiIndex.from_frame(c[["root", "contract_code"]])).to_numpy()
    end = c["ltd"] if maturity == "ltd" else c["delivery_month_start"]
    c["maturity"] = (end - c["date"]).dt.days / MONTH_DAYS
    ok = c["settle"].notna() & ~c["in_delivery_month"].astype(bool) & (c["date"] <= c["ltd"]) & (c["maturity"] > 0)
    c = c.loc[ok].sort_values(["root", "date", "maturity"])
    c["slot"] = c.groupby(["root", "date"]).cumcount()
    c["n_eligible"] = c.groupby(["root", "date"])["slot"].transform("size")
    return c[["date", "root", "contract_code", "settle", "maturity", "slot", "n_eligible"]].reset_index(drop=True)


def wide_curve(curve: pd.DataFrame, n: int = 4) -> pd.DataFrame:
    """One row per root-day with exactly ``n`` eligible contracts.

    Columns ``F0..F{n-1}``, ``M0..``, ``C0..`` (price, maturity, contract
    code) ordered by maturity.
    """

    c = curve.loc[curve["n_eligible"].eq(n) & curve["slot"].lt(n)]
    w = c.pivot_table(index=["date", "root"], columns="slot",
                      values=["settle", "maturity"], aggfunc="first")
    codes = c.pivot(index=["date", "root"], columns="slot", values="contract_code")
    out = pd.DataFrame(index=w.index)
    for k in range(n):
        out[f"F{k}"] = w[("settle", k)]
        out[f"M{k}"] = w[("maturity", k)]
        out[f"C{k}"] = codes[k]
    return out.reset_index()


def loadings(maturity: np.ndarray, lam: np.ndarray) -> np.ndarray:
    """NS design matrix [1, s(lam M), c(lam M)], shape (..., n, 3)."""

    x = lam[..., None] * maturity
    s = (1.0 - np.exp(-x)) / x
    return np.stack([np.ones_like(x), s, s - np.exp(-x)], axis=-1)


def _ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Batched OLS via normal equations; returns (beta, ssr), NaN if singular."""

    xtx = np.einsum("bij,bik->bjk", X, X)
    xty = np.einsum("bij,bi->bj", X, y)
    ok = np.abs(np.linalg.det(xtx)) > 1e-12
    beta = np.full(xty.shape, np.nan)
    beta[ok] = np.linalg.solve(xtx[ok], xty[ok][..., None])[..., 0]
    resid = y - np.einsum("bij,bj->bi", X, beta)
    return beta, (resid**2).sum(axis=1)


def _arrays(wide: pd.DataFrame, n: int = 4) -> tuple[np.ndarray, np.ndarray]:
    F = wide[[f"F{k}" for k in range(n)]].to_numpy(float)
    M = wide[[f"M{k}" for k in range(n)]].to_numpy(float)
    return F, M


def fit_ns(wide: pd.DataFrame, lam: pd.Series) -> pd.DataFrame:
    """Daily NS fit for each root-day row of ``wide`` given lambda.

    Returns:
        ``date, root, lam, bL, bS, bC, r2, r2_ls, r2_lc`` where ``r2_ls`` /
        ``r2_lc`` are the R² of the level+slope / level+curvature sub-models
        (paper Table 3).
    """

    F, M = _arrays(wide)
    X = loadings(M, lam.to_numpy(float))
    sst = ((F - F.mean(axis=1, keepdims=True)) ** 2).sum(axis=1)
    out = wide[["date", "root"]].copy()
    out["lam"] = lam.to_numpy(float)
    beta, ssr = _ols(X, F)
    out[["bL", "bS", "bC"]] = beta
    for name, cols in (("r2", [0, 1, 2]), ("r2_ls", [0, 1]), ("r2_lc", [0, 2])):
        _b, s = _ols(X[..., cols], F) if name != "r2" else (beta, ssr)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[name] = np.where(sst > 0, 1.0 - s / sst, np.nan)
    return out


def _ssr_grid(wide: pd.DataFrame, grid: np.ndarray) -> np.ndarray:
    """SSR of the NS fit for every row and every grid lambda, shape (rows, grid)."""

    F, M = _arrays(wide)
    out = np.empty((len(wide), len(grid)))
    for j, lam in enumerate(grid):
        _b, ssr = _ols(loadings(M, np.full(len(wide), lam)), F)
        out[:, j] = ssr
    return out


def lambda_series(wide: pd.DataFrame, rule: str = "paper", window: int = 252,
                  grid: np.ndarray = LAMBDA_GRID) -> pd.Series:
    """Causal lambda per root-day.

    Rules:
        ``"paper"``: 1.7933 / mean maturity of the fitted contracts (paper fn. 4).
        ``"fixed_<m>"``: constant 1.7933 / m (curvature peak at m months).
        ``"rolling_ssr"``: per root, the grid lambda minimising the summed
        SSR over the previous ``window`` fitted days (t excluded); the paper
        rule until 63 past days exist.
    """

    _F, M = _arrays(wide)
    paper = pd.Series(CURV_PEAK / M.mean(axis=1), index=wide.index)
    if rule == "paper":
        return paper
    if rule.startswith("fixed_"):
        return pd.Series(CURV_PEAK / float(rule.split("_")[1]), index=wide.index)
    if rule == "rolling_ssr":
        ssr = pd.DataFrame(_ssr_grid(wide, grid), index=wide.index)
        order = wide.sort_values(["root", "date"]).index
        past = ssr.loc[order].groupby(wide.loc[order, "root"]).transform(
            lambda s: s.rolling(window, min_periods=63).sum().shift())
        best = pd.Series(grid[np.nanargmin(past.fillna(np.inf).to_numpy(), axis=1)], index=order)
        best[past.isna().all(axis=1)] = np.nan
        return best.reindex(wide.index).fillna(paper)
    raise ValueError(f"Unknown lambda rule: {rule!r}")


def _previous_trading_day(curve: pd.DataFrame) -> pd.DataFrame:
    """Each root's previous trading day (any eligible contract priced)."""

    d = curve[["root", "date"]].drop_duplicates().sort_values(["root", "date"])
    d["prev_day"] = d.groupby("root")["date"].shift()
    return d


def ns_signals(fits: pd.DataFrame, wide: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    """One-day changes in the NS betas and the slope benchmark, per root-day.

    A change is defined only when the root was also fitted on its previous
    trading day (no differencing across gaps from the four-contract rule).
    ``roll`` flags a change of the fitted contract set. ``dS`` is the
    paper's non-NS benchmark Δ(F¹ − F⁴), defined only without a roll.

    Returns:
        ``date, root, C0..C3, F0..F3, dbS, dbC, dS, roll`` plus ``bS, bC``.
    """

    cols = ["date", "root"] + [f"C{k}" for k in range(4)] + [f"F{k}" for k in range(4)]
    f = fits[["date", "root", "bS", "bC"]].merge(wide[cols], on=["date", "root"])
    f = f.merge(_previous_trading_day(curve), on=["root", "date"], how="left").sort_values(["root", "date"])
    prev = f.groupby("root").shift()
    consecutive = prev["date"].eq(f["prev_day"])
    f["roll"] = consecutive & (f[[f"C{k}" for k in range(4)]].to_numpy() != prev[[f"C{k}" for k in range(4)]].to_numpy()).any(axis=1)
    f["dbS"] = (f["bS"] - prev["bS"]).where(consecutive)
    f["dbC"] = (f["bC"] - prev["bC"]).where(consecutive)
    slope = f["F0"] - f["F3"]
    f["dS"] = (slope - (prev["F0"] - prev["F3"])).where(consecutive & ~f["roll"])
    return f.drop(columns="prev_day").reset_index(drop=True)


def slope_pairs(sig: pd.DataFrame, curve: pd.DataFrame, score: str = "dbS", drop_rolls: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pair panel (1st vs 4th fitted contract) and sign signal for the S strategy.

    Every root-day with eligible contracts gets a row; days without a valid
    signal carry ``target = 0`` (explicit flat, D-016 item 2).

    Returns:
        ``(pairs, signal)`` in the shapes expected by ``sizing.legs_from_signal``
        and ``horizon.forward_returns``.
    """

    days = curve[["date", "root"]].drop_duplicates()
    s = days.merge(sig, on=["date", "root"], how="left")
    pairs = s.rename(columns={"C0": "contract_near", "C3": "contract_far", "F0": "settle_near", "F3": "settle_far"})
    pairs = pairs[["date", "root", "contract_near", "contract_far", "settle_near", "settle_far"]]
    x = s[score].where(~s["roll"].fillna(False).astype(bool)) if drop_rolls else s[score]
    signal = s[["date", "root"]].assign(score=x, target=np.sign(x).fillna(0.0))
    return pairs.reset_index(drop=True), signal.reset_index(drop=True)


def butterfly_legs(sig: pd.DataFrame, curve: pd.DataFrame, budget: pd.Series | None = None) -> pd.DataFrame:
    """Leg targets for the C strategy: butterfly on the 1st, 2nd and 4th contracts.

    dbC > 0 -> short 1st, long 2nd twice, short 4th (paper); equal notional
    shares 1:2:1 across the legs (|w1| = |w4| = ½|w2|). Gross budget per root
    is 1/N over roots with a signal (5-day max N, as in ``sizing``) unless
    ``budget`` is given. Root-days without a signal get an explicit flat row.
    """

    from . import sizing

    days = curve[["date", "root"]].drop_duplicates()
    s = days.merge(sig, on=["date", "root"], how="left")
    target = np.sign(s["dbC"]).fillna(0.0)
    active = target.ne(0)
    if budget is None:
        budget = 1.0 / sizing._stable_total(active.astype(float), s["date"], 5)
    s = s.assign(target=target, budget=budget.where(active, 0.0))
    group = s["root"] + "_" + s["C0"].astype(str) + "_" + s["C1"].astype(str) + "_" + s["C3"].astype(str)
    valid = active & (s[["F0", "F1", "F3"]] > 0).all(axis=1)
    legs = []
    for slot, direction, share in ((0, -1.0, 1.0), (1, 1.0, 2.0), (3, -1.0, 1.0)):
        units = direction * s["target"] * share / s[f"F{slot}"]
        legs.append(s.loc[valid].assign(group_id=group[valid], contract=s.loc[valid, f"C{slot}"], units=units[valid]))
    out = pd.concat(legs, ignore_index=True)
    flat = s.loc[~valid].assign(group_id="flat", contract=np.nan, units=0.0, budget=0.0)
    cols = sizing.LEG_COLUMNS
    return pd.concat([out[cols], flat[cols]], ignore_index=True).sort_values(["date", "root"]).reset_index(drop=True)


PAPER_ROOTS = ["BO", "C", "CC", "CL", "CT", "FC", "GC", "HG", "HO", "JO", "KC",
               "LB", "LC", "LH", "O", "RR", "S", "SI", "SM", "W", "XB"]  # paper's 21 (no CO, NG, SB)
LAMBDA_RULES = ["paper", "fixed_2", "fixed_4", "fixed_6", "rolling_ssr"]


def coverage(curve: pd.DataFrame) -> pd.DataFrame:
    """Per root: trading days, days with four eligible contracts, and the share."""

    d = curve.drop_duplicates(["root", "date"]).groupby("root")["n_eligible"]
    out = pd.DataFrame({"days": d.size(), "days_4": d.apply(lambda s: int((s >= 4).sum()))})
    out["share_4"] = out["days_4"] / out["days"]
    return out.sort_values("share_4")


def fit_summary(fits: pd.DataFrame, sig: pd.DataFrame) -> pd.DataFrame:
    """Paper Table 3 analogue per root: beta means/SDs, AC(1) of beta changes, lambda, R²."""

    f = fits.merge(sig[["date", "root", "dbS", "dbC"]], on=["date", "root"], how="left")
    g = f.groupby("root")
    ac = lambda s: s.dropna().autocorr(1)
    out = pd.DataFrame({
        "bL_mean": g["bL"].mean(), "bS_mean": g["bS"].mean(), "bS_sd": g["bS"].std(),
        "bC_mean": g["bC"].mean(), "ac1_dbS": g["dbS"].apply(ac), "ac1_dbC": g["dbC"].apply(ac),
        "lam_mean": g["lam"].mean(), "r2": g["r2"].mean() * 100,
        "r2_ls": g["r2_ls"].mean() * 100, "r2_lc": g["r2_lc"].mean() * 100,
    })
    out.loc["ALL"] = out.mean()
    return out


def build_slope_strategy(contract_panel: pd.DataFrame, marks_: pd.DataFrame, rule: str = "paper",
                         score: str = "dbS", min_adv: float = 100.0, roots: list[str] | None = None) -> dict:
    """Fits, signals and the S-strategy pair/signal tables for one lambda rule.

    Illiquid pair-days (thinner leg lagged ADV < ``min_adv``) and root-days
    without a fit get ``target = 0`` (explicit flat).

    Returns:
        dict with ``curve, wide, fits, sig, pairs, signal``.
    """

    from . import sizing

    cp = contract_panel if roots is None else contract_panel.loc[contract_panel["root"].isin(roots)]
    curve = eligible_curve(cp)
    wide = wide_curve(curve)
    fits = fit_ns(wide, lambda_series(wide, rule))
    sig = ns_signals(fits, wide, curve)
    pairs, signal = slope_pairs(sig, curve, score=score)
    pairs = sizing.attach_leg_liquidity(pairs, marks_)
    pairs["liquid"] = pairs[["adv_near", "adv_far"]].min(axis=1).ge(min_adv)
    signal = signal.assign(target=signal["target"].where(pairs["liquid"].to_numpy(), 0.0))
    return dict(curve=curve, wide=wide, fits=fits, sig=sig, pairs=pairs, signal=signal)


MODELS = {"L": [0], "LS": [0, 1], "LC": [0, 2], "LSC": [0, 1, 2]}


def _loo_press(X: np.ndarray, F: np.ndarray) -> np.ndarray:
    """Leave-one-contract-out prediction SSE (PRESS) per row.

    Each of the n contracts is predicted from a fit on the other n-1; NaN if
    a fold is singular (e.g. 3 parameters cannot be fitted on 2 points).
    """

    n = F.shape[1]
    press = np.zeros(len(F))
    for k in range(n):
        keep = [j for j in range(n) if j != k]
        beta, _ = _ols(X[:, keep, :], F[:, keep])
        press += (F[:, k] - np.einsum("bj,bj->b", X[:, k, :], beta)) ** 2
    return press


def fit_quality(wide: pd.DataFrame, lam: pd.Series) -> pd.DataFrame:
    """In-sample, adjusted and leave-one-out R² of nested NS models per root-day.

    Models: L (level only), LS, LC, LSC (full). With n = 4 contracts and p
    slope regressors, adjusted R² = 1 - (1 - R²)(n - 1)/(n - p - 1); the
    level-only model has R² = adjusted R² = 0 by construction. The LOO
    ("predictive") R² is 1 - PRESS / SST.

    Returns:
        ``date, root`` plus ``r2_<m>``, ``adj_<m>``, ``loo_<m>`` for each model.
    """

    F, M = _arrays(wide)
    X = loadings(M, lam.to_numpy(float))
    n = F.shape[1]
    sst = ((F - F.mean(axis=1, keepdims=True)) ** 2).sum(axis=1)
    out = wide[["date", "root"]].copy()
    with np.errstate(divide="ignore", invalid="ignore"):
        for name, cols in MODELS.items():
            _b, ssr = _ols(X[..., cols], F)
            r2 = np.where(sst > 0, 1.0 - ssr / sst, np.nan)
            p = len(cols) - 1
            out[f"r2_{name}"] = r2
            out[f"adj_{name}"] = 1.0 - (1.0 - r2) * (n - 1) / (n - p - 1)
            out[f"loo_{name}"] = np.where(sst > 0, 1.0 - _loo_press(X[..., cols], F) / sst, np.nan)
    return out

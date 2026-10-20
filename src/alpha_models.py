"""Pooled forecast models that combine the screened alpha factors (D-030).

Every model is fitted on all roots jointly (pooled panel). Features are the
causally scaled ``z_*`` factors (missing -> 0, the neutral value); the target
is a vol-scaled forward spread return ``y_fwd_*``. Hyper-parameters are fixed
or chosen from at most two values: tuning is deliberately not the focus.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge
from xgboost import XGBRegressor

from . import alpha_screen as S

# Ordered from simplest to most complex (ties in model selection go left).
MODEL_ZOO = {
    "ols": lambda: LinearRegression(),
    "ridge_1e3": lambda: Ridge(alpha=1e3),
    "ridge_1e5": lambda: Ridge(alpha=1e5),
    "lasso_1e-3": lambda: Lasso(alpha=1e-3),
    "lasso_1e-2": lambda: Lasso(alpha=1e-2),
    "enet": lambda: ElasticNet(alpha=1e-2, l1_ratio=0.5),
    "rf": lambda: RandomForestRegressor(
        n_estimators=200, max_depth=6, min_samples_leaf=500, max_features=0.5,
        n_jobs=-1, random_state=0),
    "xgb": lambda: XGBRegressor(
        n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, n_jobs=-1, random_state=0, verbosity=0),
}


def design(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Feature matrix of ``z_<feature>`` columns with missing values set to 0."""

    return frame[[f"z_{f}" for f in features]].fillna(0.0).to_numpy(float)


def fit_predict(panel: pd.DataFrame, features: list[str], target: str, model: str,
                fit_periods: tuple[str, ...]) -> np.ndarray:
    """Fit one model on the usable rows of ``fit_periods``; predict every row.

    Args:
        panel: Factor panel (``alpha_factors.build_factor_panel``).
        features: Raw factor names (scaled ``z_*`` columns are used).
        target: Raw target name, e.g. ``fwd_1_6``; ``y_<target>`` is fitted.
        model: Key of ``MODEL_ZOO``.
        fit_periods: Period names from ``alpha_screen.PERIODS``.

    Returns:
        Predictions aligned with ``panel`` rows.
    """

    fit = pd.concat([S.slice_period(panel, p) for p in fit_periods])
    fit = fit.loc[fit["usable"] & fit[f"y_{target}"].notna()]
    est = MODEL_ZOO[model]()
    est.fit(design(fit, features), fit[f"y_{target}"].to_numpy(float))
    return est.predict(design(panel, features))


def oos_predictions(panel: pd.DataFrame, features: list[str], target: str, model: str) -> pd.Series:
    """Train-fit predictions for train/validation, train+validation fit for test.

    The validation forecasts are genuinely out of sample (fitted on
    1986-2005); test forecasts come from a refit on 1986-2015.
    """

    p_train = fit_predict(panel, features, target, model, ("train",))
    p_full = fit_predict(panel, features, target, model, ("train", "valid"))
    is_test = panel["date"] >= S.PERIODS["test"][0]
    return pd.Series(np.where(is_test, p_full, p_train), index=panel.index, name=model)


def coefficients(panel: pd.DataFrame, features: list[str], target: str, model: str = "ols") -> pd.Series:
    """Coefficients (linear) or feature importances (trees) of a train fit."""

    fit = S.slice_period(panel, "train")
    fit = fit.loc[fit["usable"] & fit[f"y_{target}"].notna()]
    est = MODEL_ZOO[model]()
    est.fit(design(fit, features), fit[f"y_{target}"].to_numpy(float))
    vals = getattr(est, "coef_", None)
    if vals is None:
        vals = est.feature_importances_
    return pd.Series(vals, index=features, name=model)


def compare_models(frame: pd.DataFrame, models: list[str], target: str, block: int,
                   n_boot: int = 1000, seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Paired day-block bootstrap of the cross-root mean IC across models.

    Every model's forecast is ranked against the same realised ``target`` and
    all models share the resampled date blocks, so ``IC(m1) - IC(m2)`` is a
    paired difference.

    Args:
        frame: Usable rows of the evaluation period with one column per model.

    Returns:
        ``pairs`` (``m1, m2, diff, ci_lo, ci_hi, p_value, win``; ``win`` if the
        95% CI is above zero), ``summary`` (``model, mean_ic, se, wins``) and
        ``draws`` (model -> bootstrap cross-root mean IC).
    """

    mats = S.rank_matrices(frame, models, target)
    boot = S.joint_bootstrap(mats, models, block, n_boot, seed)
    draws = {m: np.nanmean(boot[m][1], axis=1) for m in models}
    point = {m: np.nanmean(boot[m][0]) for m in models}
    rows = []
    for m1 in models:
        for m2 in models:
            if m1 == m2:
                continue
            d = draws[m1] - draws[m2]
            lo, hi = np.quantile(d, [0.025, 0.975])
            p = min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean()))
            rows.append(dict(m1=m1, m2=m2, diff=point[m1] - point[m2], ci_lo=lo, ci_hi=hi, p_value=p, win=lo > 0))
    pairs = pd.DataFrame(rows)
    summary = pd.DataFrame({
        "model": models,
        "mean_ic": [point[m] for m in models],
        "se": [draws[m].std(ddof=1) for m in models],
        "wins": [int(pairs.loc[pairs["m1"].eq(m), "win"].sum()) for m in models],
    })
    return pairs, summary, draws


def select_model(summary: pd.DataFrame) -> str:
    """Most pairwise wins; ties go to the simpler model (``MODEL_ZOO`` order)."""

    order = {m: i for i, m in enumerate(MODEL_ZOO)}
    s = summary.assign(order=summary["model"].map(order))
    return s.sort_values(["wins", "order"], ascending=[False, True]).iloc[0]["model"]

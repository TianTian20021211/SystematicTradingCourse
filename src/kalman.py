"""Kalman-filter hedge ratio for the continuous calendar-spread legs.

The model follows the paper's dynamic linear model:

    near_index_t = beta_0,t + beta_1,t * far_index_t + eps_t
    beta_t = beta_{t-1} + w_t

where ``h_t = beta_1,t`` is the hedge ratio. The filter is causal: the
estimate at t uses observations through t.

Variance estimation is a tractable approximation to the paper's daily MLE:
every ``reestimate_every`` sessions, the observation variance is the residual
variance of an OLS fit on the trailing ``window`` observations, and the
process-to-observation variance ratio ``q`` is selected from a grid by the
Kalman-filter log likelihood on the same window. The chosen ``V`` and ``q``
are then held for the next block. A default ``q`` is used during the warm-up.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ["date", "root", "near_index", "far_index"]


@dataclass(frozen=True)
class KalmanHedgeParams:
    """Parameters for the rolling-likelihood Kalman hedge ratio."""

    window: int = 252
    reestimate_every: int = 60
    q_grid: tuple[float, ...] = (
        1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1
    )
    prior_mean: tuple[float, float] = (0.0, 1.0)
    prior_var: float = 1e6
    warmup_q: float = 1e-4


def _validate_params(params: KalmanHedgeParams) -> None:
    if not isinstance(params.window, int) or params.window < 10:
        raise ValueError("window must be an integer >= 10")
    if (
        not isinstance(params.reestimate_every, int)
        or params.reestimate_every <= 0
    ):
        raise ValueError("reestimate_every must be a positive integer")
    if not params.q_grid or any(
        not np.isfinite(q) or q <= 0 for q in params.q_grid
    ):
        raise ValueError("q_grid must contain positive finite values")
    if len(params.prior_mean) != 2 or not np.all(
        np.isfinite(params.prior_mean)
    ):
        raise ValueError("prior_mean must contain two finite values")
    if not np.isfinite(params.prior_var) or params.prior_var <= 0:
        raise ValueError("prior_var must be positive")
    if not np.isfinite(params.warmup_q) or params.warmup_q <= 0:
        raise ValueError("warmup_q must be positive")


def _ols_residual_variance(y: np.ndarray, x: np.ndarray) -> float:
    """Residual variance of y = a + h*x on the window."""

    if len(y) < 3:
        return np.nan
    var_x = float(np.var(x, ddof=1))
    if not np.isfinite(var_x) or var_x <= 0:
        return np.nan
    covariance = float(np.cov(y, x, ddof=1)[0, 1])
    slope = covariance / var_x
    intercept = float(np.mean(y) - slope * np.mean(x))
    residual = y - intercept - slope * x
    variance = float(np.var(residual, ddof=2))
    if not np.isfinite(variance) or variance <= 0:
        variance = float(np.var(y, ddof=1))
    if not np.isfinite(variance) or variance <= 0:
        return np.nan
    return variance


def _kalman_run(
    y: np.ndarray,
    x: np.ndarray,
    observation_var: float,
    q: float,
    prior_mean: tuple[float, float],
    prior_var: float,
) -> tuple[np.ndarray, np.ndarray, float, np.ndarray, np.ndarray]:
    """Run a two-state Kalman filter.

    Returns filtered h, filtered intercept, log likelihood, final state mean,
    and final state covariance.
    """

    beta = np.asarray(prior_mean, dtype=float).copy()
    covariance = np.eye(2) * prior_var
    process = np.eye(2) * q * observation_var
    h_values = np.full(len(y), np.nan)
    intercept_values = np.full(len(y), np.nan)
    log_likelihood = 0.0

    for index in range(len(y)):
        if not np.isfinite(y[index]) or not np.isfinite(x[index]):
            covariance = covariance + process
            continue
        design = np.array([1.0, x[index]])
        predicted_mean = beta
        predicted_covariance = covariance + process
        innovation = y[index] - design @ predicted_mean
        innovation_var = float(design @ predicted_covariance @ design + observation_var)
        if not np.isfinite(innovation_var) or innovation_var <= 0:
            covariance = predicted_covariance
            continue
        gain = predicted_covariance @ design / innovation_var
        beta = predicted_mean + gain * innovation
        covariance = predicted_covariance - np.outer(gain, design @ predicted_covariance)
        covariance = (covariance + covariance.T) / 2.0
        h_values[index] = beta[1]
        intercept_values[index] = beta[0]
        log_likelihood += -0.5 * (
            np.log(2.0 * np.pi * innovation_var)
            + innovation * innovation / innovation_var
        )

    return h_values, intercept_values, float(log_likelihood), beta, covariance


def _choose_q(
    y: np.ndarray,
    x: np.ndarray,
    observation_var: float,
    params: KalmanHedgeParams,
) -> tuple[float, float]:
    """Grid-likelihood choice of q on the window."""

    best_q = params.warmup_q
    best_ll = -np.inf
    for q in params.q_grid:
        _, _, ll, _, _ = _kalman_run(
            y, x, observation_var, q, params.prior_mean, params.prior_var
        )
        if np.isfinite(ll) and ll > best_ll:
            best_ll = ll
            best_q = q
    return best_q, best_ll


def kalman_hedge_ratio(
    leg_prices: pd.DataFrame,
    params: KalmanHedgeParams = KalmanHedgeParams(),
) -> pd.DataFrame:
    """Estimate a time-varying hedge ratio with a rolling-likelihood filter.

    Input columns are ``date, root, near_index, far_index``. The output adds
    ``hedge_ratio``, ``spread_index = near_index - h_t * far_index``, and
    diagnostics. ``h_t`` is NaN during the initial ``window`` warm-up; a
    non-positive or non-finite h is invalid and the hedge index is NaN there.
    """

    _validate_params(params)
    missing = set(REQUIRED_COLUMNS).difference(leg_prices.columns)
    if missing:
        raise ValueError(f"leg_prices missing columns: {sorted(missing)}")

    panel = leg_prices.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    if panel.duplicated(["date", "root"]).any():
        raise ValueError("leg_prices contains duplicate (date, root) rows")

    label_columns = [c for c in ("commodity", "sector") if c in panel.columns]
    frames: list[pd.DataFrame] = []

    for root, group in panel.sort_values(["root", "date"]).groupby(
        "root", sort=False
    ):
        group = group.set_index("date").sort_index()
        y = group["near_index"].to_numpy(dtype=float)
        x = group["far_index"].to_numpy(dtype=float)
        n = len(y)
        if n == 0:
            continue

        h_values = np.full(n, np.nan)
        intercept_values = np.full(n, np.nan)
        observation_var = np.full(n, np.nan)
        q_values = np.full(n, np.nan)
        log_likelihood = np.full(n, np.nan)
        is_reestimate = np.zeros(n, dtype=bool)

        beta = np.asarray(params.prior_mean, dtype=float).copy()
        covariance = np.eye(2) * params.prior_var
        current_var = np.nan
        current_q = params.warmup_q
        current_ll = np.nan
        expanding_var = (
            pd.Series(y).expanding(min_periods=2).var(ddof=1).to_numpy()
        )

        for index in range(n):
            if (
                index >= params.window
                and (index - params.window) % params.reestimate_every == 0
            ):
                window_y = y[index - params.window:index]
                window_x = x[index - params.window:index]
                valid = np.isfinite(window_y) & np.isfinite(window_x)
                if valid.sum() >= max(10, params.window // 2):
                    window_y = window_y[valid]
                    window_x = window_x[valid]
                    candidate_var = _ols_residual_variance(window_y, window_x)
                    if np.isfinite(candidate_var) and candidate_var > 0:
                        current_var = candidate_var
                        current_q, current_ll = _choose_q(
                            window_y, window_x, current_var, params
                        )
                        is_reestimate[index] = True

            if not np.isfinite(current_var) or current_var <= 0:
                current_var = float(expanding_var[index])
                if not np.isfinite(current_var) or current_var <= 0:
                    current_var = 1.0

            process = np.eye(2) * current_q * current_var
            if np.isfinite(y[index]) and np.isfinite(x[index]):
                design = np.array([1.0, x[index]])
                predicted_mean = beta
                predicted_covariance = covariance + process
                innovation = y[index] - design @ predicted_mean
                innovation_var = float(
                    design @ predicted_covariance @ design + current_var
                )
                if np.isfinite(innovation_var) and innovation_var > 0:
                    gain = predicted_covariance @ design / innovation_var
                    beta = predicted_mean + gain * innovation
                    covariance = predicted_covariance - np.outer(
                        gain, design @ predicted_covariance
                    )
                    covariance = (covariance + covariance.T) / 2.0
                    h_values[index] = beta[1]
                    intercept_values[index] = beta[0]
            else:
                covariance = covariance + process

            observation_var[index] = current_var
            q_values[index] = current_q
            log_likelihood[index] = current_ll

        valid_h = (
            np.isfinite(h_values)
            & (h_values > 0)
            & (np.arange(n) >= params.window)
        )
        hedge_index = y - h_values * x
        hedge_index = np.where(valid_h, hedge_index, np.nan)
        pair_count = np.cumsum(np.isfinite(y) & np.isfinite(x))

        frame = pd.DataFrame(
            {
                "date": group.index,
                "root": root,
                **{column: group[column].iloc[0] for column in label_columns},
                "near_index": y,
                "far_index": x,
                "hedge_ratio": h_values,
                "spread_index": hedge_index,
                "hedge_ratio_valid": valid_h,
                "kalman_intercept": intercept_values,
                "kalman_observation_var": observation_var,
                "kalman_q": q_values,
                "kalman_loglik": log_likelihood,
                "kalman_is_reestimate": is_reestimate,
                "kalman_pair_count": pair_count,
            }
        )
        frames.append(frame)

    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["date", "root"]).reset_index(drop=True)

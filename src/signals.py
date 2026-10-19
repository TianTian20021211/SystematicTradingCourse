"""Signal construction for calendar-spread ideas."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import curve


@dataclass(frozen=True)
class CarryParams:
    """Parameters for the time-series carry signal."""

    signal: str = "dollar_sign"  # "dollar_sign" | "annualized"
    annualize_days: str = "delivery_month"  # "delivery_month" | "months"


def _delivery_days_between(panel: pd.DataFrame) -> pd.Series:
    """Calendar days between the near and far delivery-month starts."""

    near = pd.to_datetime(
        {
            "year": panel["delivery_year_near"].astype("Int64"),
            "month": panel["delivery_month_near"].astype("Int64"),
            "day": 1,
        }
    )
    far = pd.to_datetime(
        {
            "year": panel["delivery_year_far"].astype("Int64"),
            "month": panel["delivery_month_far"].astype("Int64"),
            "day": 1,
        }
    )
    return (far - near).dt.days


def carry_signal(
    pair_panel: pd.DataFrame,
    params: CarryParams = CarryParams(),
) -> pd.DataFrame:
    """Build the time-series carry signal for the main pair.

    Output columns are ``date``, ``root``, optional ``commodity`` / ``sector``,
    ``spread_dollar``, ``carry_ann``, ``score``, and ``target``. ``target`` is
    +1 for backwardation, -1 for contango, and 0 when the spread is missing or
    zero. The signal is row-wise: it never uses future rows or full-sample
    statistics.
    """

    required = [
        "date", "root", "settle_near", "settle_far",
        "delivery_year_near", "delivery_month_near",
        "delivery_year_far", "delivery_month_far",
    ]
    missing = [column for column in required if column not in pair_panel.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    out = pair_panel[["date", "root"]].copy()
    for column in ("commodity", "sector"):
        if column in pair_panel.columns:
            out[column] = pair_panel[column]

    near = pair_panel["settle_near"]
    far = pair_panel["settle_far"]
    spread = near - far

    if params.annualize_days == "delivery_month":
        days = _delivery_days_between(pair_panel)
    elif params.annualize_days == "months":
        days = pair_panel["months_between"] * 30.44
    else:
        raise ValueError(
            f"Unknown annualize_days: {params.annualize_days!r}"
        )

    carry = (near - far) / far * 365.0 / days
    carry = carry.where((near > 0) & (far > 0) & (days > 0))

    out["spread_dollar"] = spread
    out["carry_ann"] = carry

    if params.signal == "dollar_sign":
        score = spread
    elif params.signal == "annualized":
        score = carry
    else:
        raise ValueError(f"Unknown carry signal: {params.signal!r}")

    out["score"] = score
    out["target"] = np.sign(score).fillna(0.0).astype(float)
    out.loc[spread.isna(), "target"] = 0.0
    return out


@dataclass(frozen=True)
class MeanReversionParams:
    """Parameters for the weekly mean-reversion signal.

    The baseline evaluates the state machine only on the last trading day of
    each week. ``evaluation="daily"`` is deliberately not implemented yet: the
    current engine only supports weekly rebalancing.
    """

    window: int = 20
    entry_z: float = 2.0
    exit_z: float = 0.0
    min_obs_frac: float = 0.8
    evaluation: str = "weekly"


def _validate_mean_reversion_params(params: MeanReversionParams) -> None:
    if not isinstance(params.window, int) or params.window <= 1:
        raise ValueError("window must be an integer > 1")
    if not params.entry_z > 0:
        raise ValueError("entry_z must be positive")
    if not (0.0 <= params.exit_z < params.entry_z):
        raise ValueError("exit_z must satisfy 0 <= exit_z < entry_z")
    if not (0.0 < params.min_obs_frac <= 1.0):
        raise ValueError("min_obs_frac must satisfy 0 < min_obs_frac <= 1")
    if params.evaluation == "daily":
        raise NotImplementedError("daily evaluation is not supported yet")
    if params.evaluation != "weekly":
        raise ValueError(f"Unknown evaluation: {params.evaluation!r}")


def _state_path(
    z: np.ndarray,
    evaluation_mask: np.ndarray,
    params: MeanReversionParams,
) -> np.ndarray:
    """Run the long/short/flat hysteresis state machine.

    The state is updated only where ``evaluation_mask`` is True and ``z`` is
    finite. Between updates, and through NaN windows, the previous state is
    held. A flip is emitted as a direct +/-1 target on the same evaluation
    date; the engine trades four leg-units in one rebalance.
    """

    target = np.zeros(len(z), dtype=float)
    state = 0.0
    for index in range(len(z)):
        if not evaluation_mask[index] or np.isnan(z[index]):
            target[index] = state
            continue

        value = float(z[index])
        if state == 0.0:
            if value >= params.entry_z:
                state = -1.0
            elif value <= -params.entry_z:
                state = 1.0
        elif state > 0.0:
            if value >= params.entry_z:
                state = -1.0
            elif value >= params.exit_z:
                state = 0.0
        else:
            if value <= -params.entry_z:
                state = 1.0
            elif value <= -params.exit_z:
                state = 0.0
        target[index] = state
    return target


def mean_reversion_signal(
    spread_index: pd.DataFrame,
    params: MeanReversionParams = MeanReversionParams(),
    trading_days: pd.DatetimeIndex | None = None,
    pair_grid: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build a weekly mean-reversion target path from a continuous spread index.

    ``spread_index`` must contain ``date, root, spread_index`` (and optionally
    ``commodity, sector``). ``trading_days`` should be the engine's union
    calendar; weekly evaluation dates are the last trading day of each week on
    that calendar. ``pair_grid`` marks dates on which a tradable pair exists;
    targets are forced to zero elsewhere so downstream conditional-mean tests
    cannot count untradable rows.

    The output is a complete daily target path per root: ``target`` is held
    between evaluation dates, and ``state`` is the internal state before the
    ``has_pair`` filter. Extra columns are diagnostics.
    """

    _validate_mean_reversion_params(params)

    required = {"date", "root", "spread_index"}
    missing = required.difference(spread_index.columns)
    if missing:
        raise ValueError(f"spread_index missing columns: {sorted(missing)}")

    panel = spread_index.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    sorted_panel = panel.sort_values(["root", "date"])
    if sorted_panel.duplicated(["date", "root"]).any():
        raise ValueError("spread_index contains duplicate (date, root) rows")

    if trading_days is None:
        trading_days = curve.trading_calendar(panel)
    else:
        trading_days = pd.DatetimeIndex(sorted(pd.to_datetime(trading_days)))
        outside = ~sorted_panel["date"].isin(trading_days)
        if outside.any():
            raise ValueError(
                "spread_index has dates outside trading_days: "
                f"{int(outside.sum())} rows"
            )

    if pair_grid is None:
        pair_grid = sorted_panel[["date", "root"]].drop_duplicates()
    else:
        missing_grid = {"date", "root"}.difference(pair_grid.columns)
        if missing_grid:
            raise ValueError(f"pair_grid missing columns: {sorted(missing_grid)}")
        pair_grid = pair_grid[["date", "root"]].drop_duplicates()
        pair_grid["date"] = pd.to_datetime(pair_grid["date"])

    weekly_dates = curve.weekly_rebalance_dates(trading_days)
    min_periods = max(2, math.ceil(params.min_obs_frac * params.window))
    evaluation_mask = pd.Series(
        trading_days.isin(weekly_dates), index=trading_days
    )

    frames: list[pd.DataFrame] = []
    for root, group in sorted_panel.groupby("root", sort=False):
        series = (
            group.set_index("date")["spread_index"]
            .reindex(trading_days)
        )
        mean = series.rolling(params.window, min_periods=min_periods).mean()
        std = series.rolling(params.window, min_periods=min_periods).std(ddof=1)
        count = series.rolling(params.window, min_periods=1).count()
        z = ((series - mean) / std).where(std.gt(0))
        z_valid = series.notna() & count.ge(min_periods) & std.gt(0)

        state = _state_path(
            z.to_numpy(dtype=float),
            evaluation_mask.to_numpy(dtype=bool),
            params,
        )
        state_series = pd.Series(state, index=trading_days)

        root_pair_dates = pd.DatetimeIndex(
            pair_grid.loc[pair_grid["root"].eq(root), "date"].unique()
        )
        has_pair = trading_days.isin(root_pair_dates)
        target = state_series.where(has_pair, 0.0)

        evaluation_date = (
            pd.Series(trading_days, index=trading_days)
            .where(evaluation_mask)
            .ffill()
        )

        first = group.iloc[0]
        frame = pd.DataFrame(
            {
                "date": trading_days,
                "root": root,
                "commodity": first.get("commodity"),
                "sector": first.get("sector"),
                "spread_index": series.to_numpy(dtype=float),
                "score": z.to_numpy(dtype=float),
                "target": target.to_numpy(dtype=float),
                "state": state_series.to_numpy(dtype=float),
                "evaluation_date": evaluation_date.to_numpy(),
                "is_evaluation": evaluation_mask.to_numpy(dtype=bool),
                "z_valid": z_valid.to_numpy(dtype=bool),
                "window_count": count.to_numpy(dtype=int),
                "has_pair": has_pair,
            }
        )
        frames.append(frame)

    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["date", "root"]).reset_index(drop=True)

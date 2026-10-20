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
class CurveMomentumParams:
    """Parameters for the monthly within-curve momentum signal.

    The signal is mathematically basis-momentum: the difference between the
    trailing returns of the near and far rank slots. ``formation_months`` is
    measured in month-end observations; ``min_obs_frac`` is the minimum share
    of usable daily returns required inside a formation window.
    """

    formation_months: int = 12
    min_obs_frac: float = 0.80


def _validate_curve_momentum_params(params: CurveMomentumParams) -> None:
    if not isinstance(params.formation_months, int) or params.formation_months <= 0:
        raise ValueError("formation_months must be an integer > 0")
    if not (0.0 < params.min_obs_frac <= 1.0):
        raise ValueError("min_obs_frac must satisfy 0 < min_obs_frac <= 1")


def _rank_return_index(
    returns_panel: pd.DataFrame,
    trading_days: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Build roll-adjusted rank return indices and valid/bad observation counts.

    ``ret_rank`` is already roll-adjusted by ``panel.build_return_panel``. A
    missing return and a negative-price (or ``ret_rank <= -1``) day are treated
    as a zero step in the index so the level stays positive; the formation
    window that contains a bad day is invalidated later. Because a skipped step
    is a common factor for any two dates after it, ratios between dates on the
    same side of the break remain valid.
    """

    required = {"date", "root", "rank", "ret_rank"}
    missing = required.difference(returns_panel.columns)
    if missing:
        raise ValueError(f"returns_panel missing columns: {sorted(missing)}")

    panel = returns_panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    if "negative_price" not in panel.columns:
        panel["negative_price"] = False
    panel["negative_price"] = panel["negative_price"].fillna(False).astype(bool)

    if panel.duplicated(["date", "root", "rank"]).any():
        raise ValueError("returns_panel contains duplicate (date, root, rank) rows")
    outside = ~panel["date"].isin(trading_days)
    if outside.any():
        raise ValueError(
            f"returns_panel has dates outside trading_days: {int(outside.sum())} rows"
        )

    frames: list[pd.DataFrame] = []
    for (root, rank), group in panel.groupby(["root", "rank"], sort=False):
        series = group.set_index("date").sort_index()
        ret = series["ret_rank"].reindex(trading_days)
        bad = series["negative_price"].reindex(trading_days).fillna(False)
        bad = bad.astype(bool) | ret.le(-1.0)
        valid = ret.notna() & np.isfinite(ret) & ~bad
        step = (1.0 + ret).where(valid, 1.0)
        level = step.cumprod()

        frames.append(
            pd.DataFrame(
                {
                    "date": trading_days,
                    "root": root,
                    "rank": int(rank),
                    "rank_index": level.to_numpy(dtype=float),
                    "valid_cum": valid.cumsum().to_numpy(dtype=int),
                    "bad_cum": bad.cumsum().to_numpy(dtype=int),
                }
            )
        )

    return pd.concat(frames, ignore_index=True)


def curve_momentum_signal(
    pair_panel: pd.DataFrame,
    returns_panel: pd.DataFrame,
    params: CurveMomentumParams = CurveMomentumParams(),
    trading_days: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    """Build the monthly within-curve momentum (basis-momentum) target path.

    ``pair_panel`` supplies the traded main pair (``rank_near`` / ``rank_far``)
    on each date. ``returns_panel`` supplies ``ret_rank`` and ``negative_price``
    from ``panel.build_return_panel``. At each month-end the signal compares the
    trailing ``formation_months`` return of the two rank slots and goes long the
    stronger leg / short the weaker leg.

    The output is a complete daily target path per root. ``target`` is held
    between month-ends and is zero when the month-end score is missing or the
    pair is missing. ``score`` is reported on signal dates only.
    """

    _validate_curve_momentum_params(params)

    required = {"date", "root", "rank_near", "rank_far"}
    missing = required.difference(pair_panel.columns)
    if missing:
        raise ValueError(f"pair_panel missing columns: {sorted(missing)}")

    pair = pair_panel.copy()
    pair["date"] = pd.to_datetime(pair["date"])
    if pair.duplicated(["date", "root"]).any():
        raise ValueError("pair_panel contains duplicate (date, root) rows")
    pair["rank_near"] = pair["rank_near"].astype(int)
    pair["rank_far"] = pair["rank_far"].astype(int)

    if trading_days is None:
        dates = pd.Index(pair["date"]).append(
            pd.Index(pd.to_datetime(returns_panel["date"]))
        )
        trading_days = pd.DatetimeIndex(sorted(pd.to_datetime(dates).unique()))
    else:
        trading_days = pd.DatetimeIndex(sorted(pd.to_datetime(trading_days)))
        outside = ~pair["date"].isin(trading_days)
        if outside.any():
            raise ValueError(
                f"pair_panel has dates outside trading_days: {int(outside.sum())} rows"
            )

    index_panel = _rank_return_index(returns_panel, trading_days)

    # Use each root's own last pair date in a month, not the global union
    # month-end. A root can be closed on the union month-end (e.g. a US holiday
    # while another exchange trades); forcing that root flat would be wrong.
    root_month_ends = (
        pair.assign(period=pair["date"].dt.to_period("M"))
        .groupby(["root", "period"], sort=False)["date"]
        .max()
        .reset_index()
    )
    prior_map = {
        (row.root, row.period): row.date
        for row in root_month_ends.itertuples(index=False)
    }
    root_month_ends["prior_date"] = pd.to_datetime(
        [
            prior_map.get((root, period - params.formation_months))
            for root, period in zip(
                root_month_ends["root"], root_month_ends["period"]
            )
        ]
    )
    signal_dates = pair.merge(
        root_month_ends[["root", "date", "prior_date"]],
        on=["root", "date"],
        how="inner",
        validate="one_to_one",
    )
    root_month_end_dates = {
        root: pd.DatetimeIndex(group["date"].sort_values())
        for root, group in root_month_ends.groupby("root", sort=False)
    }

    def merge_leg(frame: pd.DataFrame, leg: str, date_col: str) -> pd.DataFrame:
        rank_col = f"rank_{leg}"
        labels = {
            "rank": rank_col,
            "rank_index": f"idx_{leg}_{date_col}",
            "valid_cum": f"valid_{leg}_{date_col}",
            "bad_cum": f"bad_{leg}_{date_col}",
        }
        merge_date = "date" if date_col == "t" else "prior_date"
        if date_col == "prior":
            labels["date"] = "prior_date"
        lookup = index_panel.rename(columns=labels)
        value_columns = [
            value for key, value in labels.items() if key not in ("rank", "date")
        ]
        return frame.merge(
            lookup[[merge_date, "root", rank_col] + value_columns],
            on=[merge_date, "root", rank_col],
            how="left",
            validate="many_to_one",
        )

    for leg in ("near", "far"):
        signal_dates = merge_leg(signal_dates, leg, "t")
        signal_dates = merge_leg(signal_dates, leg, "prior")

    positions = pd.Series(
        np.arange(len(trading_days), dtype=int), index=trading_days
    )
    date_positions = positions.reindex(signal_dates["date"].to_numpy())
    prior_positions = positions.reindex(signal_dates["prior_date"].to_numpy())
    expected = (
        date_positions.to_numpy(dtype=float)
        - prior_positions.to_numpy(dtype=float)
    )
    min_obs = np.ceil(params.min_obs_frac * expected - 1e-12)

    valid = pd.Series(expected > 0, index=signal_dates.index)
    for leg in ("near", "far"):
        valid = valid & signal_dates[f"idx_{leg}_t"].notna()
        valid = valid & signal_dates[f"idx_{leg}_prior"].notna()
        valid = valid & signal_dates[f"idx_{leg}_prior"].gt(0)
        valid = valid & (
            signal_dates[f"valid_{leg}_t"] - signal_dates[f"valid_{leg}_prior"]
            >= min_obs
        )
        valid = valid & (
            signal_dates[f"bad_{leg}_t"] - signal_dates[f"bad_{leg}_prior"] == 0
        )

    mom_near = (
        signal_dates["idx_near_t"] / signal_dates["idx_near_prior"] - 1.0
    ).where(valid)
    mom_far = (
        signal_dates["idx_far_t"] / signal_dates["idx_far_prior"] - 1.0
    ).where(valid)
    score = mom_near - mom_far
    target = np.sign(score).fillna(0.0).astype(float)
    target.loc[score.isna()] = 0.0

    signal_columns = ["date", "root", "rank_near", "rank_far"]
    for column in ("commodity", "sector"):
        if column in signal_dates.columns:
            signal_columns.append(column)
    signals = signal_dates[signal_columns].copy()
    signals["mom_near"] = mom_near.to_numpy()
    signals["mom_far"] = mom_far.to_numpy()
    signals["score"] = score.to_numpy()
    signals["target"] = target.to_numpy()
    signals["is_signal_date"] = True

    # Forward-fill each month-end target over the root's daily pair grid. A
    # month-end without a signal (missing score or no pair) forces flat for the
    # next month rather than carrying a stale target.
    frames: list[pd.DataFrame] = []
    for root, group in pair.groupby("root", sort=False):
        first = group["date"].min()
        last = group["date"].max()
        grid = trading_days[(trading_days >= first) & (trading_days <= last)]
        root_signals = signals.loc[signals["root"].eq(root)].set_index("date")
        month_end_dates = root_month_end_dates.get(root, pd.DatetimeIndex([]))
        month_end_dates = month_end_dates[
            (month_end_dates >= first) & (month_end_dates <= last)
        ]

        # A calendar month with no tradable pair gets an explicit zero target.
        # Do not carry the previous month's target through the gap; this is the
        # O 1996-03/04 and RR 1992-05 pattern.
        global_month_ends = pd.DatetimeIndex(
            [
                date
                for date in curve.monthly_rebalance_dates(trading_days)
                if first <= date <= last
            ]
        )
        present_periods = set(month_end_dates.to_period("M"))
        missing_month_ends = pd.DatetimeIndex(
            [
                date
                for date in global_month_ends
                if date.to_period("M") not in present_periods
            ]
        )
        evaluation_dates = month_end_dates.union(missing_month_ends).sort_values()

        target_at_signal = root_signals["target"].reindex(month_end_dates).fillna(0.0)
        if len(missing_month_ends):
            target_at_signal = pd.concat(
                [
                    target_at_signal,
                    pd.Series(0.0, index=missing_month_ends),
                ]
            ).sort_index()
        target_daily = target_at_signal.reindex(grid).ffill().fillna(0.0)

        score_at_signal = root_signals["score"].reindex(month_end_dates)
        score_daily = pd.Series(np.nan, index=grid, dtype=float)
        score_daily.loc[month_end_dates] = score_at_signal.to_numpy(dtype=float)

        first_row = group.iloc[0]
        frame = pd.DataFrame(
            {
                "date": grid,
                "root": root,
                "commodity": first_row.get("commodity"),
                "sector": first_row.get("sector"),
                "target": target_daily.to_numpy(dtype=float),
                "score": score_daily.to_numpy(dtype=float),
                "is_signal_date": grid.isin(evaluation_dates),
                "rank_near": root_signals["rank_near"].reindex(grid).to_numpy(dtype=float),
                "rank_far": root_signals["rank_far"].reindex(grid).to_numpy(dtype=float),
                "mom_near": root_signals["mom_near"].reindex(grid).to_numpy(dtype=float),
                "mom_far": root_signals["mom_far"].reindex(grid).to_numpy(dtype=float),
            }
        )
        frames.append(frame)

    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["date", "root"]).reset_index(drop=True)


@dataclass(frozen=True)
class MeanReversionParams:
    """Parameters for the mean-reversion signal.

    ``evaluation="weekly"`` updates the state machine only on the last trading
    day of each week; ``evaluation="daily"`` updates it on every trading day.
    The baseline research result uses weekly; the daily audit uses daily.
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
    if params.evaluation not in {"weekly", "daily"}:
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
    """Build a mean-reversion target path from a continuous spread index.

    ``spread_index`` must contain ``date, root, spread_index`` (and optionally
    ``commodity, sector``). ``trading_days`` should be the engine's union
    calendar; weekly evaluation dates are the last trading day of each week on
    that calendar, while daily evaluation uses every trading day. ``pair_grid``
    marks dates on which a tradable pair exists; targets are forced to zero
    elsewhere so downstream conditional-mean tests cannot count untradable
    rows.

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

    min_periods = max(2, math.ceil(params.min_obs_frac * params.window))
    if params.evaluation == "daily":
        evaluation_mask = pd.Series(True, index=trading_days)
    else:
        weekly_dates = curve.weekly_rebalance_dates(trading_days)
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

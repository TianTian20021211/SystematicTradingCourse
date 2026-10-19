"""Negative-result diagnostics for the A (carry) baseline.

These helpers are deliberately separate from ``src/backtest.py`` and
``src/metrics.py`` so the C work can proceed on another branch without
conflicts.

The main question is: where does A fail?
- side x sector x era raw conditional means and P&L contribution;
- K=5 vs K=10 ex-ante eligibility;
- cost sensitivity 0/5/10/20 bps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from . import backtest, metrics, panel, signals


ERA_BINS = [
    pd.Timestamp("1986-01-01"),
    pd.Timestamp("2000-01-01"),
    pd.Timestamp("2010-01-01"),
    pd.Timestamp("2027-01-01"),
]
ERA_LABELS = ["1986-1999", "2000-2009", "2010-2026"]


def load_result(prefix: str | Path) -> backtest.BacktestResult:
    """Load a saved BacktestResult from ``<prefix>_*.parquet`` files."""

    prefix = Path(prefix)
    return backtest.BacktestResult(
        positions=pd.read_parquet(prefix.with_name(prefix.name + "_positions.parquet")),
        daily_returns=pd.read_parquet(
            prefix.with_name(prefix.name + "_daily.parquet")
        ),
        portfolio_returns=pd.read_parquet(
            prefix.with_name(prefix.name + "_portfolio.parquet")
        ),
        trades=pd.read_parquet(prefix.with_name(prefix.name + "_trades.parquet")),
        config=backtest.BacktestConfig(),
    )


def _with_direction(result: backtest.BacktestResult) -> pd.DataFrame:
    """Attach the previous-close group direction to active daily returns.

    ``positions`` is end-of-day. A daily return on date t belongs to the
    position held at t-1 close, so the direction is merged from the previous
    trading day. ``group_id`` is ``root_contract_near_contract_far``.
    """

    positions = result.positions.copy()
    positions["near_contract"] = positions["group_id"].str.split("_").str[1]
    positions["direction"] = np.where(
        positions["contract"].eq(positions["near_contract"]),
        np.sign(positions["units"]),
        np.nan,
    )
    directions = (
        positions.dropna(subset=["direction"])
        .groupby(["date", "group_id"], sort=False)["direction"]
        .max()
        .reset_index()
    )

    dates = pd.DatetimeIndex(sorted(pd.to_datetime(result.portfolio_returns["date"]).unique()))
    prev_day = {dates[i]: dates[i - 1] for i in range(1, len(dates))}
    daily = result.daily_returns.copy()
    daily["prev_date"] = daily["date"].map(prev_day)
    daily = daily.merge(
        directions.rename(
            columns={"date": "prev_date", "direction": "direction_prev"}
        ),
        on=["prev_date", "group_id"],
        how="left",
    )
    return daily


def _side_sector_era_table(frame: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for keys, group in frame.groupby(by, sort=True, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        date_means = group.groupby("date")["raw_return"].mean()
        n_dates = len(date_means)
        t_stat = (
            float(date_means.mean() / (date_means.std(ddof=1) / np.sqrt(n_dates)))
            if n_dates > 1 and date_means.std(ddof=1) > 0
            else np.nan
        )
        row = dict(zip(by, keys))
        row.update(
            {
                "n_obs": int(len(group)),
                "n_dates": int(n_dates),
                "raw_mean": float(group["raw_return"].mean()),
                "t_stat": t_stat,
                "contribution": float(group["contribution"].sum()),
                "avg_n_active": float(group["n_active"].mean()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def side_sector_era(
    result: backtest.BacktestResult,
) -> pd.DataFrame:
    """Raw spread return and exact gross contribution by side/sector/era.

    ``raw_return = return_gross * direction`` recovers the spread return from
    the sign-following position return. ``contribution = return_gross / n_active``
    is additive: summing it over all cells equals the portfolio gross return.
    Costs are not allocated to cells.
    """

    daily = _with_direction(result)
    active = daily.loc[~daily["is_cost_row"]].copy()
    active = active.loc[active["direction_prev"].notna()]
    active["direction"] = active["direction_prev"].astype(float)
    active["side"] = np.where(active["direction"] > 0, "long", "short")
    active["raw_return"] = active["return_gross"] * active["direction"]
    active["era"] = pd.cut(
        active["date"], bins=ERA_BINS, labels=ERA_LABELS, right=False
    )

    counts = active.groupby("date").size().rename("n_active")
    active = active.merge(counts, left_on="date", right_index=True, how="left")
    active["contribution"] = active["return_gross"] / active["n_active"]

    cells = _side_sector_era_table(active, ["side", "sector", "era"])
    side = _side_sector_era_table(active, ["side"])
    return pd.concat(
        [cells.assign(level="cell"), side.assign(level="side")],
        ignore_index=True,
        sort=False,
    )


def _build_bt(
    rank: pd.DataFrame,
    k: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bt = panel.build_backtest_panel(rank, d=None, k=k)
    sig = signals.carry_signal(bt["spread"])
    targets = backtest.build_target_legs(sig, bt["spread"])
    contracts = sorted(
        set(bt["spread"]["contract_near"].dropna())
        | set(bt["spread"]["contract_far"].dropna())
    )
    marks = panel.build_contract_mark_state(
        bt["contract"], contracts=contracts
    )
    return bt, targets, marks


def eligibility_compare(
    rank: pd.DataFrame,
    k_values: Iterable[int] = (5, 10),
    results: dict[int, backtest.BacktestResult] | None = None,
) -> pd.DataFrame:
    """Compare A under ex-ante K=5 and K=10 eligibility.

    D=10 is intentionally excluded: ``last_trade_proxy`` is ex post.
    ``results`` can supply an already-computed result for a k to avoid reruns.
    """

    rows: list[dict[str, object]] = []
    for k in k_values:
        if results is not None and k in results:
            bt = panel.build_backtest_panel(rank, d=None, k=k)
            res = results[k]
        else:
            bt, targets, marks = _build_bt(rank, k)
            res = backtest.run_backtest(
                bt["spread"],
                bt["contract"],
                targets,
                backtest.BacktestConfig(),
                mark_state=marks,
            )
        summary = metrics.summarize(res).iloc[0].to_dict()
        side = side_sector_era(res)
        side_only = side.loc[side["level"] == "side"].set_index("side")
        mix = bt["spread"]["pair_rank_mix"].value_counts().to_dict()
        row = {
            "k": k,
            "pair_rows": int(len(bt["spread"])),
            "m1_m2": int(mix.get("M1-M2", 0)),
            "m2_m3": int(mix.get("M2-M3", 0)),
            "ann_return_gross": summary["ann_return_gross"],
            "ann_return_net": summary["ann_return_net"],
            "sharpe_gross": summary["sharpe_gross"],
            "sharpe_net": summary["sharpe_net"],
            "max_drawdown_net": summary["max_drawdown_net"],
            "long_raw_mean": float(side_only.loc["long", "raw_mean"])
            if "long" in side_only.index
            else np.nan,
            "short_raw_mean": float(side_only.loc["short", "raw_mean"])
            if "short" in side_only.index
            else np.nan,
            "long_t_stat": float(side_only.loc["long", "t_stat"])
            if "long" in side_only.index
            else np.nan,
            "short_t_stat": float(side_only.loc["short", "t_stat"])
            if "short" in side_only.index
            else np.nan,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def cost_sensitivity(
    result: backtest.BacktestResult,
    bps_values: Iterable[float] = (0.0, 5.0, 10.0, 20.0),
) -> pd.DataFrame:
    """Scale the 5 bps cost series linearly and recompute net metrics."""

    pr = result.portfolio_returns
    gross = pr["return_gross"].to_numpy(dtype=float)
    cost5 = pr["cost"].to_numpy(dtype=float)
    rows: list[dict[str, float]] = []
    for bps in bps_values:
        net = gross - cost5 * (bps / 5.0)
        n = len(net)
        cum = np.cumprod(1.0 + net)
        dd = cum / np.maximum.accumulate(cum) - 1.0
        vol = float(np.std(net, ddof=1) * np.sqrt(252.0)) if n > 1 else np.nan
        mean = float(np.mean(net))
        rows.append(
            {
                "cost_bps_per_leg": float(bps),
                "ann_return_net": float(cum[-1] ** (252.0 / n) - 1.0) if n else np.nan,
                "ann_vol_net": vol,
                "sharpe_net": mean / (vol / np.sqrt(252.0))
                if vol and vol > 0
                else np.nan,
                "max_drawdown_net": float(dd.min()),
            }
        )
    return pd.DataFrame(rows)

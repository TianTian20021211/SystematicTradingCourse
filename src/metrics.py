"""Summary metrics and signal diagnostics for the backtest framework."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .backtest import BacktestResult, _weekly_rebalance_dates


def _slice(result: BacktestResult, start: str | None, end: str | None) -> BacktestResult:
    pr = result.portfolio_returns
    dr = result.daily_returns
    tr = result.trades
    if start is not None:
        ts = pd.Timestamp(start)
        pr = pr.loc[pr["date"] >= ts]
        dr = dr.loc[dr["date"] >= ts]
        tr = tr.loc[tr["date"] >= ts]
    if end is not None:
        te = pd.Timestamp(end)
        pr = pr.loc[pr["date"] <= te]
        dr = dr.loc[dr["date"] <= te]
        tr = tr.loc[tr["date"] <= te]
    return BacktestResult(
        positions=result.positions,
        daily_returns=dr,
        portfolio_returns=pr,
        trades=tr,
        config=result.config,
    )


def summarize(
    result: BacktestResult,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """One-row summary of gross/net returns and risk.

    Returns are gross-notional, unlevered, daily, rf=0. No-position days enter
    as zero returns. ``turnover`` is one-way traded notional divided by average
    active gross notional and years.
    """

    sub = _slice(result, start, end)
    pr = sub.portfolio_returns
    if pr.empty:
        return pd.DataFrame()
    r_gross = pr["return_gross"].to_numpy(dtype=float)
    r_net = pr["return_net"].to_numpy(dtype=float)
    n = len(pr)
    years = n / 252.0
    cum_net = np.cumprod(1.0 + r_net)
    cum_gross = np.cumprod(1.0 + r_gross)
    dd = cum_net / np.maximum.accumulate(cum_net) - 1.0
    vol_gross = float(np.std(r_gross, ddof=1) * np.sqrt(252.0)) if n > 1 else np.nan
    vol_net = float(np.std(r_net, ddof=1) * np.sqrt(252.0)) if n > 1 else np.nan
    mean_gross = float(np.mean(r_gross))
    mean_net = float(np.mean(r_net))
    sharpe_gross = (
        mean_gross / (vol_gross / np.sqrt(252.0)) if vol_gross and vol_gross > 0 else np.nan
    )
    sharpe_net = (
        mean_net / (vol_net / np.sqrt(252.0)) if vol_net and vol_net > 0 else np.nan
    )
    ann_gross = float(cum_gross[-1] ** (252.0 / n) - 1.0) if n else np.nan
    ann_net = float(cum_net[-1] ** (252.0 / n) - 1.0) if n else np.nan

    dr = sub.daily_returns
    active = dr.loc[~dr["is_cost_row"]] if "is_cost_row" in dr.columns else dr
    avg_gross = float(active["gross_notional"].mean()) if not active.empty else np.nan
    avg_n = float(pr["N_t"].mean())
    traded = sub.trades.loc[
        sub.trades["units"].ne(0) & sub.trades["price"].notna()
    ].copy()
    traded_notional = float((traded["units"].abs() * traded["price"].abs()).sum())
    portfolio_gross = avg_gross * avg_n
    turnover = (
        traded_notional / 2.0 / (portfolio_gross * years)
        if portfolio_gross and portfolio_gross > 0 and years > 0
        else np.nan
    )

    active_mask = pr["N_t"].to_numpy() > 0
    hit_rate = (
        float(np.mean(r_net[active_mask] > 0)) if active_mask.any() else np.nan
    )
    row = {
        "start": pr["date"].min(),
        "end": pr["date"].max(),
        "n_days": n,
        "years": years,
        "ann_return_gross": ann_gross,
        "ann_return_net": ann_net,
        "ann_vol_gross": vol_gross,
        "ann_vol_net": vol_net,
        "sharpe_gross": sharpe_gross,
        "sharpe_net": sharpe_net,
        "max_drawdown_net": float(dd.min()),
        "hit_rate_net": hit_rate,
        "avg_N_t": float(pr["N_t"].mean()),
        "avg_net_exposure": float(pr["net_exposure"].mean()),
        "n_trades": int(len(traded)),
        "turnover": turnover,
    }
    return pd.DataFrame([row])


def sector_summary(result: BacktestResult) -> pd.DataFrame:
    """Gross return and risk by sector (no cost allocation)."""

    dr = result.daily_returns
    if dr.empty:
        return pd.DataFrame()
    active = dr.loc[~dr["is_cost_row"]].copy() if "is_cost_row" in dr.columns else dr
    active = active.loc[active["sector"].notna()]
    rows: list[dict[str, Any]] = []
    for sector, frame in active.groupby("sector", sort=True):
        # Equal-weight across roots within the sector, then daily mean.
        daily = frame.groupby("date")["return_gross"].mean()
        rows.append(
            {
                "sector": sector,
                "n_days": int(len(daily)),
                "ann_return_gross": float(
                    (1.0 + daily).prod() ** (252.0 / len(daily)) - 1.0
                )
                if len(daily)
                else np.nan,
                "ann_vol_gross": float(daily.std(ddof=1) * np.sqrt(252.0))
                if len(daily) > 1
                else np.nan,
                "sharpe_gross": float(
                    daily.mean() / daily.std(ddof=1) * np.sqrt(252.0)
                )
                if len(daily) > 1 and daily.std(ddof=1) > 0
                else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("sector").reset_index(drop=True)


def conditional_mean(
    result: BacktestResult,
    signal_panel: pd.DataFrame,
    bootstrap: int = 1000,
    seed: int = 7,
) -> pd.DataFrame:
    """Forward normalized return by signal sign.

    The signal at t is filled at t+1. Forward returns use the backtest's
    normalized group returns from the fill close to the next rebalance fill,
    so rolls are handled by the engine. The t-stat uses a date-level block
    bootstrap to account for cross-sectional correlation.
    """

    pr = result.portfolio_returns
    dr = result.daily_returns
    if pr.empty or dr.empty:
        return pd.DataFrame()
    trading_days = pd.DatetimeIndex(sorted(pd.to_datetime(pr["date"]).unique()))
    rebalance_dates = sorted(_weekly_rebalance_dates(trading_days))
    if not rebalance_dates:
        return pd.DataFrame()

    active = dr.loc[~dr["is_cost_row"]].copy() if "is_cost_row" in dr.columns else dr
    active = active.loc[active["gross_notional"].gt(0)]
    daily = (
        active.groupby(["date", "root"])["return_gross"]
        .sum()
        .unstack("root")
        .reindex(trading_days)
        .fillna(0.0)
    )
    cum = (1.0 + daily).cumprod()

    day_list = list(trading_days)
    next_day = {
        day_list[i]: day_list[i + 1] if i + 1 < len(day_list) else None
        for i in range(len(day_list))
    }
    next_rebalance = {
        d: rebalance_dates[i + 1] if i + 1 < len(rebalance_dates) else None
        for i, d in enumerate(rebalance_dates)
    }

    signals = signal_panel.loc[
        signal_panel["target"].isin([-1.0, 1.0])
        & signal_panel["date"].isin(rebalance_dates),
        ["date", "root", "target"],
    ]
    if signals.empty:
        return pd.DataFrame()

    obs: list[dict[str, Any]] = []
    for row in signals.itertuples():
        signal_date = pd.Timestamp(row.date)
        fill_date = next_day.get(signal_date)
        if fill_date is None or row.root not in cum.columns:
            continue
        reb = next_rebalance.get(signal_date)
        end_date = next_day.get(reb, day_list[-1]) if reb is not None else day_list[-1]
        if end_date is None:
            end_date = day_list[-1]
        fill_idx = int(trading_days.get_indexer([fill_date])[0])
        end_idx = int(trading_days.get_indexer([end_date])[0])
        if fill_idx < 0 or end_idx < 0 or end_idx <= fill_idx:
            continue
        base = float(cum.iloc[fill_idx][row.root])
        if base == 0.0 or np.isnan(base):
            continue
        forward = float(cum.iloc[end_idx][row.root] / base - 1.0)
        obs.append(
            {
                "signal_date": signal_date,
                "root": row.root,
                "target": float(row.target),
                "forward_return": forward,
            }
        )
    if not obs:
        return pd.DataFrame()
    obs_df = pd.DataFrame(obs)

    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for sign, label in ((1.0, "target_positive"), (-1.0, "target_negative")):
        frame = obs_df.loc[obs_df["target"] == sign]
        if frame.empty:
            rows.append(
                {
                    "group": label,
                    "n_obs": 0,
                    "n_dates": 0,
                    "mean": np.nan,
                    "boot_se": np.nan,
                    "t_stat": np.nan,
                    "raw_mean": np.nan,
                    "raw_t_stat": np.nan,
                }
            )
            continue
        mean = float(frame["forward_return"].mean())
        by_date = frame.groupby("signal_date")["forward_return"].agg(["sum", "count"])
        sums = by_date["sum"].to_numpy()
        counts = by_date["count"].to_numpy()
        n_dates = len(sums)
        idx = rng.integers(0, n_dates, size=(bootstrap, n_dates))
        boot_means = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
        se = float(np.std(boot_means, ddof=1)) if bootstrap > 1 else np.nan
        t_stat = mean / se if se and se > 0 else np.nan
        rows.append(
            {
                "group": label,
                "n_obs": int(len(frame)),
                "n_dates": int(n_dates),
                "mean": mean,
                "boot_se": se,
                "t_stat": t_stat,
                # The strategy return is sign * raw spread return. Multiplying
                # by the sign recovers the raw spread-return conditional mean.
                "raw_mean": mean * sign,
                "raw_t_stat": t_stat * sign if not np.isnan(t_stat) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def plot_result(
    result: BacktestResult,
    path: str | Path | None = None,
    title: str = "Carry baseline",
) -> Path | None:
    """Plot cumulative gross/net returns; save to ``path`` if given."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pr = result.portfolio_returns
    if pr.empty:
        return None
    cum_gross = (1.0 + pr["return_gross"]).cumprod()
    cum_net = (1.0 + pr["return_net"]).cumprod()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(pr["date"], cum_gross, label="gross")
    ax.plot(pr["date"], cum_net, label="net")
    ax.set_title(title)
    ax.set_ylabel("cumulative return index")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    if path is None:
        return None
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path

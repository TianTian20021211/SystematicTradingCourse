"""Contract-level marks for the holdings-based simulator.

One row per (root, contract_code, date) on which the contract has a row in the
contract panel. ``dprice`` is the settle change since the contract's previous
valid settle, so summing ``holdings x point_value x dprice`` is lossless across
missing days: a gap is realised on the next valid observation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def trading_calendar(contract_panel: pd.DataFrame) -> pd.DatetimeIndex:
    """Union trading calendar of all contracts (sorted, unique)."""

    return pd.DatetimeIndex(sorted(pd.to_datetime(contract_panel["date"]).unique()))


def _tradable(frame: pd.DataFrame) -> pd.Series:
    """A settle is tradable if present and not a carried-over stale print.

    A stale print is an unchanged settle with zero or missing volume (D-009).
    """

    no_volume = frame["volume"].fillna(0).eq(0)
    stale = frame["stale"].fillna(False).astype(bool) & no_volume
    return frame["settle"].notna() & ~stale


def build_marks(
    contract_panel: pd.DataFrame,
    specs: pd.DataFrame,
    adv_window: int = 20,
    vol_window: int = 60,
) -> pd.DataFrame:
    """Build contract marks with liquidity and volatility inputs for costs.

    Args:
        contract_panel: Tian's contract panel (``date, root, contract_code,
            settle, volume, stale``).
        specs: Output of ``specs.load_contract_specs``.
        adv_window: Trailing observations for average daily volume (contracts).
        vol_window: Trailing observations for daily return volatility.

    Returns:
        DataFrame with ``date, root, contract_code, settle, mark, dprice, ret,
        tradable, adv, sigma, point_value, tick_size``. ``adv`` and ``sigma``
        are lagged one day so they are known before a trade at that settle.
    """

    cols = ["date", "root", "contract_code", "settle", "volume", "stale"]
    m = contract_panel[cols].sort_values(["root", "contract_code", "date"]).copy()
    g = m.groupby(["root", "contract_code"], sort=False)
    m["mark"] = g["settle"].ffill()
    prev_mark = m.groupby(["root", "contract_code"], sort=False)["mark"].shift()
    m["dprice"] = (m["settle"] - prev_mark).where(m["settle"].notna(), 0.0).fillna(0.0)
    m["ret"] = (m["dprice"] / prev_mark).where(prev_mark > 0)
    m["tradable"] = _tradable(m)
    g = m.groupby(["root", "contract_code"], sort=False)
    m["adv"] = g["volume"].transform(
        lambda s: s.rolling(adv_window, min_periods=5).mean().shift()
    )
    m["sigma"] = g["ret"].transform(
        lambda s: s.rolling(vol_window, min_periods=10).std().shift()
    )
    m["point_value"] = m["root"].map(specs["point_value_usd"])
    m["tick_size"] = m["root"].map(specs["tick_size"])
    if m["point_value"].isna().any():
        missing = sorted(m.loc[m["point_value"].isna(), "root"].unique())
        raise ValueError(f"No contract specs for roots: {missing}")
    return m.drop(columns=["volume", "stale"]).reset_index(drop=True)

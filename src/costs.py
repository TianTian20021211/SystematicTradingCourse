"""Three-layer transaction cost model: half-spread, fees, market impact.

Sources and defaults are documented in ``docs/transaction_costs.md``:

- half-spread: bid-ask = 1 tick for liquid nearbys (Szakmary et al. 2010;
  Paschke et al. 2020; Wang, Garcia & Irwin 2014 find ~1.26 ticks in corn),
  widened for thin contracts with the volume elasticity -0.18 of Wang et al.;
  a listed calendar-spread order crosses the bid-ask once (Bianchi et al. 2023);
- fees: USD 1.5 per contract per side (Gao et al. 2018, used by Paschke et al.
  and Bianchi et al.), charged on every leg;
- impact: square-root law Y x sigma_daily x sqrt(Q / ADV) (Toth et al. 2011),
  Y = 0.5, charged only on the quantity above ``impact_free_contracts`` (the
  first lot fills at the touch; the square-root law describes metaorders and
  overstates impact for one-lot orders).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CostParams:
    """Cost model parameters (all per side)."""

    half_spread_ticks: float = 0.5
    liquidity_elasticity: float = 0.18
    adv_ref: float = 10_000.0
    max_spread_multiplier: float = 10.0
    execution: str = "spread"  # "spread" (listed spread order) | "legs"
    fee_per_contract: float = 1.5
    impact_y: float = 0.5
    impact_free_contracts: float = 1.0
    adv_floor: float = 1.0
    proportional_bps: float = 0.0


def paper_scenarios() -> dict[str, CostParams]:
    """Bianchi et al. (2023) cost scenarios TC1–TC3, per side.

    The paper charges 0.5 x round-trip TC per unit of turnover, i.e. per side:
    TC1 = USD 0.75 commission per contract; TC2 = 0.835 bp of notional
    (Locke & Venkatesh 1997); TC3 = TC1 plus 1/8 tick of price impact.
    Legs are costed individually and no market impact is charged.
    """

    base = dict(liquidity_elasticity=0.0, execution="legs", impact_y=0.0, half_spread_ticks=0.0, fee_per_contract=0.0)
    return {
        "TC1": CostParams(**{**base, "fee_per_contract": 0.75}),
        "TC2": CostParams(**{**base, "proportional_bps": 0.835}),
        "TC3": CostParams(**{**base, "fee_per_contract": 0.75, "half_spread_ticks": 0.125}),
    }


def half_spread_ticks(adv: pd.Series, p: CostParams) -> pd.Series:
    """Half-spread in ticks, widened for low trailing volume.

    ``0.5 x clip((adv_ref / adv) ** elasticity, 1, max_mult)``; a missing ADV
    gets the maximum multiplier.
    """

    ratio = (p.adv_ref / adv.clip(lower=p.adv_floor)) ** p.liquidity_elasticity
    mult = ratio.clip(lower=1.0, upper=p.max_spread_multiplier)
    return p.half_spread_ticks * mult.fillna(p.max_spread_multiplier)


def _spread_execution_factor(trades: pd.DataFrame) -> pd.Series:
    """Share of leg half-spreads paid when legs are matched into spread orders.

    Per root-date, buys B and sells S can be paired into min(B, S) spread
    orders that cross one bid-ask each; |B - S| is legged outright. The factor
    (min(B, S) + |B - S|) / (B + S) is 0.5 for a balanced pair trade.
    """

    qty = trades["dn"].abs()
    buys = qty.where(trades["dn"] > 0, 0.0).groupby([trades["date"], trades["root"]]).transform("sum")
    sells = qty.where(trades["dn"] < 0, 0.0).groupby([trades["date"], trades["root"]]).transform("sum")
    total = buys + sells
    return ((np.minimum(buys, sells) + (buys - sells).abs()) / total).where(total > 0, 1.0)


def trade_costs(trades: pd.DataFrame, p: CostParams) -> pd.DataFrame:
    """Attach per-trade USD costs for each layer.

    Args:
        trades: ``date, root, contract, dn, price, point_value, tick_size,
            adv, sigma`` (``dn`` = signed contracts traded).
        p: Cost parameters.

    Returns:
        ``trades`` with ``notional, participation, cost_half_spread, cost_fee,
        cost_impact``.
    """

    t = trades.copy()
    qty = t["dn"].abs()
    t["notional"] = qty * t["price"].abs() * t["point_value"]
    # Missing volume is unknown liquidity, not zero: impute the root median.
    t["adv_imputed"] = t["adv"].isna()
    adv = t["adv"].fillna(t.groupby("root")["adv"].transform("median"))
    spread_px = half_spread_ticks(adv, p) * t["tick_size"] * t["point_value"]
    factor = _spread_execution_factor(t) if p.execution == "spread" else 1.0
    t["cost_half_spread"] = qty * spread_px * factor
    t["cost_fee"] = qty * p.fee_per_contract + t["notional"] * p.proportional_bps / 1e4
    t["participation"] = qty / adv.clip(lower=p.adv_floor).fillna(p.adv_floor)
    sigma = t["sigma"].fillna(t.groupby("root")["sigma"].transform("median"))
    excess = (qty - p.impact_free_contracts).clip(lower=0.0) / qty.where(qty > 0)
    impact_rate = p.impact_y * sigma.fillna(0.0) * np.sqrt(t["participation"])
    t["cost_impact"] = (t["notional"] * excess.fillna(0.0) * impact_rate)
    return t

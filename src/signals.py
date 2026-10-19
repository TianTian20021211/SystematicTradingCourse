"""Signal construction for calendar-spread ideas."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


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

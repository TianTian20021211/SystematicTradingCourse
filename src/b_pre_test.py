"""Cheap B pre-test: rank adjacent spreads by carry within each curve.

B is not A. A uses the sign of the main pair spread over time. This pre-test
uses the *relative* carry of the three adjacent spreads (M1-M2, M2-M3, M3-M4)
within one commodity: long the highest-carry spread, short the lowest. It is a
minimal, pre-registered version of "buy the cheap point, sell the rich point".

The target table is leg-level and is passed directly to the existing engine.
The main pair from the K=5 panel supplies the group's pair key and validation;
the actual B legs may be other maturities, labelled ``extra``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import backtest, metrics, panel


def _month_start(year: pd.Series, month: pd.Series) -> pd.Series:
    return pd.to_datetime(
        {
            "year": year.astype("Int64"),
            "month": month.astype("Int64"),
            "day": 1,
        }
    )


def build_adjacent_carries(rank_panel: pd.DataFrame) -> pd.DataFrame:
    """Annualized carry for M1-M2, M2-M3, M3-M4 on every date/root."""

    columns = [
        "date", "root", "commodity", "sector", "rank", "contract_code",
        "settle", "delivery_year", "delivery_month",
    ]
    base = rank_panel[columns].copy()
    parts: list[pd.DataFrame] = []
    for near_rank in (1, 2, 3):
        near = base.loc[base["rank"].eq(near_rank)]
        far = base.loc[base["rank"].eq(near_rank + 1)]
        merged = near.merge(
            far, on=["date", "root"], suffixes=("_near", "_far"), how="inner"
        )
        calendar_cols = [
            "delivery_year_near", "delivery_month_near",
            "delivery_year_far", "delivery_month_far",
        ]
        merged = merged.loc[merged[calendar_cols].notna().all(axis=1)]
        days = (
            _month_start(merged["delivery_year_far"], merged["delivery_month_far"])
            - _month_start(merged["delivery_year_near"], merged["delivery_month_near"])
        ).dt.days
        spread = merged["settle_near"] - merged["settle_far"]
        carry = spread / merged["settle_far"] * 365.0 / days
        carry = carry.where(
            merged["settle_near"].gt(0)
            & merged["settle_far"].gt(0)
            & days.gt(0)
        )
        merged = merged.assign(
            rank_near=near_rank,
            rank_far=near_rank + 1,
            spread=spread,
            carry_ann=carry,
        )
        parts.append(
            merged[
                [
                    "date", "root", "commodity_near", "sector_near",
                    "rank_near", "rank_far", "contract_code_near",
                    "contract_code_far", "settle_near", "settle_far",
                    "spread", "carry_ann",
                ]
            ].rename(
                columns={"commodity_near": "commodity", "sector_near": "sector"}
            )
        )
    return pd.concat(parts, ignore_index=True)


def _legs(frame: pd.DataFrame, near_units: float, far_units: float) -> pd.DataFrame:
    near = frame[["date", "root", "contract_near"]].rename(
        columns={"contract_near": "contract"}
    )
    near["units"] = near_units
    far = frame[["date", "root", "contract_far"]].rename(
        columns={"contract_far": "contract"}
    )
    far["units"] = far_units
    return pd.concat([near, far], ignore_index=True)


def build_b_targets(
    rank_panel: pd.DataFrame,
    pair_panel: pd.DataFrame,
) -> pd.DataFrame:
    """Build leg-level B targets: long the highest adjacent carry, short the lowest.

    The K=5 main pair is included in every group with zero units if it is not
    one of the B legs, so the engine's pair validation still works. Groups with
    no nonzero legs are dropped.
    """

    adj = build_adjacent_carries(rank_panel)
    valid = (
        adj.loc[adj["carry_ann"].notna()]
        .sort_values(["date", "root", "rank_near"])
        .copy()
    )
    stats = (
        valid.groupby(["date", "root"])["carry_ann"]
        .agg(["max", "min", "count"])
        .reset_index()
    )
    stats = stats.loc[(stats["count"] >= 2) & (stats["max"].gt(stats["min"]))]
    if stats.empty:
        return pd.DataFrame()

    high = valid.merge(stats[["date", "root", "max"]], on=["date", "root"])
    high = high.loc[np.isclose(high["carry_ann"], high["max"])].drop_duplicates(
        ["date", "root"]
    )
    low = valid.merge(stats[["date", "root", "min"]], on=["date", "root"])
    low = low.loc[np.isclose(low["carry_ann"], low["min"])].drop_duplicates(
        ["date", "root"]
    )

    high = high.rename(
        columns={
            "contract_code_near": "contract_near",
            "contract_code_far": "contract_far",
        }
    )
    low = low.rename(
        columns={
            "contract_code_near": "contract_near",
            "contract_code_far": "contract_far",
        }
    )
    legs = pd.concat(
        [_legs(high, 1.0, -1.0), _legs(low, -1.0, 1.0)], ignore_index=True
    )
    legs = (
        legs.groupby(["date", "root", "contract"], as_index=False)["units"]
        .sum()
    )
    legs = legs.loc[legs["units"].ne(0)]

    main = pair_panel[
        ["date", "root", "commodity", "sector", "contract_near", "contract_far"]
    ].rename(
        columns={"contract_near": "main_near", "contract_far": "main_far"}
    )
    groups = main.merge(legs, on=["date", "root"], how="inner")
    if groups.empty:
        return pd.DataFrame()
    groups["group_id"] = (
        groups["root"].astype(str)
        + "_"
        + groups["main_near"].astype(str)
        + "_"
        + groups["main_far"].astype(str)
    )
    groups["leg"] = np.select(
        [
            groups["contract"].eq(groups["main_near"]),
            groups["contract"].eq(groups["main_far"]),
        ],
        ["near", "far"],
        default="extra",
    )

    main_rows = groups[
        ["date", "root", "commodity", "sector", "group_id", "main_near", "main_far"]
    ].drop_duplicates(["date", "root"])
    near = main_rows[["date", "root", "commodity", "sector", "group_id", "main_near"]]
    near = near.rename(columns={"main_near": "contract"})
    near["units"] = 0.0
    near["leg"] = "near"
    far = main_rows[["date", "root", "commodity", "sector", "group_id", "main_far"]]
    far = far.rename(columns={"main_far": "contract"})
    far["units"] = 0.0
    far["leg"] = "far"
    main_unit_rows = pd.concat([near, far], ignore_index=True)

    trade_rows = groups[
        ["date", "root", "commodity", "sector", "group_id", "contract", "units", "leg"]
    ].copy()
    all_rows = pd.concat([main_unit_rows, trade_rows], ignore_index=True)
    all_rows = (
        all_rows.groupby(
            ["date", "root", "commodity", "sector", "group_id", "contract", "leg"],
            as_index=False,
        )["units"]
        .sum()
    )
    group_abs = all_rows.groupby(["date", "root", "group_id"])["units"].transform(
        lambda values: values.abs().sum()
    )
    all_rows = all_rows.loc[group_abs.gt(0)]
    # Keep zero-unit main-pair rows for pair validation; drop other zero rows.
    all_rows = all_rows.loc[
        all_rows["leg"].isin(["near", "far"]) | all_rows["units"].ne(0)
    ]
    all_rows["target"] = 1.0
    return all_rows.sort_values(["date", "root", "group_id", "leg"]).reset_index(
        drop=True
    )


@dataclass
class BPretestResult:
    targets: pd.DataFrame
    full: backtest.BacktestResult
    test: backtest.BacktestResult
    summary: pd.DataFrame


def run_b_pretest(
    rank_panel: pd.DataFrame,
    config: backtest.BacktestConfig | None = None,
) -> BPretestResult:
    """Run the pre-registered B pre-test on full and test samples."""

    cfg = config or backtest.BacktestConfig()
    bt = panel.build_backtest_panel(rank_panel, d=None, k=5)
    targets = build_b_targets(rank_panel, bt["spread"])
    contracts = sorted(
        set(targets["contract"])
        | set(bt["spread"]["contract_near"].dropna())
        | set(bt["spread"]["contract_far"].dropna())
    )
    marks = panel.build_contract_mark_state(
        bt["contract"], contracts=contracts
    )
    full = backtest.run_backtest(
        bt["spread"], bt["contract"], targets, cfg, mark_state=marks
    )
    test_cfg = backtest.BacktestConfig(
        cost_bps_per_leg=cfg.cost_bps_per_leg,
        start_date="2016-01-01",
    )
    test = backtest.run_backtest(
        bt["spread"], bt["contract"], targets, test_cfg, mark_state=marks
    )
    summary = pd.concat(
        [
            metrics.summarize(full).assign(period="full"),
            metrics.summarize(full, end="2015-12-31").assign(period="train"),
            metrics.summarize(test).assign(period="test"),
        ],
        ignore_index=True,
    )
    return BPretestResult(targets=targets, full=full, test=test, summary=summary)


def should_skip_b(summary: pd.DataFrame, min_gross_sharpe: float = 0.2) -> bool:
    """Pre-registered decision rule: skip B unless it clears both hurdles."""

    full = summary.loc[summary["period"] == "full"].iloc[0]
    gross = float(full["sharpe_gross"])
    net = float(full["sharpe_net"])
    return bool(gross < min_gross_sharpe or net <= 0.0)

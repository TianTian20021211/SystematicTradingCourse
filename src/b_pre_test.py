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
                    "delivery_year_near", "delivery_month_near",
                    "delivery_year_far", "delivery_month_far",
                    "spread", "carry_ann",
                ]
            ].rename(
                columns={"commodity_near": "commodity", "sector_near": "sector"}
            )
        )
    out = pd.concat(parts, ignore_index=True)
    # Keep the raw-rank names for existing callers and add the pair-panel
    # names used by select_adjacent / build_b_targets.
    out["contract_near"] = out["contract_code_near"]
    out["contract_far"] = out["contract_code_far"]
    return out


def build_adjacent_carries_from_pairs(pairs: pd.DataFrame) -> pd.DataFrame:
    """Annualized carry from an already-built adjacent-pair panel.

    This is the eligible-universe counterpart of
    :func:`build_adjacent_carries`: the caller supplies the D=10 / liquidity
    filtered adjacent pairs, and this function only computes the carry.
    """

    required = [
        "date", "root", "rank_near", "contract_near", "contract_far",
        "settle_near", "settle_far", "delivery_year_near",
        "delivery_month_near", "delivery_year_far", "delivery_month_far",
    ]
    missing = set(required).difference(pairs.columns)
    if missing:
        raise ValueError(f"pairs missing columns: {sorted(missing)}")

    out = pairs[required].copy()
    calendar_cols = [
        "delivery_year_near", "delivery_month_near",
        "delivery_year_far", "delivery_month_far",
    ]
    out = out.loc[out[calendar_cols].notna().all(axis=1)].copy()
    days = (
        _month_start(out["delivery_year_far"], out["delivery_month_far"])
        - _month_start(out["delivery_year_near"], out["delivery_month_near"])
    ).dt.days
    spread = out["settle_near"] - out["settle_far"]
    out["carry_ann"] = (spread / out["settle_far"] * 365.0 / days).where(
        out["settle_near"].gt(0) & out["settle_far"].gt(0) & days.gt(0)
    )
    return out


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


def _valid_adjacent(adjacent: pd.DataFrame) -> pd.DataFrame:
    """Rows with at least two valid adjacent carries per date/root."""

    valid = adjacent.loc[adjacent["carry_ann"].notna()].copy()
    counts = valid.groupby(["date", "root"]).size().rename("count")
    valid = valid.merge(counts, on=["date", "root"], how="left")
    return valid.loc[valid["count"].ge(2)].copy()


def _pick_adjacent(valid: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Pick one adjacent pair per date/root under a selection rule."""

    if rule in {"carry_high", "carry_low"}:
        stats = (
            valid.groupby(["date", "root"])["carry_ann"]
            .agg(["max", "min"])
            .reset_index()
        )
        stats = stats.loc[stats["max"].gt(stats["min"])]
        if stats.empty:
            return valid.iloc[0:0]
        col = "max" if rule == "carry_high" else "min"
        picked = valid.merge(stats[["date", "root", col]], on=["date", "root"])
        picked = picked.loc[np.isclose(picked["carry_ann"], picked[col])]
        return (
            picked.sort_values(["date", "root", "rank_near"])
            .drop_duplicates(["date", "root"])
            .copy()
        )
    if rule in {"front", "back"}:
        ascending = [True, True, rule == "front"]
        return (
            valid.sort_values(["date", "root", "rank_near"], ascending=ascending)
            .groupby(["date", "root"], as_index=False)
            .head(1)
            .copy()
        )
    raise ValueError(f"Unknown adjacent selection rule: {rule!r}")


def select_adjacent(
    adjacent: pd.DataFrame,
    long_rule: str = "carry_high",
    short_rule: str = "carry_low",
) -> pd.DataFrame:
    """Choose the long and short adjacent spread for each date/root.

    ``carry_high``/``carry_low`` preserve the original B selection (including
    its near-tie handling); ``front``/``back`` pick the lowest/highest
    maturity adjacent pair and are used for the static maturity control.
    """

    valid = _valid_adjacent(adjacent)
    if valid.empty:
        return pd.DataFrame()
    long = _pick_adjacent(valid, long_rule).rename(
        columns={
            "rank_near": "rank_long",
            "contract_near": "long_near",
            "contract_far": "long_far",
            "carry_ann": "carry_long",
        }
    )
    short = _pick_adjacent(valid, short_rule).rename(
        columns={
            "rank_near": "rank_short",
            "contract_near": "short_near",
            "contract_far": "short_far",
            "carry_ann": "carry_short",
        }
    )
    out = long[
        ["date", "root", "rank_long", "long_near", "long_far", "carry_long"]
    ].merge(
        short[
            ["date", "root", "rank_short", "short_near", "short_far", "carry_short"]
        ],
        on=["date", "root"],
        how="inner",
    )
    out = out.loc[out["rank_long"].ne(out["rank_short"])]
    return out.reset_index(drop=True)


def build_b_targets(
    rank_panel: pd.DataFrame,
    pair_panel: pd.DataFrame,
    adjacent: pd.DataFrame | None = None,
    long_rule: str = "carry_high",
    short_rule: str = "carry_low",
) -> pd.DataFrame:
    """Build leg-level B targets: long one adjacent spread, short another.

    The default (``carry_high`` long / ``carry_low`` short) is the original
    B. ``adjacent`` lets the caller pass an eligible adjacent-carry panel;
    the default raw-rank panel preserves the original B. The K=5 main pair is
    included in every group with zero units if it is not one of the B legs,
    so the engine's pair validation still works. Groups with no nonzero legs
    are dropped.
    """

    adj = build_adjacent_carries(rank_panel) if adjacent is None else adjacent.copy()
    selection = select_adjacent(adj, long_rule, short_rule)
    if selection.empty:
        return pd.DataFrame()
    long = selection.rename(
        columns={"long_near": "contract_near", "long_far": "contract_far"}
    )
    short = selection.rename(
        columns={"short_near": "contract_near", "short_far": "contract_far"}
    )
    legs = pd.concat(
        [_legs(long, 1.0, -1.0), _legs(short, -1.0, 1.0)], ignore_index=True
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

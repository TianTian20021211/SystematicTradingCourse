"""QA assertions and summary tables for the panels."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, curve


class QAError(AssertionError):
    """Raised when a panel invariant fails."""


def assert_unique_contract_date(contract_panel: pd.DataFrame) -> None:
    duplicates = contract_panel.duplicated(["date", "root", "contract_code"])
    if duplicates.any():
        raise QAError(f"Duplicate contract-date rows: {int(duplicates.sum())}")


def assert_rank_monotonic(rank_panel: pd.DataFrame) -> None:
    present = rank_panel.dropna(subset=["expiry_id"]).sort_values(
        ["root", "date", "rank"]
    )
    diffs = present.groupby(["root", "date"], sort=False)["expiry_id"].diff()
    violations = int((diffs <= 0).sum())
    duplicates = int(present.duplicated(["root", "date", "expiry_id"]).sum())
    if violations or duplicates:
        raise QAError(
            f"Rank/expiry order violations={violations}, duplicate expiry={duplicates}"
        )


def assert_roll_sync(rank_panel: pd.DataFrame) -> dict[str, object]:
    summary = curve.validate_roll_queue(rank_panel)
    if summary["n_partial_rolls"] or summary["n_full_day_violations"]:
        raise QAError(
            "Roll queue violations: "
            f"partial={summary['n_partial_rolls']}, "
            f"full_day={summary['n_full_day_violations']}"
        )
    return summary


def assert_return_mapping(return_panel: pd.DataFrame, atol: float = 1e-10) -> None:
    mask = (
        return_panel["ret_rank"].notna()
        & return_panel["ret_contract"].notna()
        & return_panel["ret_naive"].notna()
        & ~return_panel["is_roll"]
        & return_panel["prev_contract_code"].eq(return_panel["contract_code"])
    )
    diff = (return_panel.loc[mask, "ret_rank"] - return_panel.loc[mask, "ret_naive"]).abs()
    if len(diff) and diff.max() > atol:
        raise QAError(f"Rank/naive return mismatch on non-roll days: {diff.max():.3e}")


def assert_contract_calendar(contract_panel: pd.DataFrame) -> None:
    if (contract_panel["days_to_last_trading"] < 0).any():
        raise QAError("Negative days_to_last_trading")
    if (contract_panel["days_to_delivery_start"].isna()).any():
        raise QAError("Missing delivery-month distance")


def assert_no_eligible_in_delivery_month(rank_panel: pd.DataFrame) -> None:
    bad = rank_panel["eligible"] & rank_panel["in_delivery_month"]
    if bad.any():
        raise QAError(f"Eligible rows inside delivery month: {int(bad.sum())}")


def coverage_summary(rank_panel: pd.DataFrame) -> pd.DataFrame:
    total_dates = rank_panel["date"].nunique()
    summary = (
        rank_panel.groupby(["root", "rank"], sort=True)
        .agg(first=("date", "min"), last=("date", "max"), n_valid=("settle", "count"))
        .reset_index()
    )
    summary["n_dates"] = total_dates
    summary["pct_missing"] = 1 - summary["n_valid"] / total_dates
    return summary


def missing_summary(rank_panel: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rank_panel.groupby("rank", sort=True)
        .agg(
            n=("settle", "size"),
            settle_missing=("settle", lambda values: int(values.isna().sum())),
            code_missing=("code_missing", "sum"),
            volume_missing=("volume_missing", "sum"),
            oi_missing=("oi_missing", "sum"),
        )
        .reset_index()
    )
    return summary


def stale_summary(rank_panel: pd.DataFrame) -> pd.DataFrame:
    return (
        rank_panel.groupby(["root", "rank"], sort=True)
        .agg(
            stale_pct=("stale", "mean"),
            max_stale_run=("stale_run", "max"),
        )
        .reset_index()
    )


def known_events_check(rank_panel: pd.DataFrame) -> dict[str, object]:
    event = config.NEGATIVE_PRICE_EVENT
    row = rank_panel.loc[
        rank_panel["root"].eq(event["root"])
        & rank_panel["date"].eq(pd.Timestamp(event["date"]))
        & rank_panel["rank"].eq(1)
    ]
    negative = rank_panel.loc[rank_panel["negative_price"]]
    return {
        "negative_rows": int(len(negative)),
        "cl_2020_04_20_present": bool(len(row) == 1),
        "cl_2020_04_20_settle": float(row["settle"].iloc[0]) if len(row) == 1 else None,
        "expected_settle": event["settle"],
        "matches_expected": bool(
            len(row) == 1 and np.isclose(row["settle"].iloc[0], event["settle"])
        ),
    }

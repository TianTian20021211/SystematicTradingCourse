"""Return-based backtest engine for calendar-spread signals.

The engine is deliberately small and transparent:

- signals are produced by ``src/signals.py`` and are stateless row-wise tables;
- ``build_target_legs`` expands a signal into leg-level targets;
- ``run_backtest`` is a daily event loop that owns execution lag, rolls,
  missing/stale marks, costs, and P&L.

It is a hybrid: the date layer is an event loop, while operations inside a date
are table-level (pandas) operations. Pure vectorisation is not used because
rolls, pending orders, and forced exits are path-dependent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from . import curve, panel


@dataclass(frozen=True)
class BacktestConfig:
    """Execution and accounting conventions."""

    cost_bps_per_leg: float = 5.0
    rebalance: str = "last_trading_day_of_week"
    execution_lag: int = 1
    missing_exit_sessions: int = 5
    return_denominator: str = "gross_notional"
    start_date: str | None = None
    end_date: str | None = None


@dataclass
class BacktestResult:
    """Tables produced by the engine."""

    positions: pd.DataFrame
    daily_returns: pd.DataFrame
    portfolio_returns: pd.DataFrame
    trades: pd.DataFrame
    config: BacktestConfig


def build_target_legs(
    signal_panel: pd.DataFrame,
    pair_panel: pd.DataFrame,
    config: BacktestConfig | None = None,
) -> pd.DataFrame:
    """Expand a signal panel into leg-level targets.

    ``signal_panel`` must contain ``date``, ``root``, and ``target``. An
    optional ``hedge_ratio`` column scales the far leg: far units are
    ``-target * hedge_ratio`` instead of ``-target``. Rows with a missing,
    non-finite, or non-positive hedge ratio are dropped. ``pair_panel``
    supplies ``contract_near`` / ``contract_far`` and the commodity/sector
    labels. The output has one row per leg:

    ``date, root, commodity, sector, group_id, contract, units, leg, target``
    and, when supplied, ``hedge_ratio``.

    A target of +1 means long the near leg and short the far leg; -1 is the
    reverse. ``group_id`` is stable for a fixed contract pair and changes when
    the pair rolls.
    """

    required = {"date", "root", "target"}
    missing = required.difference(signal_panel.columns)
    if missing:
        raise ValueError(f"signal_panel missing columns: {sorted(missing)}")
    if signal_panel.duplicated(["date", "root"]).any():
        raise ValueError("signal_panel contains duplicate (date, root) rows")

    has_hedge_ratio = "hedge_ratio" in signal_panel.columns
    signal_columns = ["date", "root", "target"]
    if has_hedge_ratio:
        signal_columns.append("hedge_ratio")

    pairs = pair_panel[
        ["date", "root", "commodity", "sector", "contract_near", "contract_far"]
    ].copy()
    merged = signal_panel[signal_columns].merge(
        pairs, on=["date", "root"], how="inner"
    )
    merged = merged.loc[
        merged["target"].notna()
        & merged["target"].ne(0)
        & merged["contract_near"].notna()
        & merged["contract_far"].notna()
    ].copy()
    if has_hedge_ratio:
        merged = merged.loc[
            np.isfinite(merged["hedge_ratio"])
            & merged["hedge_ratio"].gt(0)
        ].copy()
    if merged.empty:
        columns = [
            "date", "root", "commodity", "sector", "group_id",
            "contract", "units", "leg", "target",
        ]
        if has_hedge_ratio:
            columns.append("hedge_ratio")
        return pd.DataFrame(columns=columns)

    merged["group_id"] = (
        merged["root"].astype(str)
        + "_"
        + merged["contract_near"].astype(str)
        + "_"
        + merged["contract_far"].astype(str)
    )

    near = merged.assign(
        contract=merged["contract_near"],
        units=merged["target"].astype(float),
        leg="near",
    )
    far_units = -merged["target"].astype(float)
    if has_hedge_ratio:
        far_units = far_units * merged["hedge_ratio"].astype(float)
    far = merged.assign(
        contract=merged["contract_far"],
        units=far_units,
        leg="far",
    )
    out = pd.concat([near, far], ignore_index=True)
    output_columns = [
        "date", "root", "commodity", "sector", "group_id",
        "contract", "units", "leg", "target",
    ]
    if has_hedge_ratio:
        output_columns.append("hedge_ratio")
    return out[output_columns].sort_values(
        ["date", "root", "group_id", "leg"]
    ).reset_index(drop=True)


def _pair_lookup(pair_panel: pd.DataFrame) -> dict[tuple[Any, Any], tuple[Any, Any]]:
    """Map (date, root) to (contract_near, contract_far)."""

    pairs = pair_panel.loc[
        pair_panel["contract_near"].notna() & pair_panel["contract_far"].notna()
    ]
    return {
        (row.date, row.root): (row.contract_near, row.contract_far)
        for row in pairs.itertuples()
    }


class _MarkBook:
    """Per-contract last-valid marks and invalid-session counters.

    The optional ``state`` frame comes from
    ``src.panel.build_contract_mark_state`` and is authoritative when a row
    exists. Dates outside a contract's state range are treated as absent and
    increment the counter, while keeping the last valid mark.
    """

    def __init__(
        self,
        contract_panel: pd.DataFrame,
        state: pd.DataFrame | None = None,
    ) -> None:
        self.state: dict[tuple[Any, Any, Any], tuple[float, int, bool]] = {}
        if state is not None and not state.empty:
            for row in state.itertuples():
                self.state[(row.date, row.root, row.contract_code)] = (
                    float(row.settle_mark) if not pd.isna(row.settle_mark) else np.nan,
                    int(row.sessions_since_valid),
                    bool(row.is_valid),
                )
        prices = contract_panel[["date", "root", "contract_code", "settle"]]
        self.price: dict[tuple[Any, Any, Any], float] = {
            (row.date, row.root, row.contract_code): row.settle
            for row in prices.itertuples()
        }
        self.last: dict[tuple[Any, Any], float] = {}
        self.sessions: dict[tuple[Any, Any], int] = {}
        self.cache: dict[tuple[Any, Any, Any], tuple[float, int, bool]] = {}

    def get(self, date: Any, root: Any, contract: Any) -> tuple[float, int, bool]:
        key = (date, root, contract)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        state_row = self.state.get(key)
        if state_row is not None:
            mark, sessions, valid = state_row
            self.last[(root, contract)] = mark
            self.sessions[(root, contract)] = sessions
            self.cache[key] = (mark, sessions, valid)
            return self.cache[key]
        price = self.price.get(key)
        if price is not None and not pd.isna(price):
            self.last[(root, contract)] = float(price)
            self.sessions[(root, contract)] = 0
            self.cache[key] = (float(price), 0, True)
            return self.cache[key]
        sessions = self.sessions.get((root, contract), 0) + 1
        self.sessions[(root, contract)] = sessions
        mark = self.last.get((root, contract), np.nan)
        self.cache[key] = (mark, sessions, False)
        return self.cache[key]


class _Engine:
    def __init__(
        self,
        pair_panel: pd.DataFrame,
        contract_panel: pd.DataFrame,
        target_legs: pd.DataFrame,
        config: BacktestConfig,
        mark_state: pd.DataFrame | None,
    ) -> None:
        self.config = config
        self.pair_panel = pair_panel
        self.contract_panel = contract_panel
        self.target_legs = target_legs
        self.mark_state = mark_state
        self.pair_lookup = _pair_lookup(pair_panel)

        self.trading_days = pd.DatetimeIndex(
            sorted(pd.to_datetime(contract_panel["date"]).unique())
        )
        if config.start_date is not None:
            self.trading_days = self.trading_days[
                self.trading_days >= pd.Timestamp(config.start_date)
            ]
        if config.end_date is not None:
            self.trading_days = self.trading_days[
                self.trading_days <= pd.Timestamp(config.end_date)
            ]
        if config.rebalance == "last_trading_day_of_week":
            self.rebalance_dates = curve.weekly_rebalance_dates(self.trading_days)
        elif config.rebalance == "last_trading_day_of_month":
            self.rebalance_dates = curve.monthly_rebalance_dates(self.trading_days)
        else:
            raise ValueError(f"Unknown rebalance: {config.rebalance!r}")

        self._targets = self._index_targets(target_legs)
        contracts = set()
        for rows in self._targets.values():
            for row in rows:
                contracts.add(row["contract"])
        for frame in (pair_panel,):
            contracts.update(frame["contract_near"].dropna().astype(str))
            contracts.update(frame["contract_far"].dropna().astype(str))
        if mark_state is None or mark_state.empty:
            self.mark_state = panel.build_contract_mark_state(
                contract_panel, contracts=sorted(contracts)
            )
        else:
            self.mark_state = mark_state
        self.marks = _MarkBook(contract_panel, self.mark_state)

        self.positions: dict[tuple[Any, Any, Any], float] = {}
        self.position_meta: dict[tuple[Any, Any], dict[str, Any]] = {}
        self.prev_marks: dict[tuple[Any, Any], float] = {}
        self.pending: dict[Any, dict[str, Any]] = {}
        self.last_pair: dict[Any, tuple[Any, Any] | None] = {}
        self.force_flat: set[Any] = set()

        self.position_rows: list[dict[str, Any]] = []
        self.return_rows: list[dict[str, Any]] = []
        self.trade_rows: list[dict[str, Any]] = []
        self.portfolio_rows: list[dict[str, Any]] = []
        self._today_rows: list[dict[str, Any]] = []
        self._today_cost_total: float = 0.0

    def _append_return(self, row: dict[str, Any]) -> None:
        self.return_rows.append(row)
        self._today_rows.append(row)

    @staticmethod
    def _index_targets(
        target_legs: pd.DataFrame,
    ) -> dict[tuple[Any, Any], list[dict[str, Any]]]:
        out: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
        if target_legs.empty:
            return out
        for row in target_legs.itertuples():
            out.setdefault((row.date, row.root), []).append(
                {
                    "group_id": row.group_id,
                    "contract": row.contract,
                    "units": float(row.units),
                    "leg": row.leg,
                    "commodity": getattr(row, "commodity", None),
                    "sector": getattr(row, "sector", None),
                }
            )
        return out

    @staticmethod
    def _pending_from_rows(
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not rows:
            return {"group_id": None, "pair": None, "legs": {}}
        near = next((row for row in rows if row["leg"] == "near"), None)
        far = next((row for row in rows if row["leg"] == "far"), None)
        pair = None
        if near is not None and far is not None:
            pair = (near["contract"], far["contract"])
        return {
            "group_id": rows[0]["group_id"],
            "pair": pair,
            "legs": {row["contract"]: row["units"] for row in rows},
            "commodity": rows[0].get("commodity"),
            "sector": rows[0].get("sector"),
            "forced": False,
        }

    def _open_positions_for(self, root: Any) -> dict[Any, float]:
        return {
            contract: units
            for (r, _group, contract), units in self.positions.items()
            if r == root and units != 0
        }

    def _group_position(self, root: Any, group_id: Any) -> dict[Any, float]:
        return {
            contract: units
            for (r, g, contract), units in self.positions.items()
            if r == root and g == group_id and units != 0
        }

    def _mark_day(self, date: pd.Timestamp) -> None:
        """Mark existing positions from the previous close to today's close."""

        self.force_flat.clear()
        self._today_rows = []
        self._today_cost_total = 0.0
        if not self.positions:
            return
        groups: dict[tuple[Any, Any], dict[str, Any]] = {}
        for (root, group_id, contract), units in list(self.positions.items()):
            if units == 0:
                continue
            mark, sessions, valid = self.marks.get(date, root, contract)
            prev = self.prev_marks.get((root, contract), np.nan)
            key = (root, group_id)
            info = groups.setdefault(
                key,
                {
                    "root": root,
                    "group_id": group_id,
                    "commodity": self.position_meta.get(key, {}).get("commodity"),
                    "sector": self.position_meta.get(key, {}).get("sector"),
                    "pnl": 0.0,
                    "gross_prev": 0.0,
                    "gross_cur": 0.0,
                    "sign": 0.0,
                    "valid": True,
                    "sessions": 0,
                },
            )
            if not pd.isna(prev) and not pd.isna(mark):
                info["pnl"] += units * (mark - prev)
                info["gross_prev"] += abs(units * prev)
                info["gross_cur"] += abs(units * mark)
            info["sign"] += units
            info["valid"] = info["valid"] and valid
            info["sessions"] = max(info["sessions"], sessions)
            if sessions > self.config.missing_exit_sessions:
                self.force_flat.add(root)
            self.prev_marks[(root, contract)] = mark

        for (root, group_id), info in groups.items():
            gross = info["gross_prev"]
            ret = info["pnl"] / gross if gross > 0 else 0.0
            self._append_return(
                {
                    "date": date,
                    "root": root,
                    "commodity": info["commodity"],
                    "sector": info["sector"],
                    "group_id": group_id,
                    "return_gross": ret,
                    "return_net": ret,
                    "gross_notional": gross,
                    "cost": 0.0,
                    "is_cost_row": False,
                    "sessions_since_valid": info["sessions"],
                    "is_valid": info["valid"],
                }
            )

    def _execute_pending(self, date: pd.Timestamp) -> None:
        """Execute orders created on the previous trading day."""

        if not self.pending:
            return
        for root, order in list(self.pending.items()):
            current_pair = self.pair_lookup.get((date, root))
            order_pair = order.get("pair")
            if order_pair is not None and current_pair != order_pair:
                # The pair rolled or disappeared before the fill: cancel.
                self.trade_rows.append(
                    {
                        "date": date,
                        "root": root,
                        "group_id": order.get("group_id"),
                        "contract": None,
                        "units": 0.0,
                        "price": np.nan,
                        "reason": "pending_canceled",
                        "flag": "pair_changed_before_fill",
                    }
                )
                self.pending.pop(root, None)
                continue

            current_groups = sorted(
                {g for (r, g, _c) in self.positions if r == root}
            )
            current_group = current_groups[0] if len(current_groups) == 1 else None
            current = self._open_positions_for(root)
            desired = dict(order.get("legs") or {})
            if not desired:
                desired = {}

            # Block entries/increases when a desired leg is not valid.
            blocked = False
            for contract, units in desired.items():
                if units == 0:
                    continue
                mark, sessions, valid = self.marks.get(date, root, contract)
                if not valid or pd.isna(mark):
                    blocked = True
                    break
            if blocked:
                desired = current
                self.trade_rows.append(
                    {
                        "date": date,
                        "root": root,
                        "group_id": order.get("group_id"),
                        "contract": None,
                        "units": 0.0,
                        "price": np.nan,
                        "reason": "entry_blocked",
                        "flag": "invalid_leg",
                    }
                )

            contracts = set(current) | set(desired)
            net_trades: dict[Any, float] = {}
            prices: dict[Any, float] = {}
            valid_trades: dict[Any, bool] = {}
            for contract in contracts:
                net = desired.get(contract, 0.0) - current.get(contract, 0.0)
                if net == 0:
                    continue
                mark, sessions, valid = self.marks.get(date, root, contract)
                if pd.isna(mark):
                    continue
                net_trades[contract] = net
                prices[contract] = mark
                valid_trades[contract] = valid

            if not net_trades:
                self.pending.pop(root, None)
                continue

            gross_prev = sum(
                abs(units * self.prev_marks.get((root, contract), np.nan))
                for contract, units in current.items()
                if not pd.isna(self.prev_marks.get((root, contract), np.nan))
            )
            gross_desired = sum(
                abs(units * self.marks.get(date, root, contract)[0])
                for contract, units in desired.items()
                if not pd.isna(self.marks.get(date, root, contract)[0])
            )
            traded = sum(abs(net * prices[contract]) for contract, net in net_trades.items())
            denom = gross_prev if gross_prev > 0 else gross_desired
            cost = (
                self.config.cost_bps_per_leg / 10_000.0 * traded / denom
                if denom > 0
                else 0.0
            )
            self._today_cost_total += cost

            reason = self._reason(
                current, desired, current_group, order.get("group_id")
            )
            for contract, net in net_trades.items():
                flag = ""
                if order.get("forced"):
                    flag = "forced_exit"
                elif net < 0 and not valid_trades.get(contract, True):
                    flag = (
                        "roll_leg_missing"
                        if reason == "roll"
                        else "exit_stale"
                    )
                self.trade_rows.append(
                    {
                        "date": date,
                        "root": root,
                        "group_id": order.get("group_id"),
                        "contract": contract,
                        "units": net,
                        "price": prices[contract],
                        "reason": reason,
                        "flag": flag,
                    }
                )

            # Replace the root's positions with the desired legs.
            for (r, g, contract) in list(self.positions):
                if r == root:
                    del self.positions[(r, g, contract)]
            group_id = order.get("group_id")
            if group_id is not None:
                self.position_meta[(root, group_id)] = {
                    "commodity": order.get("commodity"),
                    "sector": order.get("sector"),
                }
                for contract, units in desired.items():
                    if units != 0:
                        self.positions[(root, group_id, contract)] = units
                        self.prev_marks[(root, contract)] = prices.get(
                            contract, self.marks.get(date, root, contract)[0]
                        )
            else:
                for contract in current:
                    self.prev_marks.pop((root, contract), None)

            # Attach the cost to the group row for this date. New groups get a
            # zero-gross row so the cost is visible and included in the average.
            target_group = group_id if group_id is not None else current_group
            attached = False
            for row in reversed(self._today_rows):
                if row["date"] != date or row["root"] != root:
                    continue
                if row["group_id"] == target_group:
                    row["cost"] += cost
                    row["return_net"] = row["return_gross"] - row["cost"]
                    attached = True
                    break
            if not attached and cost:
                self._append_return(
                    {
                        "date": date,
                        "root": root,
                        "commodity": order.get("commodity"),
                        "sector": order.get("sector"),
                        "group_id": target_group,
                        "return_gross": 0.0,
                        "return_net": -cost,
                        "gross_notional": gross_desired,
                        "cost": cost,
                        "is_cost_row": True,
                        "sessions_since_valid": 0,
                        "is_valid": True,
                    }
                )
            self.pending.pop(root, None)

    @staticmethod
    def _reason(
        current: dict[Any, float],
        desired: dict[Any, float],
        current_group: Any,
        desired_group: Any,
    ) -> str:
        if not current and desired:
            return "entry"
        if current and not desired:
            return "exit"
        if current and desired:
            return "roll" if current_group != desired_group else "rebalance"
        return "noop"

    def _make_pending(self, date: pd.Timestamp, prev_date: pd.Timestamp | None) -> None:
        """Create pair-specific pending orders for the next trading day."""

        roots = set(self.pair_panel["root"].dropna().unique())
        for root in roots:
            current_pair = self.pair_lookup.get((date, root))
            last_pair = self.last_pair.get(root)
            pair_changed = prev_date is not None and current_pair != last_pair
            is_rebalance = date in self.rebalance_dates
            if not (pair_changed or is_rebalance):
                continue
            if root in self.force_flat:
                self.pending[root] = {
                    "group_id": None,
                    "pair": None,
                    "legs": {},
                    "commodity": None,
                    "sector": None,
                    "forced": True,
                }
                continue
            if current_pair is None:
                self.pending[root] = {
                    "group_id": None,
                    "pair": None,
                    "legs": {},
                    "commodity": None,
                    "sector": None,
                    "forced": False,
                }
                continue
            rows = self._targets.get((date, root), [])
            order = self._pending_from_rows(rows)
            if order["pair"] is not None and order["pair"] != current_pair:
                order = {
                    "group_id": None,
                    "pair": None,
                    "legs": {},
                    "forced": False,
                }
            self.pending[root] = order
            if order.get("group_id") is not None:
                self.position_meta[(root, order["group_id"])] = {
                    "commodity": order.get("commodity"),
                    "sector": order.get("sector"),
                }

    def _record_positions(self, date: pd.Timestamp) -> None:
        for (root, group_id, contract), units in self.positions.items():
            if units == 0:
                continue
            mark, sessions, valid = self.marks.get(date, root, contract)
            self.position_rows.append(
                {
                    "date": date,
                    "root": root,
                    "commodity": self.position_meta.get((root, group_id), {}).get("commodity"),
                    "sector": self.position_meta.get((root, group_id), {}).get("sector"),
                    "group_id": group_id,
                    "contract": contract,
                    "units": units,
                    "mark": mark,
                    "sessions_since_valid": sessions,
                    "is_valid": valid,
                    "flag": "sample_end_open" if date == self.trading_days[-1] else "",
                }
            )

    def _record_portfolio(self, date: pd.Timestamp) -> None:
        active_rows = [
            row for row in self._today_rows if not row.get("is_cost_row", False)
        ]
        groups_after = {
            (root, group_id)
            for (root, group_id, _contract), units in self.positions.items()
            if units != 0
        }
        n_active = len(active_rows)
        n_after = len(groups_after)
        denom = max(n_active, n_after, 1)
        ret_gross = (
            float(np.mean([row["return_gross"] for row in active_rows]))
            if active_rows
            else 0.0
        )
        cost = self._today_cost_total / denom
        gross_total = 0.0
        net_total = 0.0
        for (root, group_id, contract), units in self.positions.items():
            if units == 0:
                continue
            mark = self.marks.get(date, root, contract)[0]
            if pd.isna(mark):
                continue
            value = abs(units * mark)
            gross_total += value
            net_total += np.sign(units) * value
        self.portfolio_rows.append(
            {
                "date": date,
                "return_gross": ret_gross,
                "return_net": ret_gross - cost,
                "cost": cost,
                "N_t": max(n_active, n_after),
                "net_exposure": net_total / gross_total if gross_total > 0 else 0.0,
            }
        )

    def run(self) -> BacktestResult:
        prev_date: pd.Timestamp | None = None
        for date in self.trading_days:
            self._mark_day(date)
            self._execute_pending(date)
            self._make_pending(date, prev_date)
            self._record_positions(date)
            self._record_portfolio(date)
            for root in set(self.pair_panel["root"].dropna().unique()):
                self.last_pair[root] = self.pair_lookup.get((date, root))
            prev_date = date
            self.marks.cache.clear()

        positions = pd.DataFrame(self.position_rows)
        daily = pd.DataFrame(self.return_rows)
        portfolio = pd.DataFrame(self.portfolio_rows)
        trades = pd.DataFrame(self.trade_rows)
        return BacktestResult(
            positions=positions,
            daily_returns=daily,
            portfolio_returns=portfolio,
            trades=trades,
            config=self.config,
        )


def run_backtest(
    pair_panel: pd.DataFrame,
    contract_panel: pd.DataFrame,
    target_legs: pd.DataFrame,
    config: BacktestConfig | None = None,
    mark_state: pd.DataFrame | None = None,
) -> BacktestResult:
    """Run the daily event-loop backtest.

    ``pair_panel`` is the K=5 backtest pair/spread panel (selection and pair
    changes). ``contract_panel`` is the contract-level price panel (marks and
    fills). ``target_legs`` comes from ``build_target_legs``. The function does
    not read files, so tests can pass synthetic frames.
    """

    cfg = config or BacktestConfig()
    if cfg.execution_lag != 1:
        raise ValueError("Only execution_lag=1 is supported for now")
    if cfg.rebalance not in {
        "last_trading_day_of_week",
        "last_trading_day_of_month",
    }:
        raise ValueError(
            "rebalance must be 'last_trading_day_of_week' or "
            "'last_trading_day_of_month'"
        )
    if cfg.return_denominator != "gross_notional":
        raise ValueError(
            "Only return_denominator='gross_notional' is supported for now"
        )
    engine = _Engine(pair_panel, contract_panel, target_legs, cfg, mark_state)
    return engine.run()

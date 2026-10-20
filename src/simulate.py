"""Holdings-based daily simulator for futures spread strategies.

Timing: a leg target dated t (signal at the t settle) is filled at the t+1
settle; the first P&L of the new holdings is the t+1 -> t+2 settle change.
Holdings are contracts, so P&L = contracts x point value x settle change and
returns are P&L / capital (fully collateralised, non-compounding NAV).

Path-dependent rules (per root, D-009 spirit):
- a fill needs a tradable settle for every leg that trades; otherwise the old
  holdings are kept and the day is flagged ``blocked``;
- a held contract with no tradable settle for more than ``max_invalid``
  sessions is closed at its last mark (``forced_exit``);
- with ``resize="on_change"`` contracts are held until the target or pair
  changes, or the budget moves by more than ``rebalance_band`` (relative);
  with ``resize="daily"`` notional is reset to target every day;
- no leg row for a signal date means "no signal" and holdings are kept; an
  explicit flat row (``group_id="flat"``) closes the position.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import costs as cost_model


@dataclass(frozen=True)
class SimConfig:
    """Simulation conventions."""

    capital: float = 1_000_000.0
    resize: str = "on_change"  # "on_change" | "daily"
    max_invalid: int = 5
    rebalance_band: float = 0.25
    cost: cost_model.CostParams = field(default_factory=cost_model.CostParams)


@dataclass
class SimResult:
    """Tables produced by ``simulate``."""

    holdings: pd.DataFrame  # date, root, contract, n (end of day)
    trades: pd.DataFrame  # one row per contract trade, with USD costs
    by_root: pd.DataFrame  # date x root P&L, costs, notionals (USD)
    daily: pd.DataFrame  # portfolio daily returns per cost layer
    config: SimConfig


def _root_book(legs: pd.DataFrame) -> dict:
    """Map signal date -> (key, contracts, units, budget) for one root.

    ``key`` = (group_id, target); the budget is compared separately against
    the rebalance band. A flat row yields no contracts.
    """

    rows: dict = {}
    cols = zip(legs["date"], legs["group_id"], legs["contract"], legs["units"], legs["budget"], legs["target"])
    for date, group, contract, units, budget, target in cols:
        entry = rows.setdefault(date, [group, round(float(target), 12), [], [], float(budget)])
        if group != "flat" and isinstance(contract, str):
            entry[2].append(contract)
            entry[3].append(units)
    book = {}
    for date, (group, target, contracts, units, budget) in rows.items():
        if not contracts:
            book[date] = (("flat", 0.0), [], np.array([]), 0.0)
        else:
            book[date] = ((group, target), contracts, np.array(units, float), budget)
    return book


def _desired(spec, price: dict, pv: float, capital: float) -> dict | None:
    """Contracts per leg for a target spec at fill prices; None if unpriceable."""

    _key, contracts, units, budget = spec
    if not contracts:
        return {}
    px = np.array([price.get(c, (np.nan, False))[0] for c in contracts])
    ok = all(price.get(c, (np.nan, False))[1] for c in contracts) and np.all(px > 0)
    if not ok:
        return None
    scale = budget * capital / np.sum(np.abs(units) * px * pv)
    return dict(zip(contracts, units * scale))


def _price_book(marks_r: pd.DataFrame) -> dict:
    """Map date -> {contract: (settle, tradable, mark)} for one root."""

    book: dict = {}
    cols = zip(marks_r["date"], marks_r["contract_code"], marks_r["settle"], marks_r["tradable"], marks_r["mark"])
    for date, contract, settle, tradable, mark in cols:
        book.setdefault(date, {})[contract] = (settle, bool(tradable), mark)
    return book


def _trade_rows(date, root, old: dict, new: dict, px: dict, last_mark: dict, reason: str) -> list:
    """Trade rows for moving from ``old`` to ``new`` holdings."""

    rows = []
    for c in sorted(set(old) | set(new)):
        dn = new.get(c, 0.0) - old.get(c, 0.0)
        if abs(dn) > 1e-12:
            price = px[c][0] if c in px and px[c][1] else last_mark.get(c, np.nan)
            rows.append((date, root, c, dn, price, reason))
    return rows


def _exits(f, root, state, px, last_date, cfg) -> tuple[dict, list, str | None]:
    """Close expired contracts and contracts invalid for > max_invalid sessions.

    Both are closed at the contract's last mark. Expiry: the contract has no
    rows after its last date (final settle). Returns reduced holdings, trade
    rows and the exit status (None if nothing was closed).
    """

    hold, last_mark, invalid = state["hold"], state["last_mark"], state["invalid"]
    for c in hold:
        invalid[c] = 0 if px.get(c, (np.nan, False))[1] else invalid.get(c, 0) + 1
    expired = {c for c in hold if f > last_date.get(c, f)}
    forced = {c for c in hold if c not in expired and invalid[c] > cfg.max_invalid}
    if not expired and not forced:
        return hold, [], None
    rows = []
    for subset, reason in ((expired, "expiry"), (forced, "forced_exit")):
        rows += _trade_rows(f, root, {c: hold[c] for c in subset}, {}, {}, last_mark, reason)
    state["key"] = None
    reduced = {c: n for c, n in hold.items() if c not in expired | forced}
    return reduced, rows, "forced_exit" if forced else "expiry"


def _step(f, s, root, state, book, prices, last_date, pv, cfg) -> tuple[dict, list, str]:
    """Advance one root by one fill day; return new holdings, trades, status."""

    px = prices.get(f, {})
    for c, (_settle, _ok, mark) in px.items():
        if pd.notna(mark):
            state["last_mark"][c] = mark
    hold, rows, exit_status = _exits(f, root, state, px, last_date, cfg)
    spec = book.get(s)
    if spec is None:
        return hold, rows, exit_status or ("no_signal" if hold else "hold")
    if cfg.resize == "on_change" and spec[0] == state["key"]:
        old = state.get("budget", 0.0)
        if old == spec[3] or (old > 0 and abs(spec[3] / old - 1.0) <= cfg.rebalance_band):
            return hold, rows, exit_status or "hold"
    new = _desired(spec, px, pv, cfg.capital)
    traded = [] if new is None else [c for c in set(hold) | set(new) if abs(new.get(c, 0.0) - hold.get(c, 0.0)) > 1e-12]
    if new is None or not all(px.get(c, (np.nan, False))[1] for c in traded):
        return hold, rows, exit_status or "blocked"
    state["key"], state["budget"] = spec[0], spec[3]
    rows += _trade_rows(f, root, hold, new, px, state["last_mark"], "rebalance")
    return new, rows, exit_status or "traded"


def _run_root(root, legs_r, marks_r, calendar, pv, cfg) -> tuple[list, list, list]:
    """Event loop for one root over the union calendar."""

    book, prices = _root_book(legs_r), _price_book(marks_r)
    last_date = marks_r.groupby("contract_code")["date"].max().to_dict()
    start = calendar.searchsorted(legs_r["date"].min())
    end = calendar.searchsorted(marks_r["date"].max(), side="right")
    state = {"hold": {}, "last_mark": {}, "invalid": {}, "key": None}
    hold_rows, trade_rows, status_rows = [], [], []
    for i in range(start + 1, end):
        s, f = calendar[i - 1], calendar[i]
        new, trades, status = _step(f, s, root, state, book, prices, last_date, pv, cfg)
        state["hold"] = {c: n for c, n in new.items() if abs(n) > 1e-12}
        trade_rows += trades
        if status in ("blocked", "forced_exit", "expiry", "no_signal"):
            status_rows.append((f, root, status))
        hold_rows += [(f, root, c, n) for c, n in state["hold"].items()]
    return hold_rows, trade_rows, status_rows


def _holdings_pnl(holdings: pd.DataFrame, marks: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """P&L on day t+1 of holdings at the end of day t, plus end-of-day notional."""

    h = holdings.copy()
    pos = calendar.searchsorted(h["date"])
    h["pnl_date"] = calendar[np.minimum(pos + 1, len(calendar) - 1)]
    h.loc[pos + 1 >= len(calendar), "pnl_date"] = pd.NaT
    m = marks[["date", "root", "contract_code", "dprice", "mark", "point_value"]]
    m = m.rename(columns={"contract_code": "contract"})
    nxt = m[["date", "root", "contract", "dprice"]].rename(columns={"date": "pnl_date"})
    h = h.merge(nxt, on=["pnl_date", "root", "contract"], how="left")
    h = h.merge(m[["date", "root", "contract", "mark", "point_value"]], on=["date", "root", "contract"], how="left")
    h = h.sort_values(["root", "contract", "date"])
    h["mark"] = h.groupby(["root", "contract"])["mark"].ffill()
    h["point_value"] = h.groupby("root")["point_value"].transform(lambda s: s.ffill().bfill())
    h["pnl"] = h["n"] * h["point_value"] * h["dprice"].fillna(0.0)
    h["gross_notional"] = (h["n"] * h["point_value"] * h["mark"]).abs()
    return h


def _by_root(h: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    """Date x root USD table: P&L, costs, traded and held notional."""

    pnl = h.groupby(["pnl_date", "root"])["pnl"].sum().rename_axis(["date", "root"])
    held = h.groupby(["date", "root"])["gross_notional"].sum()
    cost_cols = ["notional", "cost_half_spread", "cost_fee", "cost_impact"]
    tr = trades.groupby(["date", "root"])[cost_cols].sum().rename(columns={"notional": "traded_notional"})
    out = pd.concat([pnl.rename("pnl_gross"), held, tr], axis=1).fillna(0.0)
    return out.reset_index().sort_values(["date", "root"]).reset_index(drop=True)


def _daily(by_root: pd.DataFrame, capital: float) -> pd.DataFrame:
    """Portfolio daily returns for each cost layer, turnover and gross exposure."""

    d = by_root.drop(columns="root").groupby("date").sum()
    out = pd.DataFrame(index=d.index)
    out["ret_gross"] = d["pnl_gross"] / capital
    out["ret_net_spread"] = (d["pnl_gross"] - d["cost_half_spread"]) / capital
    out["ret_net_fee"] = out["ret_net_spread"] - d["cost_fee"] / capital
    out["ret_net_all"] = out["ret_net_fee"] - d["cost_impact"] / capital
    out["turnover"] = d["traded_notional"] / capital
    out["gross_exposure"] = d["gross_notional"] / capital
    return out.reset_index()


def simulate(legs: pd.DataFrame, marks: pd.DataFrame, config: SimConfig | None = None) -> SimResult:
    """Run the holdings-based backtest.

    Args:
        legs: Leg targets from ``sizing.legs_from_signal`` (dated at the
            signal date t; filled at t+1).
        marks: Output of ``marks.build_marks``.
        config: Capital, resize policy and cost parameters.

    Returns:
        ``SimResult`` with holdings, costed trades, a date x root table and
        portfolio daily returns per cost layer.
    """

    cfg = config or SimConfig()
    calendar = pd.DatetimeIndex(sorted(marks["date"].unique()))
    pv = marks.groupby("root")["point_value"].first()
    hold_rows, trade_rows, status_rows = [], [], []
    for root, legs_r in legs.groupby("root"):
        marks_r = marks.loc[marks["root"] == root]
        h, t, s = _run_root(root, legs_r, marks_r, calendar, float(pv[root]), cfg)
        hold_rows += h
        trade_rows += t
        status_rows += s
    holdings = pd.DataFrame(hold_rows, columns=["date", "root", "contract", "n"])
    trades = pd.DataFrame(trade_rows, columns=["date", "root", "contract", "dn", "price", "reason"])
    m = marks.rename(columns={"contract_code": "contract"})
    trades = trades.merge(m[["date", "root", "contract", "adv", "sigma", "point_value", "tick_size"]], on=["date", "root", "contract"], how="left")
    # Expiry exits have no marks row on the exit day: use the last known inputs.
    last = m.groupby(["root", "contract"])[["adv", "sigma"]].last()
    key = pd.MultiIndex.from_frame(trades[["root", "contract"]])
    for col in ("adv", "sigma"):
        trades[col] = trades[col].fillna(pd.Series(last[col].reindex(key).to_numpy(), index=trades.index))
    trades["point_value"] = trades["root"].map(pv)
    trades["tick_size"] = trades["tick_size"].fillna(trades["root"].map(marks.groupby("root")["tick_size"].first()))
    trades = cost_model.trade_costs(trades, cfg.cost)
    by_root = _by_root(_holdings_pnl(holdings, marks, calendar), trades)
    status = pd.DataFrame(status_rows, columns=["date", "root", "status"])
    by_root = by_root.merge(status, on=["date", "root"], how="outer")
    num_cols = by_root.columns.drop(["date", "root", "status"])
    by_root[num_cols] = by_root[num_cols].fillna(0.0)
    return SimResult(holdings, trades, by_root, _daily(by_root.drop(columns="status"), cfg.capital), cfg)

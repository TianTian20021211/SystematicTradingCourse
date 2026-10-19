# Progress — Carry Baseline (A)

**Last updated:** 2026-10-19 15:16  
**Branch:** `main`  
**Working tree:** `src/curve.py` modified, `src/panel.py` modified,
`src/signals.py` new; not committed yet.  
**Plan:** `~/.claude/plans/polished-crafting-clock.md`

This is the live status file for another agent or the teammate. The stable
end-of-phase snapshot remains `docs/HANDOFF.md`; decisions are in
`docs/decisions.md`; the action history is in `docs/logs/AGENT_LOG.md`.

---

## Status

| Area | Status | Notes |
|---|---|---|
| Data layer | done | D=10 research panels unchanged |
| K=5 backtest panel | done | 236,385 pair-dates; M1–M2 159,817 / M2–M3 76,568 |
| Per-contract mark state | done | `last_valid_settle`, `sessions_since_valid` (missing + stale + absent) |
| Carry signal | done | target counts: −1 161,058 / +1 73,661 / 0 1,666 |
| Backtest engine | pending | `src/backtest.py` |
| Metrics | pending | `src/metrics.py` |
| A benchmark | pending | `notebooks/02_carry.ipynb` |
| Tests | partial | 15 existing tests pass; new tests pending |
| Docs/log | in progress | D-009 + LOG-0010 with the foundation commit |

---

## Decisions in force

- Backtest eligibility is **K=5 ex ante** (`days_to_delivery_start >= 5`,
  `d=None`); the D=10 research panel is kept and is **not** the backtest panel.
- Return is **gross-notional**:
  `position × Δspread / (|P_near| + |P_far|)`; denominator uses the previous
  trading day's last valid prices.
- Rebalance is the **last trading day of the week** (fixed Friday with holiday
  fallback); signal at t close, fill at t+1 close.
- Roll: detect at t, close the old pair at **t+1** with last valid marks; flag
  `roll_leg_missing` when the old leg is absent. No same-close roll.
- Missing/stale: no new entry; hold at last valid; forced exit on the **6th**
  consecutive invalid session.
- Costs: **5 bps per leg of that leg's notional**, applied to actual net legs.
- Sample: **1986–2015 train / 2016–2026 test**; both start flat.
- Sharpe: daily returns, rf=0, `× sqrt(252)`; no-position days return 0.
- No leverage; no liquidity hard filter; no multiplier/dollar P&L yet.

---

## Files changed in the foundation

- `src/curve.py` — `add_eligibility` / `select_pairs` accept `d=None`;
  K-only mode no longer depends on `days_to_last_trading`.
- `src/panel.py` — `build_backtest_panel()` and
  `build_contract_mark_state()`.
- `src/signals.py` — `CarryParams` and `carry_signal()`.
- `docs/PROGRESS.md` — this file.
- `docs/decisions.md` — D-009.
- `docs/logs/AGENT_LOG.md` / `docs/logs/INDEX.md` — LOG-0010.

Not committed yet at the time of writing.

---

## Verification so far

- `python -m pytest -q` → **15 passed**.
- K=5 panel: **236,385** pair-dates; M1–M2 159,817 / M2–M3 76,568.
- Mark state tested on 20 contracts: `last_valid_settle`,
  `sessions_since_valid`, stale/missing/absent flags.
- Carry signal: `carry_ann` NaN only on the CL 2020-04-20 negative-price day;
  dollar-spread `target` still valid.

---

## How to reproduce the current state

```bash
python -m pytest -q
```

```python
import pandas as pd
from src import panel, signals

rank = pd.read_parquet("data/processed/rank.parquet")
bt = panel.build_backtest_panel(rank, d=None, k=5)
sig = signals.carry_signal(bt["spread"])
```

The K=5 panels are not saved yet; `02_carry.ipynb` will save them under
`data/processed/backtest_pairs.parquet` / `backtest_spread.parquet`
(gitignored).

---

## Next

1. `src/backtest.py`: `BacktestConfig`, `BacktestResult`, `build_target_legs`,
   `run_backtest` with the pair-specific pending-order state machine.
2. `src/metrics.py`: summary + normalized conditional mean.
3. Tests and `02_carry.ipynb`.
4. D-009/LOG-0011/LOG-0012 docs, then the engine and benchmark commits.

See the plan file for the full design and the R1–R9 logic-review fixes.

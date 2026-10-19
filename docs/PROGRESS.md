# Progress — Carry Baseline (A)

**Last updated:** 2026-10-19 15:55  
**Branch:** `main`  
**Latest commits:** `f2c4771` (foundation), `1b833c9` (engine), `bd6691b`
(benchmark).  
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
| Per-contract mark state | done | last valid + missing/stale/absent sessions |
| Carry signal | done | target: −1 161,058 / +1 73,661 / 0 1,666 |
| Backtest engine | done | daily event loop, pair-specific pending orders |
| Metrics | done | summary, conditional mean, sector, plot |
| A benchmark | done | full/train/test; negative result |
| Tests | done | 32 passed |
| Notebook | done | `notebooks/02_carry.ipynb` |

---

## Benchmark result (first pass)

| Period | Gross ann. | Net ann. | Sharpe gross | Sharpe net | Max DD net |
|---|---:|---:|---:|---:|---:|
| Full 1986–2026 | −0.53% | −1.90% | −0.02 | −0.08 | −55.3% |
| Train 1986–2015 | −0.44% | −1.78% | −0.02 | −0.10 | −42.7% |
| Test 2016–2026 | −0.76% | −2.20% | −0.02 | −0.06 | −21.9% |

Conditional raw spread return (the actual A hypothesis):

| Group | Raw mean | Raw t-stat | n_dates |
|---|---:|---:|---:|
| `target_positive` (backwardation) | −0.000020 | −0.27 | 2,108 |
| `target_negative` (contango) | +0.000127 | +2.41 | 2,115 |

**Reading:** A has no edge in this simplest K=5 baseline. The contango short is
wrong-signed: contango spreads tend to strengthen, not weaken; the backwardation
long is approximately flat. Costs (~13x turnover, −1.4%/yr) make the net result
worse. This is a valid negative result, not a bug. Do not tune on the test set.

---

## Decisions in force

- Backtest eligibility is K=5 ex ante; D=10 research panels are kept.
- Gross-notional return, lagged denominator.
- Fixed Friday rebalance, t+1 settlement fill.
- Roll close at t+1, `roll_leg_missing` flag.
- 6th invalid session forced exit.
- 5 bps per leg, exact net-leg cost.
- 1986–2015 train / 2016–2026 test.
- See D-009 in `docs/decisions.md`.

---

## Main files

- `src/curve.py` — `d=None` K-only eligibility
- `src/panel.py` — `build_backtest_panel`, `build_contract_mark_state`
- `src/signals.py` — `CarryParams`, `carry_signal`
- `src/backtest.py` — `BacktestConfig`, `BacktestResult`, `build_target_legs`,
  `run_backtest`
- `src/metrics.py` — `summarize`, `conditional_mean`, `sector_summary`,
  `plot_result`
- `tests/test_eligibility.py`, `tests/test_signals.py`,
  `tests/test_backtest.py`
- `notebooks/02_carry.ipynb`
- `docs/backtest_framework.md`, `docs/data_dictionary.md` §10

---

## How to reproduce

```bash
python -m pytest -q
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/02_carry.ipynb
```

The notebook builds the K=5 panels in memory, runs the full and test backtests,
and writes summary/conditional/sector CSVs and a cumulative-return PNG to
`output/` (gitignored).

---

## Next

1. Commit the engine + benchmark (LOG-0011 / LOG-0012), update HANDOFF/README/
   AGENTS, push.
2. Decide the next idea: C (mean reversion) is the natural reuse of the engine.
3. Deferred: threshold/buffer, cross-section, inverse-vol, h=21, tick-based
   cost, liquidity filters, point-in-time D=10 proxy.

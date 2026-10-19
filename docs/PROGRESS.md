# Progress — A, B, and C Baselines

**Last updated:** 2026-10-19  
**Branch:** `feat/idea-c-mean-reversion` (C); `main` has A/B.  
**A baseline:** `bd6691b`; **A diagnosis:** `f02f18b`.  
**B pre-test:** `d257e0e`.  
**C baseline + hedge-ratio variant:** this branch; not merged into `main` yet.  
**Plans:** A `~/.claude/plans/polished-crafting-clock.md`;
C `~/.claude/plans/valiant-pondering-peacock.md`.

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
| A diagnosis | done | side × sector × era, K=5 vs K=10, costs |
| B pre-test | done | adjacent-carry rank; negative before costs |
| C baseline | done on branch | 1:1 weekly; negative net result |
| C hedge-ratio variant | done on branch | 60-day rolling OLS; negative gross result |
| Tests | done | 58 passed on the C branch |
| Notebooks | done | `02_carry`, `03_mean_reversion`, `04_a_diagnose`, `05_b_pretest` |

---

## A benchmark result (first pass)

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

## A diagnosis follow-up（merged from `a-robustness`）

- Side × sector × era：short raw mean **+0.000024**（t +2.46），
  long raw mean −0.000008（t −0.65）；负 P&L 主要来自 short side。
- K=5 vs K=10（都是 ex-ante）：两者都负；K=10 的 short raw mean +0.000018
  （t +1.84），long −0.000032（t −2.83）。D=10 未使用（ex-post）。
- 成本 0/5/10/20 bps：net ann. −0.53% / −1.90% / −3.24% / −5.89%；
  gross 已经负，成本不是主因。
- 结论：**no support + wrong sign in-sample**；test 期 t +0.87，
  不写成 “proven absent”。不做 rescue 变体。
- 文件：`src/a_diagnostics.py`、`notebooks/04_a_diagnose.ipynb`、
  `docs/a_negative_result.md`、`tests/test_a_diagnostics.py`。

---

## B pre-test（merged from `b-pre-test`）

Cheap, pre-registered B: long the highest-carry adjacent spread
(M1-M2 / M2-M3 / M3-M4), short the lowest; 4 legs; same engine.

| Period | Gross ann. | Net ann. | Sharpe gross | Sharpe net | Max DD net | Turnover |
|---|---:|---:|---:|---:|---:|---:|
| Full 1986–2026 | −1.14% | −2.84% | −0.08 | −0.19 | −70.1% | 17.4× |
| Train 1986–2015 | −1.10% | −2.80% | −0.08 | −0.21 | −58.3% | 17.6× |
| Test 2016–2026 | −1.25% | −2.96% | −0.07 | −0.15 | −28.5% | 17.0× |

Gross is already negative; the pre-registered rule says **skip B = True**.
This is the adjacent-carry version only; the residual/fitted-curve B was not
tested and should be a separate idea if ever tried.
Files: `src/b_pre_test.py`, `notebooks/05_b_pretest.ipynb`,
`docs/b_pretest.md`, `tests/test_b_pre_test.py`.

---

## Zero-cost check（0 bps）

`0 bps` = 不考虑 transaction cost，也就是 gross。A 和 B 在成本前都已经是负的：

| Idea | Period | Gross ann. (0 bps) | Gross Sharpe | Net ann. (5 bps) | Net Sharpe |
|---|---|---:|---:|---:|---:|
| A | Full | −0.53% | −0.02 | −1.90% | −0.08 |
| A | Train | −0.44% | −0.02 | −1.78% | −0.10 |
| A | Test | −0.76% | −0.02 | −2.20% | −0.06 |
| B | Full | −1.14% | −0.08 | −2.84% | −0.19 |
| B | Train | −1.10% | −0.08 | −2.80% | −0.21 |
| B | Test | −1.25% | −0.07 | −2.96% | −0.15 |

**Reading:** 成本放大亏损，但不改变符号。A 的 0 bps 结果和
`04_a_diagnose` 的 cost-sensitivity 第一行一致；B 的 gross 列来自
`05_b_pretest` 的 summary。

---

## C baseline（this branch; not yet in main）

C2 additive continuous index; dollar z L=20; weekly ±2/0; 1:1 dollar spread;
5 bps/leg.

| Period | Gross ann. | Net ann. | Sharpe net | Max DD net | Turnover |
|---|---:|---:|---:|---:|---:|
| Full 1986–2026 | +0.53% | −1.67% | −0.03 | −51.6% | 22.6× |
| Train 1986–2015 | +0.87% | −1.32% | −0.045 | −35.4% | 22.7× |
| Test 2016–2026 | −0.39% | −2.64% | −0.025 | −26.9% | 22.6× |
| Energy 1992–2013 | −1.05% | −3.12% | −0.04 | −51.7% | 25.1× |

Conditional raw spread return:

| Period | Group | Raw mean | Raw t-stat | n_dates |
|---|---|---|---:|---:|
| Full | `target_positive` | +0.000017 | +0.11 | 2,071 |
| Full | `target_negative` | −0.000101 | −1.28 | 2,065 |
| Train | `target_positive` | +0.000112 | +1.72 | 1,515 |
| Train | `target_negative` | −0.000203 | −2.12 | 1,516 |
| Test | `target_positive` | −0.000217 | −0.40 | 555 |
| Test | `target_negative` | +0.000148 | +1.05 | 548 |

**Reading:** C has no robust, tradable edge in the 1:1 weekly baseline. Gross
returns are small and positive in-sample but ~22.6× turnover and 5 bps/leg
costs turn the full and test periods negative. The train short-spread
conditional mean is significant, but it does not survive in test. Energy
1992–2013 is negative with a 1:1 spread.

## C hedge-ratio variant（0 bps gross）

60-day rolling OLS on the continuous leg levels; strict weekly rebalancing
to the current `h`; 1:1 and hedge both at 0 bps.

| Period | Variant | Gross ann. | Vol | Sharpe | Turnover | Trades |
|---|---|---:|---:|---:|---:|---:|
| Full | 1:1 | +0.535% | 3.58% | 0.010 | 22.6× | 28,645 |
| Full | hedge | +0.197% | 2.62% | 0.006 | 20.4× | 56,289 |
| Train | 1:1 | +0.868% | 1.83% | 0.030 | 22.7× | 20,163 |
| Train | hedge | +0.290% | 1.54% | 0.012 | 20.3× | 40,476 |
| Test | 1:1 | −0.391% | 6.24% | −0.002 | 22.6× | 8,476 |
| Test | hedge | −0.055% | 4.39% | 0.001 | 20.6× | 15,798 |

`h` median 1.008; 5–95% 0.796–1.312; 99.3% valid. The hedge ratio lowers
volatility and return in full/train/test, does not improve Sharpe, and roughly
doubles trade count. Conditional mean full sample: hedge `target_negative` raw
mean +0.000020 (t 0.32) vs 1:1 −0.000101 (t −1.15); neither is significant.
Energy 1992–2013 (0 bps): 1:1 gross −1.05% / Sharpe −0.013; hedge −0.10% /
0.0002; the hedge is less bad but still has no positive edge.
**Conclusion:** no 5 bps run; the hedge ratio does not rescue C overall.

**Log IDs:** C baseline uses `LOG-0013`–`LOG-0018`; the later hedge-ratio
work uses `LOG-0022`–`LOG-0024`; A is `LOG-0019`, B `LOG-0020`, the A/B merge
is `LOG-0021`.

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
- C: D-010 (additive continuous index; signal-only; L=20; weekly v0).
- C hedge-ratio variant: D-011 (60-day rolling OLS levels; h>0; strict
  weekly h rebalancing; 0 bps gross first).

---

## Main files

- `src/curve.py` — `d=None` K-only eligibility; shared weekly calendar
- `src/panel.py` — `build_backtest_panel`, `build_contract_mark_state`
- `src/continuous.py` — roll-chained leg indices; rolling OLS hedge ratio
- `src/signals.py` — `CarryParams` / `carry_signal`;
  `MeanReversionParams` / `mean_reversion_signal`
- `src/backtest.py` — `BacktestConfig`, `BacktestResult`, `build_target_legs`
  (optional hedge-ratio weights), `run_backtest`
- `src/metrics.py` — `summarize`, `conditional_mean`, `sector_summary`,
  `plot_result`
- `src/a_diagnostics.py` — A negative-result diagnostics
- `src/b_pre_test.py` — cheap adjacent-carry B pre-test
- `tests/test_eligibility.py`, `tests/test_signals.py`,
  `tests/test_backtest.py`, `tests/test_continuous.py`,
  `tests/test_a_diagnostics.py`, `tests/test_b_pre_test.py`
- `notebooks/02_carry.ipynb`, `notebooks/03_mean_reversion.ipynb`,
  `notebooks/04_a_diagnose.ipynb`, `notebooks/05_b_pretest.ipynb`
- `docs/a_negative_result.md`, `docs/b_pretest.md`
- `docs/backtest_framework.md`, `docs/data_dictionary.md` §10

---

## How to reproduce

```bash
python -m pytest -q
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/02_carry.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/03_mean_reversion.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/04_a_diagnose.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/05_b_pretest.ipynb
```

Notebook 02 produces the `output/carry_*` tables; 03 produces
`output/mean_reversion_*`; 04 loads `output/carry_full_*` and writes the
diagnosis tables; 05 writes `output/b_pretest_summary.csv`. All outputs are
gitignored.

---

## Next

1. Merge the C branch after rebasing on latest `main`; notebook `03`,
   LOG-0013–0018 (baseline), and LOG-0022–0024 (hedge-ratio) are the C slots.
2. C remaining robustness: carry-neutral first, then daily, log, adjacent
   pairs, returns-based h, 20/120-day windows, h cap, Kalman.
3. D/H remain. Deferred A/B variants: residual B, threshold/buffer,
   cross-section, inverse-vol, h=21, tick-based cost, liquidity filters,
   point-in-time D=10 proxy.
4. No report has been written yet; A/B/C are documented as negative baselines.

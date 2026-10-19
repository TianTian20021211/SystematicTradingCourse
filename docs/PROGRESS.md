# Progress — A and B Baselines（C separate）

**Last updated:** 2026-10-19  
**Branch:** `main`  
**A baseline:** `bd6691b`; **A diagnosis:** merged from `a-robustness`
(`f02f18b`).  
**B pre-test:** merged from `b-pre-test` (`d257e0e`).  
**C branch:** `feat/idea-c-mean-reversion` at `5c21cf3` — deliberately **not**
merged into main yet.  
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
| A diagnosis | done | side × sector × era, K=5 vs K=10, costs |
| B pre-test | done | adjacent-carry rank; negative before costs |
| Tests | done | 36 passed after A+B merge |
| Notebooks | done | `02_carry`, `04_a_diagnose`, `05_b_pretest` |
| Notebook 03 | reserved | idea C (mean reversion), branch only |
| C baseline | not in main | 51 tests on its branch; negative net result |

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

## C status（not merged）

C lives on `feat/idea-c-mean-reversion` at `5c21cf3`, with 51 tests. Its
baseline is gross-positive but net-negative after ~22.6× turnover:
full gross +0.53%, net −1.67%, net Sharpe −0.03; test gross −0.39%,
net −2.64%. The branch also adds the shared weekly calendar, continuous
leg indices, and D-010. It is deliberately excluded from this merge so the
C agent can continue independently.

**Reserved slots for C:** notebook `03` and log IDs `LOG-0013`–`LOG-0018`.
A is `LOG-0019`, B is `LOG-0020`, the A/B merge entry is `LOG-0021`.
C's next log entry after the current branch head should be `LOG-0022` to
avoid a collision.

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
- D-010 (C continuous index) is on the C branch, not in main.

---

## Main files

- `src/curve.py` — `d=None` K-only eligibility
- `src/panel.py` — `build_backtest_panel`, `build_contract_mark_state`
- `src/signals.py` — `CarryParams`, `carry_signal`
- `src/backtest.py` — `BacktestConfig`, `BacktestResult`, `build_target_legs`,
  `run_backtest`
- `src/metrics.py` — `summarize`, `conditional_mean`, `sector_summary`,
  `plot_result`
- `src/a_diagnostics.py` — A negative-result diagnostics
- `src/b_pre_test.py` — cheap adjacent-carry B pre-test
- `tests/test_eligibility.py`, `tests/test_signals.py`,
  `tests/test_backtest.py`, `tests/test_a_diagnostics.py`,
  `tests/test_b_pre_test.py`
- `notebooks/02_carry.ipynb`, `notebooks/04_a_diagnose.ipynb`,
  `notebooks/05_b_pretest.ipynb`
- `docs/a_negative_result.md`, `docs/b_pretest.md`
- `docs/backtest_framework.md`, `docs/data_dictionary.md` §10

---

## How to reproduce

```bash
python -m pytest -q
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/02_carry.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/04_a_diagnose.ipynb
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/05_b_pretest.ipynb
```

Notebook 02 produces the `output/carry_*` tables; 04 loads
`output/carry_full_*` and writes the diagnosis tables; 05 writes
`output/b_pretest_summary.csv`. All outputs are gitignored.

---

## Next

1. Merge C later from `feat/idea-c-mean-reversion`; keep notebook `03` and
   LOG-0013–0018, and continue its log at LOG-0022.
2. C continues on its own branch (carry-neutral, daily, log, adjacent pairs,
   rolling OLS, Kalman).
3. D/H remain. Deferred A/B variants: residual B, threshold/buffer,
   cross-section, inverse-vol, h=21, tick-based cost, liquidity filters,
   point-in-time D=10 proxy.
4. No report has been written yet; A/B are documented as negative baselines.

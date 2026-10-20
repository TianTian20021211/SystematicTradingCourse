# B Pre-test — Negative Result

**Scope:** cheap, pre-registered B version. Not a full curve-fitting B.
**Status:** **closed** (2026-10-19); documented negative pre-test.
**Detail:** `notebooks/11_idea_b_adjacent_carry.ipynb` (old `05_b_pretest`
retired; recovery in `docs/notebook_history.md`).
**Branch:** merged from `b-pre-test` into `main`.

**Update 2026-10-20:** `B-flip` (long the lowest-carry adjacent spread,
short the highest) is a separate post-hoc, gross-only signal-research
hypothesis in notebook 11 (D-025). It is not a rescue of B, does not reopen
B as a strategy, and is not in the cross-idea official comparison. B remains
closed as a negative strategy result.

---

## 1. Definition

B is not A. A bets on the sign of the main pair spread over time. This pre-test
bets on **relative carry within one curve**:

- every date/root, compute annualized carry for `M1-M2`, `M2-M3`, `M3-M4`;
- long the highest-carry adjacent spread, short the lowest;
- 4 legs (shared legs net out);
- same K=5 engine, weekly rebalance, 5 bps per leg.

This is the cheapest version of Q7's "buy the cheap point, sell the rich point".
It is not the residual/fitted-curve version.

**Pre-registered decision rule:** skip B if full-sample `gross Sharpe < 0.2`
or `net Sharpe <= 0`.

---

## 2. Result

| Period | Gross ann. | Net ann. | Sharpe gross | Sharpe net | Max DD net | Turnover |
|---|---:|---:|---:|---:|---:|---:|
| Full 1986–2026 | −1.14% | −2.84% | −0.08 | −0.19 | −70.1% | 17.4× |
| Train 1986–2015 | −1.10% | −2.80% | −0.08 | −0.21 | −58.3% | 17.6× |
| Test 2016–2026 | −1.25% | −2.96% | −0.07 | −0.15 | −28.5% | 17.0× |

**Gross = 0 bps (no transaction cost).** Gross is already negative in all
periods: full −1.14% (Sharpe −0.08), train −1.10% (−0.08), test −1.25%
(−0.07). Costs make it worse but are not the cause of the sign. The
pre-registered rule returns **skip B = True**.

Target table: 872,652 leg rows; 236,070 near + 236,070 far + 400,512 extra.
Trades: 100,117 in the full sample. The relative-value legs are real (e.g., on
2021-10-01 CL the group is long CLF22/CLZ21 and short CLG22/CLX21), so this is
not an empty/no-trade result.

---

## 3. Conclusion

**Skip B in its adjacent-carry form.** The within-curve relative carry ranking
does not have an edge in this data, even before costs.

This is a **scope decision backed by a pre-registered test**, not a proof that
every possible B exists. The residual/fitted-curve B is a different hypothesis
and was not tested; it is also higher-complexity (4 points, curve fit,
overfitting risk). If it is ever tried, it should be a separate pre-registered
idea, not a rescue of this one.

**Final status: closed.** B adjacent-carry is not pursued. No parameter tuning;
the residual/fitted-curve B is not planned unless it becomes a separate
pre-registered idea.

---

## 4. Why this matters for the project

A and B are the two assignment examples. Both fail in their cheapest forms:

- A: the level/carry sign is wrong for contango; long side ~0.
- B: the within-curve relative carry rank is negative before costs.

The honest report can say: **the carry family, as specified by the assignment's
two examples, is not supported by this data.** That is a useful negative result,
not a failure of the data work.

---

## 5. Reproduce

```bash
python -m pytest -q
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/11_idea_b_adjacent_carry.ipynb
```

Outputs go to `output/b_pretest_summary.csv` (gitignored).

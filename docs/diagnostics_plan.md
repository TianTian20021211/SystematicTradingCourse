# Failure Diagnostics — Plan（A/B/D）

**Status:** proposed; not implemented. This is the handoff for the next
conversation.
**Date:** 2026-10-19
**Input:** v2 reruns on `main` — `output/v2_rerun/comparison.csv`,
`output/v2_rerun/{a,b,d}_root.csv`, `docs/v1_v2_comparison.md`,
notebooks 10–14.
**Scope:** A (carry), B (adjacent-carry pre-test), D (curve momentum) —
Tian's ownership under D-014. C and E are cited from Jiaheng's work; this
plan does not implement C/E diagnostics.

---

## 0. Purpose

The final report already says A/B/D are negative or mixed-negative. This
plan adds the missing explanation:

- **Why** did it fail — signal, mechanism, cost, or constraint?
- **Where** did it fail — all roots, a few roots, a period, a maturity
  bucket, or only before/after costs?
- **Can the data rule out a meaningful edge**, or is the sample simply too
  short?

This is a diagnostic plan, not a rescue plan. A variant that appears after
seeing these results must be a new pre-registered hypothesis.

---

## 1. Agreed decisions

| Item | Decision |
|---|---|
| Report purpose | Final report; explain A/B/D failures |
| Scope | A/B/D (Tian); C/E cited from Jiaheng |
| Engine | **v2 rerun is primary**; v1 is historical only; never mix v1/v2 in one table |
| A mechanism | days-to-expiry buckets; 1:1 vs beta-neutral; seasonality/roll-adjacent — all three in the main text |
| B treatment | One short paragraph: IC + cost layers + pre-registered skip |
| D treatment | Full diagnostic card; exact mechanism tests to be confirmed in the next conversation |
| Per-instrument | All 24 roots; Sharpe primary, annualised return in the table; block-bootstrap CI + 3-year window positive share; gross and net |
| Multiple testing | No SPA / random-effects meta-analysis; per D-016, per-root time-series, no cross-sectional ranking |
| Deliverables | Proposed `src/diagnostics.py` + diagnostics sections in notebooks 10/11/13, or a separate `notebooks/15_failure_diagnostics.ipynb` (cross-idea, not an idea notebook; not started) |

**Why v2:** D-016/D-018 pre-registered the v2 conventions and the reruns are
already on `main`. v2 separates gross / half-spread / fees / impact, provides
per-root outputs, and supports horizon and capacity diagnostics. v2 is a
better accounting framework; it does **not** rescue any idea.

---

## 2. Headline numbers (v2, full sample, annualised %)

| Strategy | Gross | Half-spread | Fees | All-in | Turnover |
|---|---:|---:|---:|---:|---:|
| A carry | −0.48 | −0.84 | −1.00 | −2.61 | 26.1× |
| D curve momentum | +0.22 | −0.07 | −0.20 | −1.42 | 22.1× |
| B adjacent carry | −1.13 | −2.18 | −2.37 | −4.47 | 31.0× |

Train/test gross (v2): A −0.56 / −0.27; D +0.37 / −0.21; B −1.10 / −1.23.
A and B are negative before costs; D is weakly positive in-sample and
negative in test. Costs make all three worse, but they are not the cause of
A's or B's sign.

---

## 3. Diagnostic card (same structure for A/B/D)

Each idea gets the same six blocks. The report should show the same tables
and figures for each, so the reader can compare failure modes.

### 3.1 Headline and effect size

- v2 full / train / test, four cost layers: gross → half-spread → fees →
  impact → all-in.
- Annualised return, Sharpe, max drawdown, turnover.
- **95% CI for mean return and Sharpe**, not only a point estimate.
- **MDE**: what |Sharpe| can this sample rule out at 80% power?
- State clearly: “no evidence of an edge” is not the same as “no edge.”

### 3.2 Per-instrument performance

- All 24 roots, not a selected subset.
- Primary metric: Sharpe; annualised return in the supporting table.
- Gross and all-in net, so “signal wrong” and “cost too high” are separable.
- **Block bootstrap** for each root: moving/stationary blocks, block length
  20–60 trading days, 2,000 draws; report 95% percentile CI.
- **3-year rolling positive share**: fraction of rolling 3-year windows with
  positive gross Sharpe. This is the temporal-stability answer; bootstrap
  alone is not.
- Annotate years of data and a liquidity flag; do not drop short-history or
  thin roots from the figure.
- Do not pick the best root. If the best root is highlighted, show the
  noise benchmark: for N independent roots, the expected maximum Sharpe under
  the null is roughly `sqrt(2 ln N / T)` (N=24, T=41.7 → about 0.39). This is
  a sanity check, not a formal test.

### 3.3 Mechanism — A

1. **Days-to-expiry buckets.** Use `days_to_delivery_start` (ex ante) and
   `days_to_last_trading` (descriptive, ex post). Buckets 0–5, 5–10, 10–20,
   20–40, 40+ trading days. Per bucket: mean spread return conditional on
   the carry sign, signal IC, t-stat, N. If the sign is correct only in the
   window excluded by K=5/no-delivery-month, A's failure is a **constraint**
   result, not evidence that carry is absent.
2. **1:1 vs beta-neutral.** The v2 default is equal-notional legs; A's v1
   used 1:1 contracts. Estimate a rolling beta of near vs far leg returns,
   scale the far leg, and decompose the 1:1 P&L into a beta-neutral component
   and a net-beta component. If net beta dominates, the 1:1 spread was not a
   clean carry test. This is a diagnostic; it does not change D-018's main
   result.
3. **Seasonality / roll-adjacent.** Drop the weeks around pair changes; group
   by calendar month or season; show a compact heatmap and a joint test.
   Do not cherry-pick individual months.

Expected output: three figures/tables, all in the main text.

### 3.4 Mechanism — B (short)

- IC of the adjacent-carry rank against forward relative return. If IC ≈ 0,
  the ranking is noise and the negative P&L is not a cost problem.
- Cost layers and turnover; B's v2 adapter is `b_legs` → `legs_from_rows`.
- One paragraph is enough; B already has a pre-registered skip rule.

### 3.5 Mechanism — D (implemented, D-028)

D is basis momentum: 12-month formation, monthly target, N=2. The protocol
is now fixed in D-028 and implemented in `src/d_validity.py` with a
“D signal validity” section in `notebooks/13_idea_d_curve_momentum.ipynb`.
The battery is:

- **Signal mechanism:** per-root time-series IC, hit rate, expanding
  quintiles, and predictive R² for the raw score; horizon profile at
  1/3/6/12 months; same-close versus t+1 timing.
- **Independence:** nested adjusted R² static → +D → +A carry → +C z;
  residual IC after controls; static always-long versus D timing.
- **Stability:** fixed decades, carry sign, spread-volatility terciles,
  rolling 36-month IC / positive share.
- **Placebo:** sign flip, within-root 6-month block shuffle, lags 1/3/6/12,
  and a future-score lead of 24 months.
- **Inference:** per-root block bootstrap (6-month main, 12-month
  sensitivity), `n_boot=2000`, `min_obs=60` months, FDR within each
  metric/horizon family, and a max-|IC| noise benchmark.

D's official trading result remains the v2 negative/mixed baseline; this
section is an information study, not a rescue. The headline result is in
D-028 and `docs/HANDOFF.md`.

The original cost decomposition, static baseline and time-stability items
remain useful for the final report but are now secondary to the validity
battery.

### 3.6 Robustness

- Cost layers (already in v2) and a 0-cost gross comparison.
- Sizing scheme: equal (main), inverse-vol, liquidity (D-016 options).
- Leg ratio: equal-notional (main, D-018) vs 1:1 contracts (A diagnostic).
- Resize: on_change (main) vs daily; capital: USD 10m main, capacity curve.
- Jackknife: drop one root, one sector, one year, or 2020; winsorize 1%.
- Do not use the 2016–2026 test sample for any choice.

---

## 4. Statistical rules

1. **Report CI and MDE, not only p-values.** The iid Sharpe approximation is
   `SE(SR) ≈ 1/sqrt(T)`:
   - full 41.7 years: SE ≈ 0.155, 95% CI ±0.30, MDE (80%) ≈ 0.43;
   - train 30.6 years: SE ≈ 0.181, CI ±0.35, MDE ≈ 0.51;
   - test 11.1 years: SE ≈ 0.301, CI ±0.59, MDE ≈ 0.84.

   Autocorrelation and fat tails widen these; block bootstrap is the real
   interval. The conclusion should be “we can rule out a stable |Sharpe|
   above X,” not “there is no relation.”
2. **Per-root, not cross-sectional.** D-016 is explicit: settlement times
   differ across exchanges and ~20–24 markets is too thin a cross-section.
   Do not rank roots or build long-short cross-sectional portfolios for the
   diagnostic.
3. **Do not count roots as independent trials.** 24 correlated roots are not
   24 independent tests. Report the distribution and the noise benchmark;
   do not interpret “18/24 positive” as 18 confirmations.
4. **Multiple testing:** no SPA/meta-analysis in this plan. If the report
   scans many roots/periods, label those cells exploratory and report the
   full grid, not only the significant cells. A light noise benchmark is
   enough for the report.
5. **Verdict taxonomy** for each idea:
   - no economically meaningful relation (CI inside an equivalence bound);
   - wrong sign / opposite premium (reverse must be a new pre-registered
     hypothesis, with costs and tail checks);
   - subset/regime only (needs OOS confirmation);
   - cannot tell (CI too wide; report MDE).

---

## 5. What already exists on main (do not duplicate)

| Need | Existing code |
|---|---|
| Per-root gross / costs / net / turnover | `src/report.py::root_table` |
| Per-root time-series IC | `src/horizon.py::ts_ic` |
| Rolling IC | `src/horizon.py::rolling_ts_ic` |
| Per-root block-bootstrap IC + CI + p | `src/horizon.py::block_bootstrap_ic` |
| Bootstrap IC figure | `src/figures.py::bootstrap_ic_distribution` |
| Horizon / signal decay | `src/horizon.py::horizon_profile` |
| Newey-West t | `src/horizon.py::newey_west_t` |
| Per-commodity P&L and cost layers | `src/figures.py::commodity_pnl_and_costs` |
| Capacity / k sweep | `src/report.py::capacity_curve`, `k_sweep` |
| Layered cost model | `src/costs.py`, `docs/transaction_costs.md` |

**Still missing (the new work):**

- per-root **Sharpe / return** block-bootstrap CI (existing bootstrap is IC);
- **rolling Sharpe** (existing rolling is IC);
- days-to-expiry buckets;
- 1:1 vs beta-neutral decomposition;
- seasonality / roll-adjacent;
- ADF + AR(1) half-life (C reference only);
- predictive regression at 1/5/21 days (C reference; `horizon_profile` is
  close but is a signed-return profile, not a regression).

---

## 6. v2 caveats to carry into the report

- **`d=5` is not point-in-time.** `curve.add_contract_calendar` uses
  `last_trade_proxy`; D-016's “exchange calendar, hence ex ante” claim is too
  strong. State the caveat.
- **Post-hoc train/test slices.** v2 does not restart flat in 2016, so v2
  train/test are not directly comparable to v1's separate runs.
- **Negative prices.** v2 refuses non-positive settles; CL 2020-04-20 is
  excluded, which can change tail and worst-day statistics.
- **B universe.** B keeps the v1 raw-rank adjacent universe, not the v2
  `d=5` universe (D-017); it is a within-root exception, not a
  cross-commodity ranking.
- **B costs.** `execution="legs"` is conservative because listed-spread
  pairing in `costs._spread_execution_factor` groups by `(date, root)`, not
  by group.
- **Liquidity.** `min_adv=100` is pre-registered in D-018; it appears in the
  v2 notebook and driver, not in D-016.
- **v1 known issues** (unchanged): forced-exit delay, `conditional_mean`
  misnamed as a block bootstrap, and the C invalid-h doc/code mismatch.
- **Never mix v1 and v2 numbers in one table.** State the engine on every
  table.

---

## 7. Proposed deliverables (next conversation)

1. `src/diagnostics.py`:
   - `block_bootstrap_ci(x, block, n_boot)` for mean and Sharpe, reusing
     `horizon._block_indices`;
   - `rolling_positive_share(returns, window_years=3)`;
   - `per_root_table(daily_returns_by_root, ...)` with CI + rolling share;
   - `days_to_expiry_buckets(...)`;
   - `beta_neutral_decomposition(...)`;
   - `seasonality_roll_check(...)`;
   - `adf_half_life(...)` and `predictive_regression(...)` only if the
     report needs the C reference.
2. Diagnostics: add sections to the relevant idea notebook (10/11/13), or a
   separate `notebooks/15_failure_diagnostics.ipynb` (cross-idea; not an idea
   notebook). One card each for A, B (short), D; same tables/figures.
3. Tests with synthetic data:
   - a known edge is detected;
   - pure noise does not produce a false positive;
   - block bootstrap CI has reasonable coverage.
4. Update `docs/HANDOFF.md`, `docs/PROGRESS.md`, `docs/logs/*` when results
   are written.
5. Do **not** push; keep main local unless asked.

---

## 8. Next-conversation checklist

- **D is done:** the signal-validity battery is implemented under D-028
  (`src/d_validity.py`, notebook 13 section 7, `tests/test_d_validity.py`).
- Confirm whether C/E stay cited-only or need a one-page comparison.
- Confirm the per-instrument figure layout for A/B (24 roots, CI + rolling
  share).
- Confirm whether to add a v1-aligned robustness for A only (1:1 contracts,
  weekly, flat 5 bps) or keep v2 as the only main result.
- A/B diagnostics remain separate; do not mix them into the D validity
  branch.

# Decision Log

Status values: `proposed`, `accepted`, `superseded`.

---

## D-001 · M1–M4 are slots, not contracts

- **Status:** accepted
- **Date:** 2026-10-17
- **Context:** The Bloomberg bulk export contains generic nearby ranks. On every
  roll date all four ranks shift by one contract; the front contract disappears
  from the panel.
- **Decision:** Build a lossless contract-level panel from
  `FUT_CUR_GEN_TICKER`. Compute returns within a contract and map them back to
  ranks. Never difference generic prices across a roll.
- **Consequences:** Roll-day returns use the new contract's previous-day price
  (old next rank). Naive generic returns are kept only as a diagnostic.

---

## D-002 · Pair eligibility: no delivery month + D=10 trading days

- **Status:** accepted
- **Date:** 2026-10-17
- **Context:** The data's generic roll date is Bloomberg's convention, not the
  exchange last trading day. For grains, softs, and metals, M1 rolls inside the
  delivery month. Holding into delivery is not acceptable for a financial
  backtest.
- **Decision:** A contract is eligible only if:
  1. the date is at least 5 trading days before the delivery-month start; and
  2. `days_to_last_trading > D`, with `D = 10` for main results.
  `D = 5` and `D = 20` are robustness checks.
- **Consequences:** Pairs are mostly M1–M2, shifting to M2–M3 near the generic
  roll. The pair rank mix is reported in QA. The rule is a proxy for first
  notice/last trading, not an exchange calendar.

---

## D-003 · Dollar spread primary, log spread reference

- **Status:** accepted
- **Date:** 2026-10-17
- **Context:** A 1:1 calendar spread's P&L is `multiplier × Δ(P_T1 - P_T2)`.
  Ratio/log spreads are scale-free but not the traded price.
- **Decision:** `spread_dollar` is the primary trading/P&L measure.
  `spread_log` is stored and used as a reference/signal measure. Log spread is
  valid only when both prices are positive.
- **Consequences:** Cross-commodity comparisons may use log/percentage
  normalization; the backtest still executes dollar spread.

---

## D-004 · Liquidity threshold deferred

- **Status:** accepted
- **Date:** 2026-10-17
- **Context:** A 5,000-contract threshold leaves about 19 commodities recently,
  fewer historically; M2–M3 liquidity is materially thinner than M1–M2.
- **Decision:** Build liquidity metrics and diagnostic plots first. Do not
  hard-code a universe filter. Thresholds 1k/5k/10k/20k are computed as
  booleans; the user chooses the final threshold after reviewing the plots.
- **Consequences:** `universe` tables carry threshold columns; notebooks do not
  filter unless an explicit threshold is passed.

---

## D-005 · Public repository excludes licensed data and papers

- **Status:** accepted
- **Date:** 2026-10-17
- **Context:** The GitHub repository is public. Bloomberg data is licensed;
  paper PDFs and course material have copyright constraints.
- **Decision:** Do not commit raw CSV/XLSX, paper PDFs, `Project.pdf`,
  `calendar-spread-brief.html`, processed parquet, or row-level extracts.
  Commit code, notebooks, docs, metadata, logs, and tests. `data/raw/README.md`
  documents filenames, checksums, and private acquisition.
- **Consequences:** Teammates need the raw CSV through a private channel; tests
  use synthetic fixtures; executed notebooks carry only aggregate/selected
  outputs.

---

## D-006 · Notebooks are narrative; logic lives in src

- **Status:** accepted
- **Date:** 2026-10-17
- **Context:** The final deliverable must be readable and reproducible.
- **Decision:** `notebooks/00_data_audit.ipynb` and
  `notebooks/01_panel_build.ipynb` contain short markdown narrative and short
  code cells that call `src/*.py`. No long transformations or million-row
  prints in notebooks. Processed parquet is generated, not committed.
- **Consequences:** All reusable logic is testable and importable; notebooks
  can be read without reading every implementation detail.

---

## D-007 · Agent log protocol

- **Status:** accepted
- **Date:** 2026-10-17
- **Context:** Two collaborators and their coding agents need a durable record
  of what changed and why, beyond git diffs.
- **Decision:** Maintain `docs/logs/AGENT_LOG.md` (append-only) and
  `docs/logs/INDEX.md`. Every material change gets an entry with ID, actions,
  files, commands, reason, validation, commit subject, and next step. Entries
  are committed with the change; commit messages reference the log ID.
- **Consequences:** Read `INDEX.md` and recent entries before work; append and
  index after work; never rewrite committed entries.

---

## D-008 · One common tradable spread for comparability

- **Status:** accepted
- **Date:** 2026-10-17
- **Context:** The project compares several signal families. If each idea uses
  a different pair definition, the comparison is not apples-to-apples.
- **Decision:** Main experiments use one common pair rule (nearest two eligible
  contracts, D=10, no delivery month) and one common dollar spread. Different
  ideas change the signal and holding period, not the spread definition.
  Adjacent pairs are built for robustness/alternative analysis; log/ratio
  representations are transformations, not different trades.
- **Consequences:** A/B/C/D/H are comparable at the instrument level; any
  per-idea pair change must be documented as a separate robustness experiment.

---

## D-009 · Carry baseline backtest conventions

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** D-002 uses `days_to_last_trading`, which is computed from each
  contract's final appearance in the full extract (`last_trade_proxy`). That is
  ex post information and cannot be used for pair selection in a backtest. The
  research panels remain useful for QA and description, but the backtest needs
  an ex ante universe and explicit execution/cost conventions so A (and later
  C/D/B) are comparable.
- **Decision:**
  1. **Eligibility:** the backtest uses K=5 ex ante only
     (`days_to_delivery_start >= 5`; `d=None`), not D=10. The existing D=10
     research panels are kept and are not overwritten.
  2. **Mark state:** per-contract `last_valid_settle` and
     `sessions_since_valid`, counting missing, stale (unchanged settle with
     zero/missing volume), and absent sessions. The rank-level `stale_run` is
     not used for the backtest.
  3. **Signal timing:** weekly rebalance on the last trading day of the week
     (fixed Friday with holiday fallback); signal at t close, fill at t+1
     close. No same-close execution.
  4. **Roll:** detect the pair change at t; close the old pair at t+1 using
     last valid marks; flag `roll_leg_missing` if the old leg is absent. Open
     the new pair from the t-close signal at t+1. Never difference spreads
     across different pairs.
  5. **Return:** gross-notional return,
     `position × Δspread / (|P_near| + |P_far|)`, with the denominator using
     the previous trading day's last valid prices. No dollar multiplier yet.
  6. **Missing/stale:** no new entry if either leg is invalid; hold at last
     valid; forced exit on the 6th consecutive invalid session, with a flag.
  7. **Costs:** 5 bps per leg of that leg's notional, applied to actual net
     traded legs (entry/exit 2 leg-units, flip/roll 4 leg-units, same-sign
     rebalance 0).
  8. **Sample:** 1986–2015 train, 2016–2026 test, each starting flat.
  9. **Leverage:** none; Sharpe uses daily returns, rf=0, `sqrt(252)`.
- **Consequences:** A uses an ex ante, testable universe. D=10 remains the
  research/QA convention; a point-in-time D=10 proxy is deferred. The backtest
  panels are saved under distinct `backtest_*` names. Any later change to
  these rules requires a new decision entry.

---

## D-010 · Idea C baseline conventions

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** Idea C tests calendar-spread mean reversion. A fixed contract
  pair rolls, so the raw spread level is not a continuous signal series. The
  baseline must define the signal series explicitly while keeping the traded
  instrument and P&L unchanged.
- **Decision:**
  1. **Continuous index:** additive price-change chaining. On the first pair
     date, initialize each leg index at that date's observed settle. Thereafter
     add each contract's own `settle_t - settle_{t-1}` (within the contract).
     On a roll date use the new pair's contract-level changes; never difference
     old and new spread levels.
  2. **Signal-only:** `spread_index` is used only to compute z-scores. The
     backtest still trades the raw dollar spread; P&L is the engine's
     contract-level mark-to-market. This is not a back-adjusted price for the
     main results.
  3. **Missing/zero:** a missing change holds the corresponding leg index and
     sets the spread index to NaN for that date. Zero previous settle is
     flagged and treated as missing. Negative settles are supported by the
     additive construction. No raw price is forward-filled.
  4. **Signal:** dollar z-score with L=20, `min_periods=16`, `ddof=1`,
     `std<=0 -> NaN`. Entry when z crosses ±2; exit when z crosses 0. The state
     machine updates on the last trading day of each week, uses the engine's
     trading calendar, holds through NaN windows, and emits at most one target
     per root. `evaluation="daily"` is deferred until the engine supports it.
  5. **Instrument:** K=5 main pair (nearest two eligible contracts), 1:1 dollar
     spread, 24 commodities, 5 bps per leg, equal-weight active roots.
  6. **Baseline:** weekly v0; energy 1992–2013 sanity check first, then full
     1986–2026 with 1986–2015 train / 2016–2026 test. Honest negative results
     are reported.
  7. **Deferred:** daily evaluation, log spread, adjacent pairs, rolling OLS
     hedge ratio, Kalman replication, carry/momentum controls, liquidity
     thresholds, 100/200 windows.
- **Consequences:** The continuous index is a signal-construction object, not a
  back-adjusted price. Any later change to the index construction or the state
  machine requires a new decision entry.

---

## D-011 · Idea C rolling-OLS hedge-ratio variant

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** The 1:1 C baseline is a negative result. Before abandoning the
  idea, test whether a time-varying hedge ratio improves the same
  mean-reversion signal.
- **Decision:**
  1. **Estimation:** rolling OLS on the levels of the continuous leg indices,
     `near_index = a + h·far_index + e`; `h = Cov(near, far) / Var(far)`.
     Window 60 trading days, `min_periods=60`; 20/120 days are robustness.
  2. **Validity:** `h` must be finite and positive. Invalid `h` makes the
     hedge index NaN and forces `target=0` (flat); the last valid `h` is not
     carried forward. No cap in the main experiment; extreme values are
     reported and capped only as a robustness check.
  3. **Signal:** hedge index `p_t = near_index_t − h_t·far_index_t`; same
     state machine as C (L=20, ±2 entry, 0 exit, weekly evaluation, 80%
     valid observations).
  4. **Trading:** strict weekly rebalancing to the current `h`: near units =
     target, far units = `−target·h_t`; if `h` changes, the difference is
     traded. Pair rolls use the current `h` on the roll date.
  5. **Costs:** the first experiment uses 0 bps and compares gross-to-gross
     with the 1:1 baseline at 0 bps. A 5 bps run follows only if the gross
     hedge result is materially better.
  6. **Universe:** all 24 commodities, main pair; energy 1992–2013 sanity
     check; full 1986–2026, train 1986–2015, test 2016–2026.
  7. **Robustness:** returns-based `h`, 20/120-day windows, and a cap on
     extreme `h` are separate checks. A Kalman filter remains deferred.
- **Consequences:** The hedge-ratio variant is a separate instrument from the
  1:1 C baseline and is not merged into the main C result. Because `h_t`
  changes, the hedge index can jump when the weight changes; the experiment
  must report the `h` distribution and change magnitude. If strict ratio
  rebalancing adds too much turnover, the hold-at-entry variant is a separate
  robustness experiment.

---

## D-012 · Kalman hedge-ratio variant and C close-out

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** The rolling-OLS hedge ratio did not improve C. The paper uses a
  dynamic linear model with a Kalman-filtered time-varying hedge ratio; test
  that model before closing the idea.
- **Decision:**
  1. **Model:** `near_index_t = beta_0,t + beta_1,t·far_index_t + eps_t`;
     `beta_t = beta_{t-1} + w_t`; `h_t = beta_1,t`. Prior
     `beta_0 = [0, 1]`, large diagonal covariance.
  2. **Variance estimation:** observation variance from the residual variance
     of an OLS fit on the trailing 252 observations; process-to-observation
     ratio `q` selected from `1e-9 … 1e-1` by the Kalman log likelihood every
     60 observations; `W = qV·I`; 252-observation warm-up; `h>0` required;
     no cap.
  3. **Signal and trading:** same C state machine (L=20, ±2 entry, 0 exit,
     weekly), strict weekly h rebalancing, 0 bps gross first; 1:1 and
     rolling-OLS at 0 bps are the comparison.
  4. **Result:** aggregate full gross +0.98%, vol 8.9%, max drawdown −28.9%,
     turnover 28.3×; implied 5 bps net about −1.8%/yr full and −2.5%/yr test.
     Per-root paper sample (1992–2013): NG +1.34% / Sharpe +0.31, CL −0.79% /
     −0.26; the paper's WTI strength is not reproduced. CL's worst day is
     2020-04-20 (−48.4% of average gross), while its 2020 calendar-year
     contribution is +10.0%; no data are excluded or capped.
  5. **Close-out:** C is closed as a **mixed/negative** result. Do not build a
     daily paper-replication branch. A genuine 5–21 day mean-reversion edge
     should survive weekly sampling in some form; its absence, together with
     the paper's large commodity × maturity × MA-window grid and its own
     weak significance in many combinations, suggests the reported Sharpe >2
     is selection/overfitting rather than a robust effect.
- **Consequences:** `src/kalman.py` and its tests are the code deliverable;
  results live in `docs/PROGRESS.md` and `docs/HANDOFF.md`, not a new
  notebook. C uses LOG-0013–0018 (baseline), LOG-0022–0024 (hedge ratio), and
  LOG-0026 (Kalman/close-out). If a daily CL/NG replication is ever revisited,
  it must be a separate pre-registered project with engine daily-rebalance
  support.

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

---

## D-013 · Curve-momentum / basis-momentum baseline (D)

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** A/B/C are closed as negative or mixed-negative. Idea D is the
  next signal family: within-commodity curve momentum. The signal is
  mathematically basis-momentum: the difference between the trailing returns
  of the near and far rank slots (Paschke, Prokopczuk & Wese Simen 2020;
  Boons & Porras Prado 2019). The baseline must reuse the K=5 panel and the
  event-loop engine, and must not change A/C behavior.
- **Decision:**
  1. **Universe:** N=2, the main pair's current `rank_near` / `rank_far`;
     no liquidity filter; all 24 commodities.
  2. **Signal:** 12-month formation; each root's last pair date in a month is
     its month-end; build a roll-adjusted rank return index from `ret_rank`
     by compounding `1 + ret_rank`, skipping NaN and negative-price/broken
     days; require at least 80% valid returns in the window; a window
     containing `negative_price` or `ret_rank <= -1` is invalid. Score =
     `mom_near - mom_far`; target = sign(score), 0 if either mom is missing
     or the score is 0.
  3. **Timing:** signal at month-end close, fill at t+1 close. The month-end
     target is forward-filled to every trading date until the next month-end
     so mid-month rolls keep the position. A missing month-end score sets the
     next month's target to 0.
  4. **Positions and costs:** ±1 units on the two legs; equal-weight across
     active roots; 5 bps per leg; report gross and net.
  5. **Sample:** full 1986–2026; train 1986–2015; test 2016–2026.
  6. **First result (K=5, monthly):** full gross +0.55%/yr, net −0.99%/yr,
     net Sharpe −0.04, max drawdown −34.8%, turnover 16.1×; train gross
     +0.85%, net −0.65%; test gross −0.28%, net −1.89%. Static always-+1
     gross +0.35% / net −0.84%, turnover 11.4×; D's gross is slightly higher
     but its net is worse. Monthly net Sharpe: full −0.90, train −0.61, test
     −1.66; block-bootstrap t-stat full −5.87, test −5.41. The gross result is
     weak and not robust out of sample; 5 bps/leg costs turn it negative. This
     is a documented negative/mixed baseline, not a tuning target.
  7. **Deferred:** N=4, weekly/6-month variants, liquidity thresholds,
     inverse-vol, decay, D-vs-A and carry-regime diagnostics, H. `D-x`
     (cross-sectional basis-momentum) is a separate backlog item: rank
     commodities by BM, long the top bucket and short the bottom bucket. It
     must not be mixed into this baseline.
- **Consequences:** The monthly rebalance helper is shared by the signal and
  engine and is reusable for H. `src/signals.py` gains
  `CurveMomentumParams` / `curve_momentum_signal`; `src/curve.py` gains
  `monthly_rebalance_dates`; `src/backtest.py` accepts
  `rebalance="last_trading_day_of_month"` without changing weekly behavior.
  The D notebook is `06_curve_momentum.ipynb`. Do not use the 2016–2026 test
  sample for tuning; A/B/C remain closed.

---

## D-014 · Idea ownership and Nelson–Siegel back in scope

- **Status:** accepted
- **Date:** 2026-10-19
- **Merge note:** written on branch `jiaheng/backtest-v2` as D-010 and
  renumbered to D-014 on merge (D-013 was already used for D on main). In the
  meantime C was implemented and closed on main by Tian (D-010–D-012). C's
  ownership below is therefore historical; the daily-rebalance engine (D-015)
  is what D-012 names as the prerequisite for any daily CL/NG replication.
- **Context:** Two team members implement signal families in parallel on the
  shared data layer and backtest engine. `docs/project_brief.md` §4 had
  excluded E (Nelson–Siegel) because fitting 3 parameters to 4 contracts leaves
  one degree of freedom.
- **Decision:**
  1. **Tian Tian:** A (carry) and D (curve momentum, Paschke et al. 2020).
  2. **Jiaheng Han:** C (mean reversion, Lubnau & Todorova 2015) and E
     (curve dynamics, Bianchi, Fan, Miffre & Zhang 2023). Both are
     fitted-parameter signals: C fits a time-varying hedge ratio between legs;
     E fits the Nelson–Siegel level/slope/curvature of the curve.
  3. E is back in scope. It trades daily changes in fitted factors (as in
     Bianchi et al., who also fit the nearest 4 contracts), not fit residuals;
     the one-degree-of-freedom concern must be addressed explicitly in the E
     notebook.
- **Consequences:** C and E reuse the D-008 common pair and D-009 backtest
  conventions unless a separate robustness experiment is documented. Each
  owner adds signals in `src/signals.py` and a dedicated notebook; shared
  modules (`src/panel.py`, `src/backtest.py`) change only with a new decision
  entry.

---

## D-015 · Daily rebalance option in the engine

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** D-009 fixed weekly rebalancing. C (Lubnau & Todorova 2015) is an
  event-driven daily band strategy with 2–21 day holds, and E (Bianchi et al.
  2023) holds for one day. A weekly schedule would change both strategies
  rather than reproduce them.
- **Decision:** `BacktestConfig.rebalance` accepts `"daily"` in addition to the
  default `"last_trading_day_of_week"`. Under `"daily"` every trading day is a
  rebalance date; all other D-009 rules (t-close signal, t+1 fill, roll on
  pair change, costs on net traded legs, missing/stale handling) are unchanged.
- **Consequences:** The default stays weekly, so A results are unaffected. C
  and E report daily rebalancing as the main result and weekly as a
  comparability check against A/D. Covered by
  `test_daily_entry_is_next_trading_day` and
  `test_daily_flip_fills_next_day_weekly_waits`.

---

## D-016 · Backtest v2: holdings-based simulator with layered costs

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** The v1 engine (`src/backtest.py`, D-009) reports one net return
  with a flat 5 bps per leg and no notion of capital, so it cannot show how
  costs split into spread, fees and impact, how they scale with strategy size,
  or how a signal decays across horizons. C, D and E also need daily trading
  and non-1:1 legs.
- **Decision:** Add a parallel v2 stack (`src/specs.py`, `marks.py`,
  `sizing.py`, `costs.py`, `simulate.py`, `horizon.py`, `report.py`); v1 is
  kept unchanged for A's original benchmark.
  1. **Timing:** signal at the t settle, fill at the t+1 settle, first P&L
     t+1 -> t+2. Holdings are (fractional) contracts; P&L = contracts x point
     value x settle change; returns = P&L / capital (non-compounding).
  2. **Pairs:** `build_backtest_panel(rank, d=5, k=5)`. The last trading day is
     on the exchange calendar, hence ex ante; with `d=None` CL/CO/NG legs
     expire inside the holding window.
  3. **Sizing:** gross budget 1/N per active root (N = 5-day max of active
     roots, so ICE trading on US holidays does not concentrate the book),
     inverse spread volatility, or liquidity weight dollar_ADV ** alpha
     (thinner leg, lagged; alpha = 0.5 default); equal weight is the default
     scheme; equal-notional legs by default; k overlapping
     sleeves; ex-ante liquidity flag (lagged 20-day ADV of the thinner leg),
     an illiquid date is an explicit exit.
  4. **Holding rules:** no signal row = keep holdings; explicit flat = exit;
     resize only on target/pair change or > 25% budget drift; blocked fills
     keep holdings; expired contracts close at the final settle; > 5 invalid
     sessions force an exit at the last mark.
  5. **Costs (per side, every leg):** half-spread 0.5 tick widened by
     (10,000 / ADV)^0.18, one half-spread per matched listed-spread order;
     USD 1.5 fee per contract; square-root impact Y = 0.5 on quantity above
     the first lot. Sources in `docs/transaction_costs.md`.
  6. **Time series only:** every strategy and diagnostic is per commodity on
     its own history (per-root time-series IC, own-history expanding bins).
     No cross-sectional ranking: settlement times differ across exchanges and
     ~20 markets is too thin a cross-section.
- **Consequences:** Results are reported as gross / − half-spread / − fees /
  − impact, plus turnover, per-root costs, horizon decay, k sweep and a
  capacity curve. Contract specs live in `data/metadata/contract_specs.csv`.
  v1 and v2 numbers for A differ (weekly vs on-change rebalancing, cost model,
  pair rule) and are not directly comparable.

---

## D-017 · v2 hedge-ratio and multi-leg extensions; B within-root exception

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** D-016 defined v2 as a two-leg, time-series-only simulator.
  C's rolling-OLS and Kalman variants need a time-varying hedge ratio; B's
  adjacent-carry pre-test needs explicit multi-leg rows and ranks adjacent
  maturity spreads within one root. Without an extension those variants
  cannot run through v2 without ad-hoc leg tables.
- **Decision:**
  1. v2 leg targets may carry an optional `hedge_ratio` column. Near units
     are `sign(target)`, far units are `-sign(target) * h`; `h` is a contract
     ratio, not a multiplier on the price ratio. Invalid or non-positive h
     produces an explicit flat row.
  2. v2 gains a generic explicit-row builder, `sizing.legs_from_rows`, for
     multi-leg targets. It nets duplicate contracts, requires one non-flat
     group per `(date, root)`, and requires explicit flat rows for exits.
  3. The on-change resize key includes an optional `resize_key` column in
     addition to `(group_id, target)`, so weekly hedge-ratio changes and B
     composition changes trigger a resize without daily notional churn.
  4. B's adjacent-carry ranking is a narrow exception to D-016's
     time-series-only rule: it ranks the three adjacent maturity spreads
     within one root on the same exchange, not commodities across the panel.
     It must be reported separately and may not be used to justify
     cross-commodity ranking. B runs with `execution="legs"` because the
     spread-order cost pairing is not group-aware.
- **Consequences:** C rolling-OLS/Kalman and B can run through v2; A, D and
  C 1:1 stay two-leg and use the default path. The extension is additive;
  existing v2 signals and the 10–14 notebooks keep their interface.

---

## D-018 · v2 re-run conventions for A/D/C/B

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** The team is re-running the validated A/D/C ideas and the C
  hedge / B variants through v2. The universe, cost model and execution
  conventions must be fixed before looking at results.
- **Decision:**
  1. **Universe and pairs:** `panel.build_backtest_panel(rank, d=5, k=5)`;
     `min_adv=100` on the thinner leg; all roots. B keeps its original
     raw-rank adjacent universe and its own `d=None` main-pair validation.
  2. **Capital and sizing:** capital USD 10m; equal 1/N budget;
     equal-notional legs except hedge-ratio signals; fractional contracts;
     `resize="on_change"`.
  3. **Costs:** v2 three layers (half-spread, USD 1.5/contract fee,
     square-root impact); no flat 5 bps translation.
  4. **Calendar strategies:** A uses the v2-native daily on_change path with
     `rebalance_band=0.25`. C 1:1 and C hedge/Kalman use a large band so
     only weekly target changes, weekly-snapped h changes and pair rolls
     resize. D uses a large band so only monthly target changes and pair
     rolls resize. B uses weekly rebalance dates plus main-pair change dates
     and a large band.
  5. **C hedge/Kalman:** h is daily but snapped to weekly evaluation dates;
     pair-change dates use the current-day h; invalid h is flat.
  6. **B:** `execution="legs"`; budget 1/N per root-date; net shared
     contracts; one group per root-date.
  7. **Reporting:** full 1986–2026, train 1986–2015, test 2016–2026; train
     and test are post-hoc slices of the full simulation, not flat restarts.
     Gross and each cost layer are reported separately. Do not tune on test.
- **Consequences:** Results are v2-native and not directly comparable with
  v1's 5 bps/leg, weekly/monthly, 1:1-contract numbers. The comparison doc
  must label the differences by construction.

---

## D-019 · v2 re-run results are the official results

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** v1 and v2 are different accounting systems. The v2 re-runs of
  A/D/C/C-hedge/B are complete under D-018. The project needs one final
  reported set of numbers; the user chose v2 as the official result while
  keeping v1 as a historical baseline.
- **Decision:**
  1. Official/final result tables use v2: `notebooks/08_v2_rerun.ipynb`,
     `output/v2_rerun/comparison.csv` and `docs/v1_v2_comparison.md`.
  2. v1 notebooks `02_carry`, `03_mean_reversion`, `05_b_pretest`,
     `06_curve_momentum` and the v1 result sections remain in the repo as
     historical baselines. They must be labeled `v1`; they are not rewritten.
  3. Headline tables report v2 gross and the three cost layers. Do not mix
     v1 and v2 numbers in the same table, and do not compare v1 net with v2
     all-in net as if they used the same accounting.
  4. The closed/negative conclusions do not change: A/B gross is negative;
     D/C/C-hedge gross is weak and all-in net is negative. v2 is the final
     presentation, not a rescue.
- **Consequences:** README/HANDOFF/PROGRESS/onboarding and notebook 08 use
  v2 as the final result; v1 is historical. No code or locked data
  convention changes. No push.
- **Note (2026-10-19):** D-020 retires the old v1/aggregate notebooks from
  the working tree and replaces notebook 08 with per-idea notebooks. The
  v1/v2 result hierarchy and the "v2 is official" rule are unchanged.

---

## D-020 · One notebook per trading idea; retire superseded notebooks

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** The v1 and v2 notebooks duplicated ideas, mixed historical and
  official numbers, and gave each idea several notebooks. The user approved a
  single notebook per idea with a fixed presentation.
- **Decision:**
  1. The notebook layout is: `00_data_audit`, `01_panel_build`,
     `10_idea_a_carry`, `11_idea_b_adjacent_carry`,
     `12_idea_c_mean_reversion` (1:1, rolling OLS, Kalman subsections),
     `13_idea_d_curve_momentum`, and `14_idea_e_nelson_siegel`. Exactly
     one notebook per idea.
  2. Every idea notebook runs only its own strategy on v2 and shows:
     (a) cumulative PnL after each cost layer; (b) a two-panel position
     figure with a month-end signed per-root heatmap and gross
     exposure/turnover; (c) one full-sample all-in net Sharpe. C reports one
     Sharpe per pre-registered variant, with 1:1 as the idea-level headline.
  3. Delete notebooks 02–08 from the working tree. Historical v1 methodology
     and results live in docs and git history; `docs/notebook_history.md`
     records purpose, replacement and recovery commands. Do not recreate
     retired notebooks.
  4. v2 remains official (D-019). D-019 clause 2 (keep the v1 notebooks in
     the working tree) is superseded by this decision; the result hierarchy
     is unchanged.
  5. Position semantics: `+` = long nearest-expiry leg / short the rest,
     `-` = the opposite, `0` = flat. Heatmap colour is signed gross notional
     divided by capital. Net signed dollar exposure is not used because a
     calendar spread is dollar-neutral by construction.
- **Consequences:** The working tree has five idea notebooks (10–14) instead
  of seven historical ones. v1 numbers remain in docs and are recoverable
  from git. No data/backtest convention changes.
- **Note (2026-10-20):** D-024 adds E as `14_idea_e_nelson_siegel` after the
  cloud E work was merged; the layout is now five idea notebooks.

---

## D-021 · Idea E: Nelson–Siegel curve-dynamics replication protocol

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** Bianchi, Fan, Miffre & Zhang (2023, JBF 154) fit a
  Nelson–Siegel (NS) curve each day to the nearest four contracts of each
  commodity and trade the sign of the one-day change in the slope (S) and
  curvature (C) betas, holding for one day (gross Sharpe 1.41 for S; net
  0.44–1.04; post-GFC net 0.20). Three facts shape the protocol: (i) λ_t is
  set by rule, not estimated, so with four contracts and three betas the fit
  is a one-degree-of-freedom OLS and ΔβS is close to a fixed linear
  combination of the four price changes; (ii) their non-NS benchmark
  ΔS_t = Δ(F¹ − F⁴) already earns Sharpe 1.31 (Table 10), so the NS
  increment must be measured, not assumed; (iii) their trades are "set up at
  the end of day t and implemented for one day", i.e. filled at the same
  settle that produced the signal, which this project treats as not
  tradable (D-009, D-015).
- **Decision:**
  1. **Order of work.** (a) Replicate the paper's S and C strategies as
     specified; (b) compare the paper's timing with the tradable timing;
     (c) run the non-NS benchmark ΔS_t; (d) only if the edge survives a t+1
     fill, run the filtering/shrinkage extensions in item 10.
  2. **Contract set.** Per root and day, the eligible contracts among M1–M4
     are those with a tradable settle, not in their delivery month, and
     before their last trading day (the paper holds a contract until the
     last trading day before the front enters its maturity month).
     - Snapshot OLS (main replication): fit only when exactly four eligible
       contracts exist. Otherwise no fit and an explicit flat target for that
       root-day (three contracts would be an exact, zero-dof fit).
     - Kalman/state-space variants (item 10): update with whatever eligible
       contracts exist (minimum three), dropping missing rows from the
       measurement equation.
     - The number of days lost to the four-contract rule is reported per
       root.
  3. **Maturity.** M = calendar days from t to the contract's last trading
     day, divided by 365.25/12 (months). The last trading day is on the
     exchange calendar and therefore ex ante. For expired contracts it is the
     contract's last appearance in the generic M1–M4 roll (Bloomberg rolls at
     expiry); for contracts still trading at the end of the extract
     (`is_censored`), it is the delivery-month start plus the root's median
     historical offset. Robustness: maturity to the delivery-month start.
  4. **Fit.** Price levels (as in the paper, Eq. 1), λ_t = 1.7933 / M̄_t
     where M̄_t is the mean maturity of the fitted contracts (the curvature
     loading peaks at λM ≈ 1.7933; paper footnote 4); betas by OLS. Store
     βL, βS, βC, λ, R² and the R² of the L+S and L+C sub-models (paper
     Table 3: 96.5%, 37.5%, 82.7% on average).
  5. **Signals.** S: sign(ΔβS,t); C: sign(ΔβC,t), with Δ between
     consecutive fitted days of the same root. Days on which the fitted
     contract set changed (rolls) are flagged; the main replication keeps
     them (as the paper does), a robustness run drops them.
  6. **Instruments and weights.** S trades the slope spread of the first
     and fourth fitted contracts (long 1st / short 4th when ΔβS > 0), equal
     notional legs. C trades the butterfly short 1st / long 2nd / short 4th
     when ΔβC > 0 with leg weights |w1| = |w4| = ½|w2| (paper: 1/(4N),
     1/(2N), 1/(4N)). This deviates from the D-008 common pair by design;
     the D-008 pair is a robustness run for S.
  7. **Timing.** Main (tradable): signal at the t settle, fill at the t+1
     settle, first P&L t+1 -> t+2, one-day holding, `rebalance="daily"`
     (D-015). The paper's timing, window [t, t+1], is reported only as an
     execution-free diagnostic and is labelled not tradable.
  8. **Aggregation.** Time series per root; no cross-sectional ranking
     (settlement times differ across exchanges). Equal weight across active
     roots by default, liquidity weight (dollar ADV^½) as robustness. The
     paper's equal split of capital between the long and short sides is not
     imposed and the difference is stated in the results.
  9. **Samples.** (i) Replication: the paper's 21 commodities (our 24 minus
     CO, NG, SB) from 1992-01-02 to 2019-06-28; (ii) full panel: 24
     commodities, 1986–2015 train / 2016–2026 test. No parameter is chosen
     on the test sample.
  10. **Extensions (conditional on item 1d).** Random-walk state-space NS
      (Kalman filter; equivalent to shrinking each day's fit toward the
      previous filtered betas), AR(1)/VAR(1) dynamic NS with the forecast
      E[Δβ_{t+1} | F_t] as the signal (Diebold–Li; Grønborg–Lunde), and
      3/5-day moving averages of ΔβS (paper Table 9). Noise variances and
      AR parameters are estimated on the training sample or an expanding
      window, never on the full sample.
  11. **Costs and reporting.** v2 three-layer costs (D-016), plus the
      paper's TC1–TC3 scenarios for comparability. Report the full v2 set:
      cost layers, turnover, marginal and cumulative horizon decay, k sweep,
      and the per-commodity block-bootstrap IC of ΔβS.
- **Consequences:** New `src/nelson_siegel.py` (eligible set, maturities,
  daily fit, signals), a multi-leg weight path in `src/sizing.py` for the C
  butterfly and the 1st/4th spread, and `notebooks/14_idea_e_nelson_siegel.ipynb`.
  The 1-dof critique of `docs/project_brief.md` §4 is addressed by items 1c,
  4 and 10. Changing any item requires a new decision entry.

---

## D-022 · Idea E results: lambda as a causal hyperparameter, $1m capital, E closed

- **Status:** accepted
- **Date:** 2026-10-19
- **Context:** D-021 fixed the replication protocol. Two refinements were
  requested before running it: treat the NS decay λ as a hyperparameter chosen
  among causal rules on a validation sample, and size the framework for a
  USD 100k–1m book (below that many contracts cannot be bought in whole lots).
- **Decision:**
  1. **λ rules** (`nelson_siegel.LAMBDA_RULES`), all causal: `paper`
     (1.7933 / mean maturity), `fixed_2/4/6` (curvature peak at 2/4/6 months),
     `rolling_ssr` (per root, grid λ minimising the summed fit SSR over the
     previous 252 fitted days, day t excluded). Amends D-021 item 4.
  2. **Selection:** the highest tradable gross Sharpe (t+1 fill, daily, equal
     weight) on the validation sample 2006-01-01–2015-12-31; the test sample
     2016–2026 is read once for the selected rule.
  3. **Capital:** `SimConfig.capital` default and the notebooks use USD 1m;
     capacity grids span USD 100k–100m. `SimConfig.round_lots=True` rounds
     each leg to whole contracts and skips spreads with a leg below half a
     lot; `capacity_curve` assumes fractional contracts.
  4. **Paper costs:** `costs.paper_scenarios()` reproduces Bianchi et al.'s
     TC1–TC3 per side (USD 0.75; 0.835 bp of notional via
     `CostParams.proportional_bps`; USD 0.75 + 1/8 tick), legs costed
     individually, no impact.
  5. **Result and close-out:** the paper's S effect replicates at its own
     timing (21 commodities, 1992–2019: gross 3.55%/yr, Sharpe 2.03 vs the
     paper's 1.77% / 1.41) and vanishes with a one-day lag (gross −0.18%/yr,
     t = −0.6; `[t+1, t+2]` signed return t = −0.1). The non-NS ΔS benchmark
     behaves the same, all λ rules have validation Sharpe between −0.29 and
     +0.02 (`rolling_ssr` selected; test gross +0.15%/yr, t = 0.2), and the C
     butterfly is also flat (gross −0.32%/yr). Turnover is ~230×/yr, so even
     the paper's cheapest TC1 gives −0.8%/yr. **E is closed as not
     tradable**; per D-021 item 1(d) the Kalman / dynamic-NS extensions are
     not run.
- **Consequences:** `notebooks/14_idea_e_nelson_siegel.ipynb` is the E record;
  The E notebook uses USD 1m. Revisiting E requires intraday or
  trade-at-settlement data to test whether the same-settle effect is
  executable.

---

## D-023 · Idea E follow-ups: fit significance, paper-timing costs, Kalman A/B

- **Status:** accepted
- **Date:** 2026-10-20
- **Context:** After D-022, three questions remained: does each NS component
  describe the curve significantly better, does the paper's same-settle
  strategy survive costs or smoothing, and does a Kalman dynamic NS improve on
  the daily OLS snapshot.
- **Decision:**
  1. **Fit significance:** per-commodity 21-day moving-block bootstrap of
     daily fit statistics; nested models compared with paired bootstraps on
     adjusted R² (in-sample R² cannot fall when a regressor is added) and on
     leave-one-contract-out R² (median; heavy tails). Result: slope helps on
     22–24/24 commodities in every metric; curvature helps out of sample on
     11/24 and hurts on 9/24 (seasonal curves: LC, LH, FC, LB, XB, SB, S, CT,
     NG).
  2. **Paper timing with costs:** `simulate.same_settle` re-dates targets so
     the engine fills at the signal's own settle (diagnostic only). Paper
     sample, paper λ, USD 1m: gross 3.11%/yr (Sharpe 1.95); paper TC1–TC3 net
     1.2–2.5%/yr; v2 half-spread alone takes it to −0.04%/yr and fees to
     −1.35%/yr. k-day smoothing lowers turnover but dilutes the one-day edge
     faster; no k is positive net of spread and fees at either timing.
  3. **Kalman A/B:** random-walk state-space NS (`src/ns_kalman.py`), noise
     scaled by the previous mean price, (r, q) chosen per root by one-step
     log likelihood on 1986–2005, A/B on 2006–2026 with paired block
     bootstraps. Kalman is better on leave-one-out fit (24/24) but worse on
     one-step-ahead curve forecasts (20/24), and its ΔβS signal is worse at
     the tradable timing ([t+1, t+2] −0.57 bp, t = −1.7). Adoption rule
     (significant improvement on most commodities) is not met: **not
     adopted**.
- **Consequences:** E stays closed as not tradable (D-022). For curve-shape
  descriptors used elsewhere, slope is robust; curvature only for smooth
  curves.

---

## D-024 · Merge idea E into the D-020 notebook layout

- **Status:** accepted
- **Date:** 2026-10-20
- **Context:** The cloud branch merged the idea E work (PR #1 and follow-ups)
  while local `main` had D-019/D-020 and notebooks 10–13. Decision IDs, log
  IDs and notebook numbers collided.
- **Decision:**
  1. Keep local decisions D-001–D-020 and the D-020 notebook layout.
  2. Import the idea E decisions as D-021 (protocol), D-022 (results) and
     D-023 (follow-ups); the E log entries are renumbered to LOG-0051–LOG-0053.
  3. Add idea E as `notebooks/14_idea_e_nelson_siegel.ipynb`; keep notebooks
     02–08 retired (D-020) and do not restore `06_backtest_framework`.
  4. Port the E method additions (`simulate.same_settle`,
     `horizon.block_bootstrap_mean`, `report.execution_free_returns`,
     `report.return_summary`, `ns_kalman`) onto local v2 without removing
     the local position/Sharpe additions.
- **Consequences:** Local `main` now contains the cloud E work and the D-020
  layout. E remains closed as not tradable (D-022). A future idea notebook
  slot is 15.

---

## D-025 · Idea D signal-validity protocol

- **Status:** accepted
- **Date:** 2026-10-20
- **Context:** D is closed as a documented negative/mixed **trading**
  baseline. The user wants a separate **information** study: no transaction
  costs, no PnL rescue, only whether the D score predicts forward spread
  returns, how stable that relation is, and whether it is independent of
  static always-long, A carry and C mean reversion. The E validity tests
  (nested adjusted R², per-root block bootstrap, paired A/B) provide the
  template, but E's leave-one-contract-out R² does not transfer because D
  has only two legs.
- **Decision:**
  1. **Spec.** Keep D-013 fixed: 12-month formation, N=2 main pair, monthly
     root-specific month-end, `target = sign(score)`, D=5, no liquidity
     filter, `min_obs_frac=0.80`. No parameter grid and no main-spec
     selection in this phase. Formation 6/9/24, 12-1, weekly, N=4, liquidity,
     D=10 and score transforms are phase 2.
  2. **Returns.** Roll-adjusted rank-index near-minus-far forward return
     from `t+1` to the root's month-end `h` months later, `h = 1/3/6/12`.
     Same-close `t` to month-end is a timing diagnostic only. Fixed-pair
     dollar spread is optional robustness. All returns are gross; no costs.
  3. **Score.** Raw `score` is the primary predictor; `sign(score)` is the
     strategy comparison.
  4. **Controls.** At each D signal date, take month-end snapshots of A
     carry `score` and C z-score (the `score` column of
     `mean_reversion_signal`), plus static always-long. No look-ahead.
  5. **Checks.** Per-root rank IC/hit rate/expanding quintiles/predictive
     R²; horizon profile at 1/3/6/12 months; nested adjusted R² and
     residual IC versus static/A/C; stability by decade, carry sign and
     spread-volatility tercile plus rolling 36-month IC; placebo sign flip,
     within-root 6-month block shuffle, lags 1/3/6/12 and a future-score
     lead of 24 months.
  6. **Inference.** Per-root moving-block bootstrap; block 6 months main,
     12 months sensitivity; `n_boot=2000`; `min_obs=60` months; FDR within
     each metric/horizon family; max-|IC| noise benchmark from the shuffle
     null; roots are correlated and are never treated as independent trials.
  7. **Samples.** Full 1986–2026; subperiods 1986–1999, 2000–2009,
     2010–2026; validation 2006–2015; test 2016–2026 read once and never
     used for selection. Period-specific statistics require the forward
     endpoint to lie inside the period.
  8. **Verdict rule.** D is “valid independent information” only if the
     1-month raw-score IC is positive in a majority of roots, the aggregate
     mean IC has a CI excluding zero with per-root FDR positives not
     isolated to one or two roots, IC is stable across decades and
     carry/vol regimes, and the incremental IC after A/C/static has a CI
     excluding zero and is not economically trivial. Otherwise report “no
     independent information” or “subset/regime only”; do not rescue with
     parameter changes or costs.
  9. **Implementation.** `src/d_validity.py`, tests in
     `tests/test_d_validity.py`, and a validity section in
     `notebooks/13_idea_d_curve_momentum.ipynb` (no separate notebook).
- **Result (2026-10-20):** 1-month raw-score IC 0.049 (NW t 3.48; 79% of
  roots positive), but only 2/24 roots survive FDR (LC, W). IC rises with
  horizon (0.140 / 0.173 / 0.190 at 3/6/12 months). The expanding-quintile
  relation is non-monotonic. Stability is limited: 1986–1999 IC 0.013,
  high-volatility IC −0.007, rolling 36-month positive share 39%.
  Incremental adjusted R² is 0.007 for D and its CI includes zero; the
  residual-IC gain is 0.016 (18/24 roots positive, 2/24 significant).
  Timing spread is about 11 bp/month, but static always-long is also about
  11 bp/month. **Verdict: detectable but unstable information, largely
  overlapping with static/carry; not stable independent information.**
- **Consequences:** D's official trading result remains the negative/mixed
  v2 baseline (D-019). This decision does not change D-013, the v2 engine or
  the cost model. Parameter scans/response curves require a separate
  decision and must not use the test sample for selection.

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

## D-010 · Idea ownership and Nelson–Siegel back in scope

- **Status:** accepted
- **Date:** 2026-10-19
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

## D-011 · Daily rebalance option in the engine

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

## D-012 · Backtest v2: holdings-based simulator with layered costs

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

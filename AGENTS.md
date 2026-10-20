# AGENTS.md

This file is the entry point for any coding agent working in this repository.
Read it before changing code, data, notebooks, or docs.

## Read order

1. `README.md` — one-page project entry.
2. `docs/HANDOFF.md` — current state, key numbers, open questions, next step.
3. `AGENTS.md` — this file.
4. `docs/decisions.md` — locked research/data decisions.
5. `docs/data_dictionary.md` — raw and derived fields.
6. `docs/logs/INDEX.md` and the latest entries in `docs/logs/AGENT_LOG.md`.
7. `docs/project_brief.md` or `docs/research_notes.md` — detailed background.

## Project in one paragraph

The project studies commodity futures calendar spreads using a Bloomberg bulk
export: 24 commodities × 4 nearby generic ranks (M1–M4) × 4 fields
(`PX_SETTLE`, `PX_VOLUME`, `OPEN_INT`, `FUT_CUR_GEN_TICKER`), daily,
1986-01-01 to 2026-10-13. The generic ranks are slots, not contracts. Every
roll date all four ranks shift together by one contract. The contract code
column lets us reconstruct each real contract's full life and compute returns
without mixing two contracts on a roll date.

## Hard invariants

1. **M1–M4 are slots, not contracts.**
   - Never compute a return by differencing generic M1 prices across a roll.
   - Compute contract-level returns and map them back to ranks.
   - On a roll date, the new M1's previous-day price is the old M2 price.

2. **Pair eligibility is locked.**
   - Do not hold a contract in its delivery month.
   - Exit at least 5 trading days before the delivery-month start.
   - Require `days_to_last_trading > D`, with `D = 10` for main results.
   - `D = 5` and `D = 20` are robustness checks only.
   - Do not change these values without a new entry in `docs/decisions.md`.

3. **Spread conventions are locked.**
   - `spread_dollar = P_T1 - P_T2` is the primary traded/P&L measure.
   - `spread_log = log(P_T1/P_T2)` is a reference/signal measure.
   - `spread_log` is valid only when both prices are positive; otherwise NaN
     plus a `negative_price` flag.
   - Do not back-adjust price levels for the main results.

4. **Data hygiene.**
   - Raw prices are never forward-filled.
   - Missing contract code means the row cannot be aligned; drop it.
   - Missing volume/OI is missing, not zero.
   - Do not delete the CL 2020-04-20 settlement of -37.63. It is real.
   - Do not splice XB with legacy HU, or LB with LBR.

5. **Public repository.**
   - Never commit raw Bloomberg CSV/XLSX, paper PDFs, `Project.pdf`,
     `calendar-spread-brief.html`, processed parquet, or secrets.
   - `data/raw/README.md` and `paper/README.md` explain where local files go.

## Repository conventions

- All reusable logic lives in `src/*.py`. Notebooks are narrative and call
  functions; they must not contain long transformations or loops.
- Notebooks are bilingual: Chinese narrative and explanation, English technical
  terms and code identifiers. `README.md`, `docs/HANDOFF.md`,
  `docs/research_notes.md`, `docs/onboarding.md`, and `docs/project_brief.md`
  are in Chinese; technical docs and agent logs are in English.
- Keep notebook outputs concise: `.head()`, summary tables, a few figures.
  Never print a million-row DataFrame.
- Use `python -m pytest -q` for tests. Tests must pass without raw data
  (synthetic fixtures only); integration tests are opt-in.
- Run notebooks from the repo root. `src.config` resolves paths from the repo
  root, not from the current working directory.
- Data paths:
  - raw: `data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv`
  - metadata: `data/metadata/commodities.csv`
  - processed: `data/processed/*.parquet`
  - output: `output/`

## Agent logging (mandatory)

Every material change must be logged. Material means: file/code/doc/test/
notebook edits, data-generation runs, dependency changes, git setup, commits,
pushes, or a failure that changes the plan.

1. Before starting, read `docs/logs/INDEX.md` and the last few entries in
   `docs/logs/AGENT_LOG.md`.
2. Append a new entry to `docs/logs/AGENT_LOG.md` using the format in
   `docs/logs/_template.md`.
3. Update `docs/logs/INDEX.md`.
4. Stage the log together with the change; the commit must include it.
5. Put `Log: docs/logs/AGENT_LOG.md#LOG-XXXX` in the commit message.
6. Never rewrite committed entries. Corrections go into a new entry.

Read-only exploration can be summarized in one "Inspection" entry per phase;
do not log every `ls`.

## Commit conventions

- Logical commits, not one giant commit.
- Format: `<type>(<scope>): <summary>` (e.g. `feat(panel): ...`).
- Body: what changed, why, key decisions, validation, log reference.
- End every commit message with:

  ```text
  Log: docs/logs/AGENT_LOG.md#LOG-XXXX
  Co-Authored-By: Claude Code <noreply@anthropic.com>
  ```

- Push to `origin main` after each logical commit when collaborating.

## Backtest invariants

- The backtest uses the K=5 ex-ante universe (`d=None`); the D=10 research
  panels are kept unchanged. Do not use `last_trade_proxy` for backtest
  selection.
- Signal at t close; fill at t+1 close. Mark existing positions before
  executing pending orders. No same-close fills.
- Return is gross-notional with the lagged denominator; costs are 5 bps per
  leg of actual net traded notional.
- Do not use `is_censored`, episode `exit_date`/`holding_days`, or other
  ex-post fields as signals.
- The engine is `src/backtest.py`; add new ideas as signal functions in
  `src/signals.py` rather than editing the engine.

## Current phase

The data layer and the A/B/C/D baselines are complete: K=5 backtest panel,
per-contract mark state, `src/signals.py`, `src/continuous.py`,
`src/kalman.py`, `src/backtest.py`, `src/metrics.py`,
`src/a_diagnostics.py`, `src/b_pre_test.py`, and notebooks `02_carry`,
`03_mean_reversion`, `04_a_diagnose`, `05_b_pretest`, `06_curve_momentum`.
A, B, the C 1:1 baseline, and the C rolling-OLS hedge-ratio variant are
**negative results**. A and B are **closed**: no further parameter tuning or
rescue variants. The C Kalman variant is **mixed/negative**, and C is
**closed** and **merged into `main`**; notebook `03`, LOG-0013–0018
(baseline), LOG-0022–0024 (rolling OLS), and LOG-0026 (Kalman/close-out) are
the C slots. D (curve momentum / basis-momentum) is **closed as a
documented negative/mixed baseline**: the gross result is weak and the net
result is negative; the monthly rebalance support is shared with the engine
and reusable for H. Do not tune D on the 2016–2026 test sample. `D-x`
(cross-sectional basis-momentum) is a separate backlog item. The next phase
is H. Do not build a daily C paper-replication branch; if revisited, it is a
separate pre-registered project. Do not change the locked A/C conventions without a
new `docs/decisions.md` entry. Keep the panels reproducible from the raw CSV
and the notebooks.

## Questions / ownership

Repo owner: Tian Tian (`TianTian20021211`). If a decision is ambiguous, add it
to `docs/decisions.md` as "proposed" and ask the user before changing locked
conventions.

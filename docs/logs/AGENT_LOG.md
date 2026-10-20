# Agent Log

Append-only. See `README.md` for the protocol and `_template.md` for the format.

---

## LOG-0001 · 2026-10-17 15:30 · Phase 0 · Claude Code

**Goal:** Understand the raw Bloomberg extract and decide the data-cleaning and
research-panel design before writing any code.

**Actions:**
- Inspected project files and the Excel metadata sheets (`START_HERE`,
  `Tickers_For_Wizard`, `Universe_Details`, `Optional_Extras`,
  `Historical_Coverage`).
- Parsed the wide CSV into a long `date × commodity × rank` audit table.
- Checked date coverage, missing sentinels, contract-code formats, rank
  ordering, roll synchronization, contract lifecycles, price anomalies, stale
  runs, volume/OI missingness, and liquidity.
- Compared sampled Excel and CSV cells (60 rows × 385 columns; only date
  formatting differed).
- Tested `D=5/10/20` pair-selection mixes using the last observed date as the
  expiry proxy.

**Files changed:** none (read-only audit).

**Commands:**
- `python3` scripts that read the CSV/XLSX and print audit summaries.
- `git ls-remote` / `gh repo view` to inspect the empty public GitHub repo.

**Why:** To determine whether the proposed research panel could be built from
the raw extract and where the real data risks are.

**Validation / key findings:**
- 24 commodities, 96 generic series, 10,640 weekdays (1986-01-01 to
  2026-10-13); 128 all-blank US holidays.
- 6,735 real contracts; 950,626 contract-date observations; 0 duplicate
  contract-date; max gap ≤7 calendar days.
- 6,639 full-queue roll dates / 26,562 single-rank roll events; all four ranks
  shift together on every roll date; 0 partial rolls; each contract's rank is
  monotonic 4→3→2→1.
- Naive M1 returns on roll dates are contaminated: median absolute return on
  roll vs non-roll days is e.g. corn 2.97% vs 0.85%, live hogs 7.00% vs 0.80%,
  oats 4.24% vs 1.10%, WTI 1.84% vs 1.22%.
- Negative settlement only: CL 2020-04-20 = -37.63. No zero prices.
- 583 rows have settle but no contract code, mostly holidays/outages
  (2001-09-11, day after Thanksgiving, Columbus Day); discard from alignment.
- Volume/OI missing: ~16–20% overall, ~4% after 2000, much worse in 1986–1990.
- Stale runs: M1 max 4 sessions; M4 max 14 sessions (oats/rough rice).
- Liquidity: about 19 commodities pass a 5,000-contract trailing median for
  both legs recently; M2–M3 is much thinner historically (average ~7.8 names).
- Pair mix with D=10 (without the no-delivery-month rule) ≈78% M1–M2 /
  22% M2–M3; the no-delivery-month rule will shift more days to M2–M3 for
  grains/softs.

**Commit:** none (pre-repository).

**Next:** scaffold the public repo, write the collaboration/logging protocol,
then implement the panels.

---

## LOG-0002 · 2026-10-17 16:23 · Phase R · Claude Code

**Goal:** Scaffold the public repository, preserve the raw data locally, and
establish the documentation and agent-log protocol before implementation.

**Actions:**
- Created `data/raw`, `data/metadata`, `data/processed`, `docs/logs`, `src`,
  `notebooks`, `tests/fixtures`, `output`.
- Moved the Bloomberg CSV/XLSX from `data/` to `data/raw/` (not deleted).
- Generated `data/metadata/commodities.csv` (24 unique commodities from
  `Universe_Details`) and `data/metadata/raw_file_checksums.txt`.
- Copied the detailed Chinese README to `docs/project_brief.md`; wrote a new
  concise `README.md`.
- Added `AGENTS.md`, `CLAUDE.md`, `requirements.txt`, `.gitignore`.
- Added `docs/decisions.md` (D-001..D-008), `docs/data_dictionary.md`,
  `docs/onboarding.md`, and the `docs/logs/` protocol files.
- Added `data/raw/README.md`, `paper/README.md`, and `.gitkeep` placeholders.

**Files changed:**
- `README.md` — rewritten (concise Chinese entry)
- `docs/project_brief.md` — preserved detailed background
- `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `requirements.txt` — new
- `docs/decisions.md`, `docs/data_dictionary.md`, `docs/onboarding.md` — new
- `docs/logs/README.md`, `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`,
  `docs/logs/_template.md` — new
- `data/metadata/commodities.csv`, `data/metadata/raw_file_checksums.txt` — new
- `data/raw/README.md`, `paper/README.md` — new
- `data/processed/.gitkeep`, `output/.gitkeep` — new

**Commands:**
- `mkdir -p ...`
- `mv data/*.csv data/*.xlsx data/raw/`
- `python3` (openpyxl) to generate metadata and SHA-256 checksums
- `cp README.md docs/project_brief.md`

**Why:** The GitHub repo is public. Raw Bloomberg data and paper PDFs must stay
local. A teammate and their coding agent need a concise human README, a generic
agent entry point, durable decisions, a data dictionary, and an append-only
operation log.

**Validation:**
- `data/metadata/commodities.csv` has 24 rows.
- CSV SHA-256 `045293...7771`; XLSX SHA-256 `de9b...5b42`; sizes 20MB/25MB.
- `.gitignore` excludes raw data, PDFs, parquet, and output; `data/raw/README.md`
  and `data/processed/.gitkeep` remain trackable.

**Commit:** `chore(repo): scaffold public repository and agent collaboration protocol`; follow-up `docs: add project brief, data provenance, and paper reading list`

**Next:** initialize git, add the remote, commit the scaffold/docs, push, then
start Phase 1 (loader/parser).

---

## LOG-0003 · 2026-10-17 16:40 · Phase 1 · Claude Code

**Goal:** Implement the raw loader, contract-code parser, and rank-panel
construction; validate on a synthetic fixture and the full raw CSV.

**Actions:**
- Added `src/config.py` with repo paths, D/K constants, liquidity thresholds,
  month codes, and the negative-price event.
- Added `src/load.py`:
  - `read_raw_wide` parses the six-header-row CSV and validates tickers/fields.
  - `parse_ticker`, `normalize_contract_code`, `parse_contract_code` handle
    spaced roots, one- and two-digit years, and `.NA.`.
  - `build_rank_panel` builds the long `date × commodity × rank` panel with
    contract identity and audit flags.
- Added `tests/fixtures/make_synthetic.py` and the generated
  `tests/fixtures/synthetic_wide.csv` (2 commodities × 4 ranks × 13 dates;
  one simultaneous roll, missing values, `.NA.`, negative price, holiday).
- Added `tests/test_contract_parsing.py` and `tests/test_roll_logic.py`.
- Installed `pytest` 9.1.1 in the active environment (was missing).

**Files changed:**
- `src/config.py` — new
- `src/load.py` — new
- `tests/fixtures/make_synthetic.py`, `tests/fixtures/synthetic_wide.csv` — new
- `tests/test_contract_parsing.py`, `tests/test_roll_logic.py` — new

**Commands:**
- `python3 tests/fixtures/make_synthetic.py`
- `python3 -m pytest -q` → 9 passed
- `python3` full-data smoke test → 1,013,664 rows × 23 columns in ~4s;
  24 roots, 10,559 union dates, 0 parse failures, 583 code-missing rows,
  1 negative price (CL 2020-04-20), 25,511 roll flags.

**Why:** Phase 1 establishes the contract identity layer. Every later panel and
return calculation depends on correct parsing and not treating M1–M4 as fixed
contracts.

**Validation:**
- Fixture panel: 96 rows, 12 dates (holiday dropped), 8 roll events, all four
  ranks roll together, 0 duplicate contract-date, one code-missing row, one
  negative price.
- Full raw: 24 roots × 4 ranks; no parse failures; `.NA.` rows flagged.
- `pytest` 9 passed.

**Commit:** `feat(load): parse Bloomberg wide export and normalize contract metadata`

**Next:** Phase 2 — contract/return panels, roll-aware returns, QA assertions.

---

## LOG-0004 · 2026-10-17 16:55 · Phase 2 · Claude Code

**Goal:** Build the contract and return panels with roll-aware returns and QA
that proves the generic-slot trap is handled.

**Actions:**
- Added `src/curve.py`: trading calendar, contract calendar/expiry proxy,
  roll detection/validation, eligibility (no delivery month + D), nearest-two
  eligible pair selection with an adjacency guard, dollar/log/percentage
  spreads, and fixed-pair episodes.
- Added `src/panel.py`: contract panel, rank enrichment, contract-level
  returns, rank-return mapping, spread panel, parquet writer.
- Added `src/qa.py`: uniqueness, rank monotonicity, roll-queue validation,
  return-mapping check, contract-calendar check, delivery-month check, coverage/
  missing/stale summaries, and the known CL 2020-04-20 event.
- Added `tests/test_spread.py` covering contract/return panels, eligibility,
  pair adjacency, spread definitions, and negative-price log-spread handling.
- Fixed a QA edge case: `ret_naive` must not be compared with `ret_rank` when
  the previous rank row had a missing contract code (no alignment).
- Added an adjacency guard: main pair must be `rank_far == rank_near + 1`;
  dates where a middle rank is missing are skipped instead of creating M1–M3.

**Files changed:**
- `src/curve.py` — new
- `src/panel.py` — new
- `src/qa.py` — new
- `tests/test_spread.py` — new

**Commands:**
- `python3 -m pytest -q` → 12 passed
- Full-data panel run → rank panel 1,013,664 rows; contract panel 950,626 rows
  (6,735 contracts); return panel 1,013,664 rows; 236,186 selected pair-days
  (139,017 M1–M2 / 97,169 M2–M3); 6,664 episodes.
- QA on full data: 0 duplicate contract-date, 0 rank-order violations,
  0 partial rolls, 0 full-day queue violations, return mapping passes,
  contract calendar passes, CL 2020-04-20 matches -37.63.

**Why:** This is the project's technical core. Naive generic-price differences
on roll dates are not returns; the contract panel and the rank-return mapping
make the roll-day return use the new contract's previous-day price.

**Validation:**
- Fixture: 95 contract rows, 10 unique contracts, roll-day CL M1 return
  `62.0/61.4 - 1`; naive return differs.
- Full data: 6,377 full roll dates; all four ranks shift together; no partial
  or queue violations.
- `pytest` 12 passed.

**Commit:** `feat(panel): build contract and return panels with roll-aware QA`

**Next:** Phase 3 — liquidity/universe metrics and pair-episode validation.

---

## LOG-0005 · 2026-10-17 17:10 · Phase 3 · Claude Code

**Goal:** Add point-in-time liquidity diagnostics and validate pair episodes,
without applying a universe threshold.

**Actions:**
- Added `build_universe` and trailing-median helpers to `src/panel.py`:
  - contract-level 252-session median volume/OI, min 60 observations;
  - rank-level fallback with `liq_proxy` flags;
  - `pair_liq = min(leg_near, leg_far)`;
  - threshold booleans for 1k/5k/10k/20k (volume and OI).
- Added `liquidity_summary` and `qa.assert_pair_adjacency`.
- Added an adjacency guard in `select_pairs`: the main pair must be
  `rank_far == rank_near + 1`; dates with a missing middle rank are skipped.
- Extended `build_pair_episodes` to aggregate mean/min pair liquidity when the
  universe columns are present.
- Added tests for episode additivity and universe liquidity/thresholds.

**Files changed:**
- `src/panel.py` — universe/liquidity metrics and summary
- `src/curve.py` — adjacency guard, episode liquidity aggregation
- `src/qa.py` — pair adjacency assertion
- `tests/test_spread.py` — episode and universe tests

**Commands:**
- `python3 -m pytest -q` → 14 passed
- Full-data run → 236,186 selected pair-days; 6,664 episodes; pair mix
  139,017 M1–M2 / 97,169 M2–M3.
- Liquidity summary: 5k volume threshold passes 69,301 pair-days across 19
  roots; 5k OI passes 151,137 pair-days across 21 roots; 1k volume passes
  127,944 pair-days across 20 roots.
- `liq_proxy` share ≈30%; pair-level volume liquidity missing ≈7.2% (mostly
  very early history with fewer than 60 observations).

**Why:** The user wants to choose the universe threshold after seeing the
diagnostics. The code must expose the metrics without silently filtering. The
episode table also needs liquidity so the signal layer can later decide which
pairs are tradable.

**Validation:**
- Full-data pair adjacency assertion passes.
- No eligible row is inside a delivery month.
- Episode entry/exit spread arithmetic is additive in the synthetic unit test.
- `pytest` 14 passed.

**Commit:** `feat(spread): build liquidity universe and pair episodes`

**Next:** Phase 4 — notebooks `00_data_audit` and `01_panel_build`, execute,
save parquet, final QA and README/log updates.

---

## LOG-0006 · 2026-10-17 17:20 · Phase 3b · Claude Code

**Goal:** Add the adjacent-pair robustness panel promised in D-008, without
changing the main selected pair.

**Actions:**
- Added `build_adjacent_pairs` to `src/panel.py`: builds every eligible
  adjacent pair (M1–M2, M2–M3, M3–M4), flags the main selected subset with
  `is_main_pair`, and reuses the same eligibility/eligibility-reason columns.
- Extended `build_all` to return `adjacent_pairs` and `adjacent_spread` in
  addition to the main `pairs`/`spread`.
- Added a unit test that every adjacent pair is truly adjacent and that the
  `is_main_pair` count equals the main `select_pairs` count.
- Updated the data dictionary for the adjacent panels and the actual
  `pass_vol_*` / `pass_oi_*` column names.

**Files changed:**
- `src/panel.py` — adjacent-pair builder and expanded `build_all`
- `tests/test_spread.py` — adjacent-pair test
- `docs/data_dictionary.md` — adjacent panels and universe column names

**Commands:**
- `python3 -m pytest -q` → 15 passed
- Full-data run → `adjacent_pairs` 610,801 rows; main subset 236,186;
  mix 139,017 M1–M2 / 235,917 M2–M3 / 235,867 M3–M4.

**Why:** The main experiment should use one common pair, but the signal layer
may need alternative adjacent pairs for robustness. Keeping both avoids
rerunning the data build later.

**Validation:**
- All adjacent rows satisfy `rank_far == rank_near + 1`.
- `is_main_pair.sum()` equals the main `pairs` row count.
- Main pair mix is unchanged.

**Commit:** `feat(spread): add adjacent-pair robustness panel`

**Next:** notebooks and final docs.

---

## LOG-0007 · 2026-10-17 17:35 · Phase 4 · Claude Code

**Goal:** Deliver the human-facing notebooks, execute them from raw data, save
the processed panels, and finalize the repo status.

**Actions:**
- Added `src/viz.py`: coverage heatmap, liquidity heatmap, universe counts,
  pair mix, and spread distribution plots (matplotlib only).
- Added `notebooks/00_data_audit.ipynb`: raw structure, coverage, roll
  mechanics, data quality, and liquidity diagnostics.
- Added `notebooks/01_panel_build.ipynb`: builds the stack, shows the
  contract/return/spread examples, runs QA, and saves nine parquet panels.
- Executed both notebooks top-to-bottom with `nbconvert`; kept outputs concise
  (summary tables and selected figures), and changed the save cell to print
  relative paths.
- Updated `README.md`, `AGENTS.md`, and `docs/onboarding.md` to mark the data
  layer complete and the next phase (signals/backtest) as not started.

**Files changed:**
- `src/viz.py` — new plotting helpers
- `notebooks/00_data_audit.ipynb`, `notebooks/01_panel_build.ipynb` — new
- `README.md`, `AGENTS.md`, `docs/onboarding.md` — status/phase updates

**Commands:**
- `jupyter nbconvert --execute --to notebook --inplace notebooks/00_data_audit.ipynb`
- `jupyter nbconvert --execute --to notebook --inplace notebooks/01_panel_build.ipynb`
- `python3 -m pytest -q` → 15 passed
- Notebook outputs: 00 ≈502KB, 01 ≈243KB; no execution errors; text outputs
  capped at ~1.3k characters; 1–2 figures per plot cell.
- Saved panels (gitignored): rank, contract, returns, pairs, spread, universe,
  episodes, adjacent_pairs, adjacent_spread.

**Why:** The final deliverable must be readable by a human and reproducible by
a teammate. Logic stays in `src/`; the notebooks explain what happened and
what the data now supports.

**Validation:**
- Both notebooks run top-to-bottom from `data/raw/...csv`.
- QA assertions pass; CL 2020-04-20 = -37.63; selected pair excludes the
  expiring front contract.
- `git status` shows no raw data, PDFs, or parquet staged.
- Notebook save output uses relative `data/processed/...` paths.

**Commit:** `feat(audit): add data audit and panel build notebooks`

**Next:** user review of notebooks/panels; signals/backtest only after explicit
approval. Stop here for this phase.

---

## LOG-0008 · 2026-10-17 16:50 · Phase 4b · Claude Code

**Goal:** Make the repo self-describing for a new conversation or a teammate's
coding agent, and make the notebooks readable in Chinese/bilingual.

**Actions:**
- Added `docs/HANDOFF.md`: current state, key row counts, locked decisions,
  what is done/not done, reproduction commands, open questions, next step.
- Added `docs/research_notes.md`: paper/industry roll conventions, why we use
  no-delivery-month + D=10, dollar/log spread definitions, and data-audit facts.
- Added `data/processed/README.md`: expected parquet files/shapes, regeneration
  instructions, and the public-repo/gitignore rationale. Updated `.gitignore`
  to track this README while still ignoring parquet.
- Added `scripts/run_all.sh`: install dependencies, run tests, execute both
  notebooks, list generated panels. Made it executable and syntax-checked.
- Translated both notebook markdown narratives to Chinese/bilingual while
  keeping code identifiers and panel names in English; re-executed both.
- Updated `README.md`, `AGENTS.md`, `CLAUDE.md`, and `docs/onboarding.md` with
  the HANDOFF read order, bilingual notebook convention, and run_all command.

**Files changed:**
- `docs/HANDOFF.md`, `docs/research_notes.md` — new
- `data/processed/README.md`, `.gitignore` — new/tracked exception
- `scripts/run_all.sh` — new
- `notebooks/00_data_audit.ipynb`, `notebooks/01_panel_build.ipynb` — Chinese/
  bilingual markdown, re-executed
- `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/onboarding.md` — read order,
  language convention, reproduction command

**Commands:**
- `chmod +x scripts/run_all.sh && bash -n scripts/run_all.sh`
- `jupyter nbconvert --execute --to notebook --inplace notebooks/00_data_audit.ipynb`
- `jupyter nbconvert --execute --to notebook --inplace notebooks/01_panel_build.ipynb`
- `python3 -m pytest -q` → 15 passed

**Why:** A new Claude Code conversation auto-reads `CLAUDE.md`, but a teammate's
agent or a fresh chat needs a compact state snapshot. The notebooks are for the
two authors to read, not a code-submission artifact, so Chinese/bilingual
narrative is more useful than English-only prose.

**Validation:**
- Both bilingual notebooks execute top-to-bottom with no errors; outputs remain
  concise (00 ≈502KB, 01 ≈242KB).
- No absolute local paths remain in notebook outputs.
- `data/processed/README.md` is tracked; parquet files remain ignored.
- `scripts/run_all.sh` passes `bash -n`.
- 15 tests pass; HANDOFF row counts match the generated panels.

**Commit:** `docs: add handoff snapshot, research notes, and bilingual notebooks`

**Next:** user reviews HANDOFF/notebooks; choose liquidity threshold and signal
priority. Do not start signals/backtest until explicitly approved.

---

## LOG-0009 · 2026-10-17 16:52 · Phase 4c · Claude Code

**Goal:** Make `scripts/run_all.sh` leave the git tree clean after re-executing
the notebooks.

**Actions:**
- Added `scripts/clean_notebook_metadata.py`: removes only nbconvert's volatile
  per-cell `metadata.execution` timestamps; sources and outputs are untouched.
- Updated `scripts/run_all.sh` to call the cleaner after both notebook
  executions.
- Cleaned both committed notebooks once; verified that sources and outputs are
  identical to the previous commit and only execution timestamps were removed.
- Re-ran `bash scripts/run_all.sh` to validate the workflow.

**Files changed:**
- `scripts/clean_notebook_metadata.py` — new
- `scripts/run_all.sh` — call the cleaner after execution
- `notebooks/00_data_audit.ipynb`, `notebooks/01_panel_build.ipynb` — timestamps
  removed; sources/outputs unchanged

**Commands:**
- `python3 scripts/clean_notebook_metadata.py notebooks/*.ipynb`
- `bash scripts/run_all.sh` → 15 tests, both notebooks execute, panels listed
- `python3` comparison vs HEAD → sources True, outputs True, execution metadata
  removed

**Why:** Re-running the reproduction script should not dirty the working tree
with wall-clock timestamps. This keeps diffs meaningful for the two-person
collaboration.

**Validation:**
- Sources and outputs are byte-identical to the prior notebooks.
- `run_all.sh` completes and the only notebook change is the timestamp removal.
- 15 tests pass.

**Commit:** `chore(notebooks): strip volatile execution timestamps`

**Next:** commit/push, then verify a second `run_all.sh` leaves `git status`
clean. Stop before signals.

---

## LOG-0010 · 2026-10-19 15:16 · Phase 5 · Claude Code

**Goal:** Establish the foundation for the A (carry) baseline: an ex-ante K=5
backtest panel, a per-contract mark state, the carry signal, and a live
progress file for other agents/teammates.

**Actions:**
- Added `d=None` K-only mode to `add_eligibility` / `select_pairs`; the
  `missing_calendar` and `too_close_expiry` conditions no longer require
  `days_to_last_trading` when `d` is None.
- Added `build_backtest_panel()` and `build_contract_mark_state()` to
  `src/panel.py`. The backtest panel is K=5 and saved under distinct
  `backtest_*` names; the D=10 research panels are unchanged.
- Added `src/signals.py` with `CarryParams` and `carry_signal()`
  (`sign(P_near − P_far)`; annualized carry stored for diagnostics).
- Added `docs/PROGRESS.md`: live status, decisions, files, verification, next.
- Added D-009 to `docs/decisions.md` recording the backtest conventions.
- Updated `docs/logs/INDEX.md` with LOG-0010.

**Files changed:**
- `src/curve.py` — `d=None` eligibility
- `src/panel.py` — `build_backtest_panel`, `build_contract_mark_state`
- `src/signals.py` — new
- `docs/PROGRESS.md` — new
- `docs/decisions.md` — D-009
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 15 passed
- `build_backtest_panel(rank, d=None, k=5)` → 236,385 pair-dates;
  M1–M2 159,817 / M2–M3 76,568
- `carry_signal(backtest_spread)` → target counts: −1 161,058 / +1 73,661 /
  0 1,666; one NaN `carry_ann` (CL 2020-04-20)

**Why:** D-002's D=10 condition uses the contract's final appearance in the
full extract, which is ex post and would leak future information into pair
selection. The backtest needs an ex-ante universe and explicit mark/return/cost
conventions; the research panels remain useful for QA and description.

**Validation:**
- Existing 15 tests pass; the K=5 panel row count and pair mix match the
  independent simulation in the plan.
- The per-contract mark state was spot-checked on 20 contracts; it counts
  missing/stale/absent sessions and preserves the last valid price.
- The negative CL price on 2020-04-20 produces NaN annualized carry but a valid
  dollar spread and target.

**Commit:** `feat(backtest): add K=5 panel, mark state, and carry signal`

**Next:** implement `src/backtest.py` (pair-specific pending orders,
t+1 execution, roll/missing/cost state machine), then `src/metrics.py`, tests,
and `notebooks/02_carry.ipynb`.

---

## LOG-0011 · 2026-10-19 15:48 · Phase 5b · Claude Code

**Goal:** Implement the reusable return-based calendar-spread backtest engine
and its tests, so A can be benchmarked and C/D/B can reuse the engine.

**Actions:**
- Added `src/backtest.py`:
  - `BacktestConfig`, `BacktestResult`, `build_target_legs`, `run_backtest`.
  - Daily event loop with pair-specific pending orders; signal at t, fill at
    t+1 close; mark before execute.
  - Roll handling at t+1 with last-valid marks and `roll_leg_missing`.
  - Per-contract mark state use; 6th invalid session forced exit.
  - Exact net-leg cost: 5 bps × traded notional / previous gross notional.
  - Sample-end open-position flag; config guards for unsupported options.
- Added `src/metrics.py`: `summarize`, `sector_summary`, `conditional_mean`
  (normalized, fill-to-fill, date-level block bootstrap), `plot_result`.
- Added `tests/test_eligibility.py`, `tests/test_signals.py`,
  `tests/test_backtest.py` (17 new tests).
- Added `docs/backtest_framework.md`; added §10 to `docs/data_dictionary.md`.
- Fixed `build_contract_mark_state` to accept minimal synthetic contract
  panels (compute `first_date`/`last_date` and tolerate missing volume).

**Files changed:**
- `src/backtest.py` — new
- `src/metrics.py` — new
- `src/panel.py` — mark-state robustness on minimal frames
- `tests/test_eligibility.py`, `tests/test_signals.py`,
  `tests/test_backtest.py` — new
- `docs/backtest_framework.md` — new
- `docs/data_dictionary.md` — §10 backtest tables/conventions

**Commands:**
- `python -m pytest -q` → 32 passed
- Synthetic checks: entry at t+1, lagged denominator, roll with four net legs,
  `roll_leg_missing`, stale-entry block, forced exit, same-sign zero cost,
  3-leg sanity, config guards.

**Why:** A needs a point-in-time, roll-aware engine; vectorising the whole
backtest would mishandle pending orders, rolls, and forced exits. The signal
layer stays separate so C/D/B only add signal functions.

**Validation:**
- 32 tests pass.
- Full K=5 run completes; test run starts flat in 2016.
- Trade reasons/flags are populated (`roll`, `roll_leg_missing`,
  `forced_exit`, `entry_blocked`, `pending_canceled`).

**Commit:** `feat(backtest): add return-based calendar-spread engine`

**Next:** run the A benchmark in `notebooks/02_carry.ipynb`, record the
negative result, and update the status docs.

---

## LOG-0012 · 2026-10-19 15:55 · Phase 5c · Claude Code

**Goal:** Run the first A (carry) baseline benchmark end-to-end and record the
result, including the negative finding.

**Actions:**
- Added `notebooks/02_carry.ipynb`: K=5 panel, carry signal, target legs,
  full/test backtests, summary, conditional mean, sector summary, cumulative
  plot, interpretation, next steps.
- Updated `scripts/run_all.sh` to execute 02 and clean its metadata.
- Updated `docs/PROGRESS.md`, `docs/HANDOFF.md`, `README.md`, `AGENTS.md`,
  `docs/onboarding.md`, and `data/processed/README.md` for the new state.
- Saved `output/carry_summary.csv`, `output/carry_conditional_mean.csv`,
  `output/carry_sector.csv`, `output/carry_cumulative.png` (gitignored).

**Files changed:**
- `notebooks/02_carry.ipynb` — new
- `scripts/run_all.sh` — run 02
- `docs/PROGRESS.md`, `docs/HANDOFF.md`, `README.md`, `AGENTS.md`,
  `docs/onboarding.md`, `data/processed/README.md` — status
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/02_carry.ipynb` → OK
- `python scripts/clean_notebook_metadata.py notebooks/02_carry.ipynb`
- `python -m pytest -q` → 32 passed

**Why:** The project needs an honest first read on A before adding more ideas.
The notebook is the readable record; the CSVs/plot are local outputs.

**Validation:**
- Notebook executes top-to-bottom.
- Full sample net Sharpe −0.08, net ann. −1.90%; test net Sharpe −0.06.
- Conditional raw mean for `target_negative` is +0.000127 (t +2.41):
  contango spreads strengthen, so the short spread is the wrong direction.
- `target_positive` raw mean ≈ 0. A has no edge in this simplest baseline.
- K=5 pair mix and CL 2020-04-20 NaN carry are shown in the notebook.

**Commit:** `feat(carry): add idea A baseline benchmark`

**Next:** decide whether to try A variants/robustness or move to C
(mean reversion). Do not tune on the 2016–2026 test sample.

---

## LOG-0013 · 2026-10-19 16:33 · Phase 6a · Claude Code

**Goal:** Share the weekly rebalance calendar between the backtest engine and
the signal layer before implementing idea C, without changing engine behavior.

**Actions:**
- Added `curve.weekly_rebalance_dates(trading_days)`; it is the same
  `W-FRI` last-trading-day logic previously private in `src/backtest.py`.
- Updated `src/backtest.py` to call `curve.weekly_rebalance_dates`; removed
  the private helper.
- Updated `src/metrics.py` to import and use the public helper.
- Added equivalence and holiday-fallback tests in `tests/test_backtest.py`.
- Worked on branch `feat/idea-c-mean-reversion` so A and C commits stay
  separate.

**Files changed:**
- `src/curve.py` — public weekly helper
- `src/backtest.py` — delegate to curve helper
- `src/metrics.py` — use public helper
- `tests/test_backtest.py` — equivalence/holiday tests
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 34 passed

**Why:** Idea C needs to evaluate its weekly signal on exactly the same dates
the engine rebalances. A single shared helper prevents the signal calendar and
the engine calendar from drifting apart. The refactor is behavior-preserving.

**Validation:**
- The new helper matches the legacy `to_period("W-FRI").groupby.max()`
  expression.
- Holiday fallback returns the last trading day of the week.
- All 34 tests pass (A's 32 plus 2 new).

**Commit:** `refactor(curve): share weekly rebalance calendar`

**Next:** implement `src/continuous.py` (roll-chained leg price indices) and
its tests.

---

## LOG-0014 · 2026-10-19 16:42 · Phase 6b · Claude Code

**Goal:** Build a roll-chained continuous near/far price index for idea C.

**Actions:**
- Added `src/continuous.py`:
  - `build_continuous_leg_prices`: initializes each leg at the first observed
    settle on the first pair date, then adds contract-level
    `settle_t - settle_{t-1}`; on rolls uses the new pair's own price changes.
  - `build_spread_index`: thin dollar-spread layer.
  - `roll_diagnostics`: compares raw spread changes with continuous changes
    and the expected contract-level change.
- Added `tests/test_continuous.py` covering initialization, non-roll tracking,
  two rolls, adjacent rolls, pair change back and forth, missing changes,
  zero/negative settles, prehistory, duplicates, and diagnostics.

**Files changed:**
- `src/continuous.py` — new
- `tests/test_continuous.py` — new
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest tests/test_continuous.py -q` → 10 passed
- `python -m pytest -q` → 51 passed
- Full K=5 panel diagnostic: 236,385 rows, 6,640 pair changes; all 6,593 valid
  roll changes and 229,098 valid non-roll changes match
  `delta_near - delta_far`; 694 rows have NaN changes because the previous
  index is missing.

**Why:** Idea C needs a signal series that does not jump when the fixed pair
rolls. Chaining contract-level price changes is the roll-safe construction;
the raw dollar spread is still the traded instrument.

**Validation:**
- Synthetic tests cover two consecutive rolls, adjacent rolls, and a pair
  change back and forth.
- Full-panel diagnostics show no mismatch for any valid change; NaN changes
  are confined to missing previous observations.
- Full suite passes.

**Commit:** `feat(continuous): build roll-chained leg price indices`

**Next:** implement the mean-reversion state machine in `src/signals.py`.

---

## LOG-0015 · 2026-10-19 16:47 · Phase 6c · Claude Code

**Goal:** Implement the weekly mean-reversion signal and lock the idea C
baseline conventions.

**Actions:**
- Added `MeanReversionParams` and `mean_reversion_signal` to `src/signals.py`.
  - Rolling z with L=20, `min_periods=16`, `ddof=1`.
  - `_state_path` hysteresis: entry at ±2, exit at 0, direct flip, NaN hold.
  - Weekly evaluation on the engine calendar; complete daily target path.
  - `pair_grid` forces `target=0` where no tradable pair exists.
  - `evaluation="daily"` raises `NotImplementedError`.
- Added signal tests: state machine, weekly path, no-pair targets, truncation
  causality, and parameter guards.
- Added an integration test: a signal target path rolls a short position
  through a pair change rather than flattening.
- Added D-010, the continuous layer to `docs/backtest_framework.md`, and the
  new schemas to `docs/data_dictionary.md`.

**Files changed:**
- `src/signals.py` — `MeanReversionParams`, `_state_path`,
  `mean_reversion_signal`
- `tests/test_signals.py` — state and public API tests
- `tests/test_backtest.py` — signal/roll integration test
- `docs/decisions.md` — D-010
- `docs/backtest_framework.md` — continuous layer and C example
- `docs/data_dictionary.md` — continuous index and signal schemas
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 51 passed
- Full K=5 panel: 252,168 signal rows; target counts 0=166,822, −1=43,945,
  +1=41,401; 93.3% z-valid; all 24 roots trade.
- Full-sample backtest: gross ann. +0.53%, net −1.67%, net Sharpe −0.03,
  turnover 22.6×.

**Why:** The state machine must be explicit and causal, and the target path
must be complete on pair-change dates or the engine would flatten positions
during rolls. The baseline is deliberately weekly; daily is deferred.

**Validation:**
- The signal's evaluation dates are the engine's weekly dates.
- Truncating the input does not change past targets.
- No nonzero target appears on a date without a pair.
- A short signal survives a pair change as an engine roll.
- Full suite passes.

**Commit:** `feat(signals): add mean-reversion signal`

**Next:** build `notebooks/03_mean_reversion.ipynb`; run the energy 1992–2013
sanity check and the full/train/test backtests.

---

## LOG-0016 · 2026-10-19 17:05 · Phase 6d · Claude Code

**Goal:** Add the idea C baseline notebook and wire it into the reproduction
script.

**Actions:**
- Added `notebooks/03_mean_reversion.ipynb`:
  - K=5 panel rebuilt in memory (no dependency on A's local parquet).
  - Continuous index + roll diagnostics.
  - Weekly mean-reversion signal, target legs, energy 1992–2013 sanity check,
    full/train/test backtests, conditional mean, sector summary, cumulative
    plot, and an honest negative-result interpretation.
- Added notebook 03 to `scripts/run_all.sh` (execute + metadata clean).
- Updated `docs/backtest_framework.md` current status.
- Outputs are local/gitignored: `output/mean_reversion_*`.

**Files changed:**
- `notebooks/03_mean_reversion.ipynb` — new
- `scripts/run_all.sh` — run and clean 03
- `docs/backtest_framework.md` — C status
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/03_mean_reversion.ipynb` → OK
- `python scripts/clean_notebook_metadata.py notebooks/03_mean_reversion.ipynb`
- `python -m pytest -q` → 51 passed

**Why:** The notebook is the readable baseline record for the teammate; the
whole-file status docs (PROGRESS/HANDOFF/README/AGENTS/onboarding) are
intentionally deferred to a post-rebase commit to avoid conflicts with A.

**Validation:**
- Notebook executes top-to-bottom.
- Full sample gross +0.53%, net −1.67%, net Sharpe −0.03; train gross +0.87%,
  net −1.32%; test gross −0.39%, net −2.64%.
- Energy 1992–2013: gross −1.05%, net −3.12%, net Sharpe −0.04.
- Conditional mean full sample not significant; train short-spread raw mean
  −0.000203 (t −2.12), test not significant.
- Roll diagnostics: all valid changes match expected; 694 NaN changes due to
  missing previous observations.

**Commit:** `feat(mean-reversion): add idea C baseline benchmark`

**Next:** rebase on latest `main`, update status docs, run `run_all.sh`, then
merge the branch after review.

---

## LOG-0017 · 2026-10-19 17:15 · Phase 6e · Claude Code

**Goal:** Record the C baseline in the status docs after the notebook commit.

**Actions:**
- Updated `docs/PROGRESS.md` to cover both A and C baselines, including the C
  benchmark table and conditional-mean reading.
- Updated `docs/HANDOFF.md`: current commits, C results, D-010, read order,
  done/not-done, reproduction, open questions, and next step.
- Updated `README.md`, `AGENTS.md`, and `docs/onboarding.md` for the C
  baseline and the separate A/C branches.
- Updated `docs/logs/INDEX.md` with the C commit hashes.
- Kept this as a separate commit so the A robustness branch can be reconciled
  by union rather than by mixing code and status changes.

**Files changed:**
- `docs/PROGRESS.md`, `docs/HANDOFF.md`, `README.md`, `AGENTS.md`,
  `docs/onboarding.md`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 51 passed
- Notebook 03 was executed in LOG-0016; no code changes here.

**Why:** The teammate needs the C baseline and its negative result visible in
the same status files used for A, without mixing the A/C code branches.

**Validation:**
- Status numbers match notebook 03 and the saved `output/mean_reversion_*`
  files.
- A's baseline numbers are unchanged.
- C is described as a negative net result, with the train/test conditional
  mean caveat.

**Commit:** `docs(status): record idea C baseline`

**Next:** rebase on latest `main`, run the full `scripts/run_all.sh` after the
A/C branches are reconciled, then review and merge C.

---

## LOG-0018 · 2026-10-19 17:20 · Phase 6f · Claude Code

**Goal:** Lock the weekly evaluation calendar against a later-start backtest.

**Actions:**
- Added a test that the full-calendar signal's weekly evaluation dates cover
  the weekly dates produced by a later-start trading calendar (the shape of
  the 2016 test run's calendar).

**Files changed:**
- `tests/test_signals.py`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 52 passed

**Why:** The engine filters its calendar by `start_date`, while the signal is
computed on the full calendar. The target path is held daily, so it must cover
every engine rebalance date in a later-start run.

**Validation:**
- The full-calendar weekly set is a superset of the later-start weekly set.
- Full suite passes (52 tests).

**Commit:** `test(signals): cover later-start weekly calendar`

**Next:** final review/merge.

---

## LOG-0022 · 2026-10-19 17:40 · Phase 6g · Claude Code

**Merge note:** renumbered from LOG-0019 at the A/C merge to avoid the A
diagnosis entry (main LOG-0019). LOG-0023/0024 follow the same branch.

**Goal:** Add a rolling OLS hedge ratio on the continuous leg indices for the
C hedge-ratio variant.

**Actions:**
- Added `continuous.rolling_ols_hedge_ratio(leg_prices, window=60,
  min_periods=60)`:
  - `h_t = Cov(near_index, far_index) / Var(far_index)` over the trailing
    window;
  - hedge index `near_index − h_t·far_index`;
  - `h` must be finite and positive; otherwise the hedge index is NaN;
  - rolling estimates use only data through t.
- Added tests for a known slope of 2.0, negative/zero-variance invalidation,
  truncation/no-lookahead, and parameter/key validation.

**Files changed:**
- `src/continuous.py` — `rolling_ols_hedge_ratio`
- `tests/test_continuous.py` — hedge-ratio tests
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 58 passed
- Full-panel diagnostic: 236,385 rows, 99.3% valid; `h` quantiles
  1%=0.555, 5%=0.796, 50%=1.008, 95%=1.312, 99%=1.612.

**Why:** The user wants to test whether a time-varying hedge ratio improves
the same mean-reversion signal. The rolling OLS on levels is the direct
analogue of the paper's hedge portfolio; `h` near 1 means the hedge portfolio
is close to the 1:1 spread.

**Validation:**
- Synthetic near = 2·far recovers h=2 and hedge index 0.
- Negative/zero-variance slopes are invalid and produce NaN.
- Truncating the input does not change past h.
- Full suite passes.

**Commit:** `feat(continuous): add rolling OLS hedge ratio`

**Next:** support optional hedge-ratio weights in `build_target_legs`.

---

## LOG-0023 · 2026-10-19 17:42 · Phase 6h · Claude Code

**Goal:** Support hedge-ratio-weighted far legs and lock the C hedge-ratio
variant conventions.

**Actions:**
- Extended `backtest.build_target_legs` with an optional `hedge_ratio`
  column: far units are `−target × hedge_ratio`; invalid/missing ratios are
  dropped; behavior without the column is unchanged.
- Added a duplicate `(date, root)` guard to the signal panel.
- Added D-011 and updated the data dictionary and framework docs.
- Added tests for long/short hedge weights and invalid ratios; updated the
  existing target-leg test to use unique dates.

**Files changed:**
- `src/backtest.py` — optional hedge-ratio weights
- `tests/test_backtest.py` — hedge-weight tests
- `docs/decisions.md` — D-011
- `docs/data_dictionary.md`, `docs/backtest_framework.md`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 58 passed

**Why:** The hedge-ratio variant requires a far-leg position of `−target·h`
instead of `−target`. The target-leg layer is the documented place for this
change; the engine already accepts arbitrary units.

**Validation:**
- target +1 / h=2 → near +1, far −2; target −1 / h=0.5 → near −1, far +0.5.
- Missing/non-positive ratios are dropped.
- The 1:1 path is unchanged when `hedge_ratio` is absent.
- Full suite passes.

**Commit:** `feat(backtest): support hedge-ratio leg weights`

**Next:** add the hedge-ratio comparison section to notebook 03 and run the
gross (0 bps) experiment.

---

## LOG-0024 · 2026-10-19 17:45 · Phase 6i · Claude Code

**Goal:** Run the C rolling-OLS hedge-ratio variant gross (0 bps) and compare
it with the 1:1 baseline.

**Actions:**
- Built the 60-day rolling OLS hedge index and signal on the K=5 panel.
- Merged `hedge_ratio` onto the signal, forced target=0 where h is invalid,
  and built hedge-weighted target legs.
- Ran 1:1 and hedge variants with `cost_bps_per_leg=0.0`:
  - full 1986–2026, train 1986–2015, test 2016–2026.
- Compared gross summary and conditional mean.

**Results:**
- h distribution: median 1.008; 5–95% 0.796–1.312; 99.3% valid.
- 0 bps full: 1:1 gross ann. +0.535%, Sharpe 0.010, turnover 22.6×;
  hedge gross ann. +0.197%, Sharpe 0.006, turnover 20.4×.
- Train: 1:1 +0.868% / Sharpe 0.030; hedge +0.290% / 0.012.
- Test: 1:1 −0.391% / Sharpe −0.002; hedge −0.055% / 0.001.
- Conditional mean full: 1:1 target_positive +0.000017 (t 0.10),
  target_negative +0.000101 (t 1.15); hedge target_positive +0.000057
  (t 0.48), target_negative −0.000020 (t −0.32).
- Energy 1992–2013 (0 bps): 1:1 gross −1.05% / Sharpe −0.013; hedge
  −0.10% / 0.0002; less bad but still no positive edge.

**Why:** The hedge ratio was the remaining plausible explanation for C's weak
gross result. The gross comparison shows it does not improve full/train/test
returns; it lowers volatility and returns, with more trades and similar/worse
Sharpe. Energy is less bad but still has no positive edge.

**Validation:**
- Same state machine, universe, and weekly timing; only the index and far-leg
  weights change.
- 1:1 and hedge runs both use 0 bps, so the comparison isolates the hedge
  ratio.
- No 5 bps run because the hedge gross result is not materially better.

**Commit:** `feat(mean-reversion): add hedge-ratio robustness section`

**Next:** document the negative hedge-ratio result; do not run costs or tune
on the test sample.


## LOG-0019 · 2026-10-19 16:40 · Phase 6b · Claude Code

**Goal:** Explain the A (carry) negative result, without trying to rescue it.
The deliverable is a concise negative-result diagnosis, not a new strategy.

**Actions:**
- Added `src/a_diagnostics.py`:
  - `side_sector_era`: raw spread mean, cluster-by-date t-stat, exact gross
    contribution, by side × sector × era.
  - `eligibility_compare`: same A signal under ex-ante K=5 and K=10;
    D=10 is deliberately excluded because `last_trade_proxy` is ex post.
  - `cost_sensitivity`: linearly scales the 5 bps cost series to 0/5/10/20.
  - `load_result`: load the saved `output/carry_full_*` tables.
- Added `notebooks/04_a_diagnose.ipynb` (short narrative + three tables).
- Added `docs/a_negative_result.md` (one-page conclusion and caveats).
- Added `tests/test_a_diagnostics.py` (direction, contribution, cost scaling).
- Updated `docs/PROGRESS.md` with the diagnosis summary.
- Kept the work isolated on branch `a-robustness`; C continues on its own
  branch/worktree.

**Files changed:**
- `src/a_diagnostics.py` — new
- `tests/test_a_diagnostics.py` — new
- `notebooks/04_a_diagnose.ipynb` — new
- `docs/a_negative_result.md` — new
- `docs/PROGRESS.md`, `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 34 passed
- `jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/04_a_diagnose.ipynb` → OK
- `eligibility_compare(..., k_values=(5, 10), results={5: full})` → K=10 rerun

**Why:** The baseline is negative. Before moving on, the project needs a short,
credible explanation of why A's edge is absent; otherwise the negative result
looks like an implementation bug. The diagnosis is deliberately limited to the
hypothesis (side × sector × era), ex-ante eligibility (K=5 vs K=10), and costs.
No rescue variants are tried.

**Validation:**
- Short raw mean +0.000024 (t +2.46); long raw mean −0.000008 (t −0.65).
- K=10: short +0.000018 (t +1.84), long −0.000032 (t −2.83); both net
  Sharpe negative.
- Costs 0/5/10/20 bps: net ann. −0.53% / −1.90% / −3.24% / −5.89%;
  gross is already negative.
- Contribution cells sum to the cumulative daily portfolio gross return.
- Cost scaling at 5 bps matches the baseline net result.

**Commit:** `feat(a-diagnostics): add A negative-result diagnosis`

**Next:** merged into `main` as LOG-0019; the notebook was renumbered to
`04_a_diagnose.ipynb` to reserve `03` and LOG-0013–0018 for the C branch.

---

## LOG-0020 · 2026-10-19 16:55 · Phase 6c · Claude Code

**Goal:** Decide whether B is worth pursuing with a cheap, pre-registered
pre-test. This is not a full curve-fitting B and not a rescue of A.

**Actions:**
- Added `src/b_pre_test.py`:
  - annualized carry for M1-M2 / M2-M3 / M3-M4;
  - long the highest-carry adjacent spread, short the lowest;
  - leg-level targets passed directly to the existing engine; the K=5 main
    pair supplies the group key and pair validation, with zero-unit main legs
    when the B trade uses other maturities;
  - `run_b_pretest` full/train/test and `should_skip_b` decision rule.
- Added `notebooks/05_b_pretest.ipynb` and `docs/b_pretest.md`.
- Added `tests/test_b_pre_test.py` (high/low legs and decision rule).
- Updated `docs/PROGRESS.md`; kept the work on branch `b-pre-test` so it does
  not mix with A or C.

**Files changed:**
- `src/b_pre_test.py` — new
- `tests/test_b_pre_test.py` — new
- `notebooks/05_b_pretest.ipynb` — new
- `docs/b_pretest.md` — new
- `docs/PROGRESS.md`, `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 34 passed
- `jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/05_b_pretest.ipynb` → OK
- `run_b_pretest(rank)` → 128.7 s; 872,652 target leg rows; 100,117 trades

**Why:** A's negative result does not logically kill B, but B is a different
(and more complex) hypothesis. A cheap pre-test is the right way to decide
whether to spend time on a shallow B. The decision rule was fixed before
looking at the result.

**Validation:**
- Full: gross ann. −1.14%, net −2.84%, gross Sharpe −0.08, net −0.19.
- Train: gross −1.10%, net −2.80%; test: gross −1.25%, net −2.96%.
- Gross is already negative; costs are not the cause of the sign.
- `should_skip_b` → True.
- Targets are non-empty and traded; this is not a no-trade artifact.

**Commit:** `feat(b-pretest): add cheap B negative pre-test`

**Next:** merged into `main` as LOG-0020 after A; skip B in this form. A residual /
fitted-curve B is a separate pre-registered idea, not a rescue.

---

## LOG-0021 · 2026-10-19 17:25 · Phase 6g · Claude Code

**Goal:** Integrate A and B into `main` without mixing in the deferred C branch.

**Actions:**
- Created an integration worktree from `main` (`09b88ec`) and merged
  `a-robustness` (`ab4286a`, change `f02f18b`) with `--no-ff`; no conflicts.
- Renumbered A diagnosis notebook `03_a_diagnose` → `04_a_diagnose` and
  LOG-0014 → LOG-0019. Notebook `03` and LOG-0013–0018 are reserved for C.
- Merged `b-pre-test` (`21fa760`, change `d257e0e`); resolved conflicts in
  `docs/PROGRESS.md`, `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`.
- Renumbered B pre-test notebook `04_b_pretest` → `05_b_pretest` and
  LOG-0015 → LOG-0020.
- Updated `README.md`, `AGENTS.md`, `docs/HANDOFF.md`, `docs/onboarding.md`,
  `docs/PROGRESS.md`, and `scripts/run_all.sh` for the A/B baselines. C is
  explicitly left on `feat/idea-c-mean-reversion` and not merged.
- Finalized A/B as **closed** documented negative baselines: no parameter
  tuning and no rescue variants.
- No report file was written.

**Files changed:**
- `src/a_diagnostics.py`, `tests/test_a_diagnostics.py`,
  `notebooks/04_a_diagnose.ipynb`, `docs/a_negative_result.md` (from A)
- `src/b_pre_test.py`, `tests/test_b_pre_test.py`,
  `notebooks/05_b_pretest.ipynb`, `docs/b_pretest.md` (from B)
- `docs/PROGRESS.md`, `docs/HANDOFF.md`, `README.md`, `AGENTS.md`,
  `docs/onboarding.md`, `scripts/run_all.sh`, `docs/logs/*`

**Commands:**
- `python -m pytest -q` → 36 passed
- `jupyter nbconvert --execute --to notebook ... notebooks/04_a_diagnose.ipynb`
  → OK
- `jupyter nbconvert --execute --to notebook ... notebooks/05_b_pretest.ipynb`
  → OK

**Validation:**
- A: K=5 net Sharpe −0.0799; K=10 net Sharpe −0.0853; short raw mean
  +0.000024 (t +2.46), long −0.000008 (t −0.65); cost 0/5/10/20 bps
  net ann. −0.53% / −1.90% / −3.24% / −5.89%.
- B: full gross −1.14%, net −2.84%, gross Sharpe −0.076, net −0.187;
  `should_skip_b` → True. Results are unchanged from the A/B branches.
- Zero-cost check: A full gross ann. −0.53% (Sharpe −0.02); B full gross
  ann. −1.14% (Sharpe −0.08). Both negative before transaction costs.
- A/B closed; the final report will state the A/B idea does not work.
- `main` is the A/B integration; C remains separate.

**Commit:** A merge `a15541e`; B merge `7d1d626`; this docs commit.

**Next:** A/B closed. C merge later; keep notebook `03` and LOG-0013–0018,
continue its log at LOG-0022. D/H next.

---

## LOG-0025 · 2026-10-19 18:05 · Phase 6j · Claude Code

**Goal:** Reconcile the C branch with A/B `main` after the reserve-slot merge.

**Actions:**
- Rebased `feat/idea-c-mean-reversion` onto `main` (`4c7dee8`), which contains
  A diagnosis and B pre-test.
- Kept A/B entries `LOG-0019`–`LOG-0021`; C baseline uses `LOG-0013`–`0018`.
- Renumbered the later C hedge-ratio entries to `LOG-0022`–`LOG-0024` (merge
  note in LOG-0022) to avoid the A/B IDs.
- Merged the status docs so A/B content is preserved and C results are added,
  rather than taking either side wholesale.
- Recombined `scripts/run_all.sh` to run notebooks 00, 01, 02, 03, 04, 05.

**Files changed:**
- `AGENTS.md`, `README.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`
- `scripts/run_all.sh`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 62 passed
- conflict-marker scan over md/py/sh/ipynb → none

**Why:** The C branch was created before main integrated A diagnosis and B
pre-test. The rebase keeps C's commits separate while making the shared
engine, docs, and log numbering consistent with main.

**Validation:**
- 62 tests pass (A/B/C combined).
- No duplicate INDEX rows; no conflict markers.
- `scripts/run_all.sh` runs all five notebooks.
- Notebook 03 still contains the hedge-ratio section and outputs.

**Commit:** `docs(status): reconcile C log IDs after rebase`

**Next:** review and merge the C branch; do not mix A/B and C commits.

---

## LOG-0026 · 2026-10-19 18:40 · Phase 6k · Claude Code

**Goal:** Test the paper's Kalman-filter hedge ratio, run the aggregate and
per-root comparison, and close idea C honestly.

**Actions:**
- Added `src/kalman.py`:
  - two-state DLM (`near = beta_0 + beta_1·far`, random-walk beta);
  - 252-observation warm-up; observation variance from a trailing OLS
    residual; `q` selected from `1e-9 … 1e-1` by Kalman likelihood every 60
    observations; `W = qV·I`; `h>0`; no cap.
- Added `tests/test_kalman.py`: known slope, no-lookahead truncation, missing
  observations, parameter/key validation.
- Ran the 0 bps aggregate comparison (1:1, rolling OLS, Kalman) and a per-root
  dollar P&L report for the paper sample.
- Added D-012 and documented the close-out.

**Results:**
- Aggregate Kalman full: gross +0.984%, vol 8.90%, Sharpe 0.0094,
  max drawdown −28.9%, turnover 28.3×; test: gross +0.519%, vol 16.7%,
  Sharpe 0.0064.
- Implied 5 bps net: about −1.8%/yr full, −2.5%/yr test.
- Per-root paper sample (dollar P&L / average gross): CL −0.79% / Sharpe
  −0.257, CO −0.57% / −0.236, HO −0.50% / −0.458, NG **+1.34% / +0.309**,
  XB +0.21% / +0.268.
- CL worst day is 2020-04-20 (−48.4% of average gross); its 2020
  calendar-year contribution is +10.0%. No data were excluded, capped, or
  winsorized.
- The paper's Sharpe >2 is not reproduced in the weekly K=5 setting. NG is
  directionally consistent, CL is not. A genuine 5–21 day edge should
  survive weekly sampling; the gap plus the paper's large grid and weak
  significance in many combinations points to selection/overfitting.

**Files changed:**
- `src/kalman.py` — new
- `tests/test_kalman.py` — new
- `docs/decisions.md` — D-012
- `docs/backtest_framework.md`, `docs/data_dictionary.md`
- `docs/PROGRESS.md`, `docs/HANDOFF.md`, `README.md`, `AGENTS.md`,
  `docs/onboarding.md`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 66 passed
- Kalman panel: 252-day likelihood, 60-day re-estimation, 9-point q grid;
  96.4–96.5% valid h; h median ≈1.001.
- Per-root dollar P&L report: `output/kalman_per_root_dollar.csv` (local,
  gitignored).

**Why:** Kalman was the remaining paper-faithful hedge-ratio variant. It
improves gross return but not risk-adjusted return; costs and drawdowns make
it non-tradable. The weekly result and the per-root signs do not support the
paper's strong Sharpe, so C is closed rather than extended into a daily
replication.

**Validation:**
- Full suite 66 passed.
- q-grid boundary checked down to 1e-9; no material boundary effect.
- Negative prices and extreme P&L are retained; only the statistical
  reporting was changed to dollar/arithmetic measures.
- The aggregate and per-root numbers are reproducible from the scripts and
  the C branch data.

**Commit:** `feat(kalman): add Kalman hedge-ratio and close idea C`

**Next:** D/H; keep C closed unless a pre-registered daily CL/NG project is
explicitly started.

---

## LOG-0027 · 2026-10-19 18:50 · Phase 7 · Claude Code

**Goal:** Merge the closed C branch into `main` and reconcile A/B close-out
docs.

**Actions:**
- Merged `feat/idea-c-mean-reversion` into `main` with `--no-ff` in the
  `Project-ab-merge` worktree.
- Preserved A/B close-out wording from main; added C merged/closed status.
- Kept all C logs (`LOG-0013`–`0018`, `0022`–`0026`); A/B logs
  `LOG-0019`–`0021` are unchanged.
- Resolved conflicts in `AGENTS.md`, `README.md`, `docs/HANDOFF.md`,
  `docs/PROGRESS.md`, `docs/onboarding.md`, and the two log files by union,
  not by dropping either side.
- Code, tests, notebook 03, and `src/kalman.py` merged cleanly.

**Files changed:**
- `AGENTS.md`, `README.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`,
  `docs/onboarding.md`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 66 passed

**Why:** C is closed; integrate its negative/mixed results while preserving
the A/B close-out.

**Validation:**
- 66 tests pass on the merged tree.
- No conflict markers.
- `main` has notebooks 00–05 and `src/kalman.py`.

**Commit:** `merge: integrate idea C baselines`

**Next:** D/H; C closed.

---

## LOG-0028 · 2026-10-19 20:34 · Phase 8a · Claude Code

**Goal:** Add monthly rebalance support and the curve-momentum /
basis-momentum signal for idea D.

**Actions:**
- Added `curve.monthly_rebalance_dates` (last trading day of each calendar
  month, holiday fallback), shared by engine and signal.
- Extended `BacktestConfig.rebalance` and `_Engine` to support
  `last_trading_day_of_month`; the weekly default is unchanged.
- Added `CurveMomentumParams`, `_rank_return_index`, and
  `curve_momentum_signal` to `src/signals.py`.
- Added synthetic tests for the signal and monthly calendar.

**Files changed:**
- `src/curve.py`, `src/backtest.py`, `src/signals.py`
- `tests/test_backtest.py`, `tests/test_curve_momentum.py`

**Commands:**
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 80 passed
- Real-data signal smoke test: 243,699 rows; 11,310 signal dates;
  target counts +1 123,221 / −1 112,924 / 0 7,554.

**Why:** D needs a 12-month rank-slot momentum signal and monthly
rebalancing; the monthly calendar is reusable for H.

**Validation:**
- Weekly default is unchanged (equivalence test).
- Signal tests cover roll-adjusted compounding, min observations, negative
  prices, forward-fill, missing-month reset, mid-month pair changes, and
  no look-ahead.
- CL 2020-04-20 invalidates the 12-month windows; the signal recovers after
  the window rolls past the event.

**Commit:** `feat(curve-momentum): add monthly engine and basis-momentum signal`

**Next:** Add the D baseline notebook and run the full-sample diagnostics.

---

## LOG-0029 · 2026-10-19 20:35 · Phase 8b · Claude Code

**Goal:** Add the idea D baseline notebook and reproduce the full
diagnostics.

**Actions:**
- Added `notebooks/06_curve_momentum.ipynb`: K=5 panel, rank return index,
  monthly signal, targets, full/test backtests, summary, sector, static
  benchmarks, monthly Sharpe, block bootstrap, and cumulative plot.
- Added notebook 06 to `scripts/run_all.sh` and the metadata-clean list.
- Wrote `output/curve_momentum_*` (gitignored).

**Files changed:**
- `notebooks/06_curve_momentum.ipynb`
- `scripts/run_all.sh`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `~/miniconda3/envs/mfe/bin/jupyter nbconvert --execute --to notebook \
  --inplace --ExecutePreprocessor.timeout=1800 \
  notebooks/06_curve_momentum.ipynb` → OK

**Why:** The project needs an honest first read on D before deciding whether
to add robustness or move to H.

**Validation:**
- Notebook executes top-to-bottom.
- Full gross +0.55%/yr, net −0.99%/yr; train gross +0.85%, net −0.65%;
  test gross −0.28%, net −1.89%.
- Static +1: gross +0.35%, net −0.84%, turnover 11.4×; static −1: gross
  −0.37%, net −1.56%.
- Monthly net Sharpe: full −0.90, train −0.61, test −1.66; block-bootstrap
  t-stat full −5.87, test −5.41.
- Sector gross: Energy +1.51%, Oilseeds +0.65%, Grains +0.48%, Softs
  +0.19%, Livestock +0.12%, Metals +0.03%, Industrials −0.76%.
- CL 2020-04-20 signal is NaN for the affected 12-month windows; no stale
  target.

**Commit:** `feat(curve-momentum): add idea D baseline notebook`

**Next:** Record the D decision and close-out docs; then H.

---

## LOG-0030 · 2026-10-19 20:36 · Phase 8c · Claude Code

**Goal:** Record the D decision and close-out documentation.

**Actions:**
- Added D-013: D baseline conventions, first result, and the deferred
  N=4/weekly/6m/liquidity/inverse-vol/decay list.
- Recorded `D-x` (cross-sectional basis-momentum) as a separate backlog
  item, not part of D.
- Updated `README.md`, `AGENTS.md`, `docs/HANDOFF.md`,
  `docs/PROGRESS.md`, `docs/onboarding.md`,
  `docs/backtest_framework.md`, and `docs/data_dictionary.md` for D.
- Updated `paper/README.md` to list the local `basis_momentum.pdf`.
- Added LOG-0028–LOG-0030 and INDEX rows.

**Files changed:**
- `README.md`, `AGENTS.md`, `paper/README.md`
- `docs/HANDOFF.md`, `docs/PROGRESS.md`, `docs/decisions.md`,
  `docs/onboarding.md`, `docs/backtest_framework.md`,
  `docs/data_dictionary.md`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 80 passed
- `git diff --check` → clean

**Why:** D is a documented negative/mixed baseline; the docs must say so
without inviting test-set tuning. D-x is explicitly deferred and must not be
mixed into D.

**Validation:**
- D-013 matches the executed notebook summary and static/monthly tables.
- README/AGENTS/HANDOFF/PROGRESS/onboarding/backtest_framework/
  data_dictionary all list D and notebook 06 consistently.
- No raw data, PDFs, processed parquet, or output files are staged.

**Commit:** `docs(curve-momentum): record idea D baseline`

**Next:** H (holding-period scan); D-x remains a separate backlog item.

---

## LOG-0031 · 2026-10-19 20:40 · Phase 8d · Claude Code

**Goal:** Record the local D merge handoff and done/not-done state for a
new conversation.

**Actions:**
- Added HANDOFF §0b: branch, base, commits, worktree/merge instructions,
  D results, done/not-done/backlog.
- Added a local merge handoff block to PROGRESS.
- Recorded that nothing is pushed and `main` is checked out in the
  `Project-ab-merge` worktree.

**Files changed:**
- `docs/HANDOFF.md`, `docs/PROGRESS.md`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `git status -sb` → clean
- `git log --oneline --decorate -6` → 4 D commits ahead of main
- `git worktree list` → main in `Project-ab-merge`
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 80 passed

**Why:** The user will switch to another conversation to merge locally;
the next agent needs branch/commit/worktree instructions and the exact
done/not-done state.

**Validation:**
- HANDOFF §0b matches the actual branch, commits, worktree, and test count.
- D results match the executed notebook and earlier logs.
- No push was performed.

**Commit:** `docs(handoff): record idea D local merge handoff`

**Next:** Merge locally; H; D-x backlog.

---

## LOG-0032 · 2026-10-19 20:45 · Phase 8e · Claude Code

**Goal:** Merge idea D into `main` locally.

**Actions:**
- Merged `feat/idea-d-curve-momentum` into `main` with `--no-ff`.
- No conflicts; all D code, tests, notebook, docs, and logs are included.
- Kept the merge local; no push.

**Files changed:**
- Merge of the D branch: `src/curve.py`, `src/backtest.py`,
  `src/signals.py`, `tests/test_backtest.py`,
  `tests/test_curve_momentum.py`, `notebooks/06_curve_momentum.ipynb`,
  `scripts/run_all.sh`, `AGENTS.md`, `README.md`, `paper/README.md`,
  `docs/*`, `docs/logs/*`.

**Commands:**
- `git merge --no-ff feat/idea-d-curve-momentum` → clean
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 80 passed

**Why:** The user asked to merge the completed D baseline into local `main`.
The D branch is based directly on `cb755d0`; no conflicts.

**Validation:**
- 80 tests pass on `main`.
- D notebook 06 is present and executed.
- No push performed.

**Commit:** `merge: integrate idea D curve-momentum baseline`

**Next:** H; D-x backlog; keep local unless asked to push.

---

## LOG-0033 · 2026-10-19 · Phase 6 · Claude Code

**Goal:** Record the C/E ownership split and let the engine rebalance daily,
which C (Lubnau & Todorova) and E (Bianchi et al.) need.

**Actions:**
- Added D-014 (Tian: A, D; Jiaheng: C, E; Nelson–Siegel back in scope) and
  D-015 (daily rebalance option) to `docs/decisions.md`.
- Added `REBALANCE_RULES` and `_rebalance_dates` to `src/backtest.py`;
  `BacktestConfig(rebalance="daily")` now rebalances on every trading day.
  The default stays weekly.
- Updated the config guard test and added two daily-rebalance tests.
- Updated the config section of `docs/backtest_framework.md`.

**Files changed:**
- `src/backtest.py` — rebalance dispatcher, config guard
- `tests/test_backtest.py` — `rebalance` arg in `_run`, two new tests
- `docs/decisions.md` — D-014, D-015
- `docs/backtest_framework.md` — supported rebalance values
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 34 passed

**Why:** Weekly rebalancing would change C (daily band entries/exits, 2–21 day
holds) and E (1-day holds) instead of reproducing them.

**Validation:**
- Daily: a Wednesday signal fills Thursday; a constant target trades once.
- A flip on Monday fills Tuesday under daily and the following Monday under
  weekly.
- All pre-existing tests unchanged and passing; A defaults untouched.

**Commit:** `feat(backtest): add holdings-based v2 framework with layered costs` (`0b3d947`, includes the daily rebalance option)

**Next:** plan and implement the C and E signal modules on the shared engine.

## LOG-0034 · 2026-10-19 · Phase 7 · Claude Code

**Goal:** Rebuild the backtest framework so costs are layered (half-spread,
fees, impact), scale with capital, and signals can be diagnosed across
horizons; demonstrate on idea A.

**Actions:**
- Read the cost and position-construction sections of Paschke et al.,
  Lubnau & Todorova and Bianchi et al.; searched literature on futures
  bid-ask spreads (Wang, Garcia & Irwin), fees (Gao et al.) and square-root
  impact (Tóth et al.). Summary in `docs/transaction_costs.md`.
- Added `data/metadata/contract_specs.csv` (point value, tick in Bloomberg
  quote units) and v2 modules `src/specs.py`, `marks.py`, `sizing.py`,
  `costs.py`, `simulate.py`, `horizon.py`, `report.py`.
- Added `notebooks/03_backtest_framework.ipynb` (calls only) and added it to
  `scripts/run_all.sh`; D-016 in `docs/decisions.md`.
- Fixed issues found on real data: CL/CO/NG legs expiring inside the holding
  window (use `d=5` pairs + expiry exits); missing volume treated as zero
  liquidity (impute root median ADV); missing signal treated as flat (now
  hold); 1/N collapsing on exchange holidays (5-day max N); one-lot orders
  charged square-root impact (first lot impact free).

**Files changed:**
- `src/specs.py`, `src/marks.py`, `src/sizing.py`, `src/costs.py`,
  `src/simulate.py`, `src/horizon.py`, `src/report.py` — new
- `tests/test_simulate.py` — new (16 tests)
- `data/metadata/contract_specs.csv`, `docs/transaction_costs.md`,
  `notebooks/03_backtest_framework.ipynb` — new
- `docs/decisions.md`, `docs/backtest_framework.md`, `scripts/run_all.sh`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 50 passed
- `python -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=900 notebooks/03_backtest_framework.ipynb` → OK (~70 s)

**Why:** Replication of C/D/E needs daily trading, non-1:1 legs, cost
attribution and capacity; signal quality should be visible before execution.

**Validation:**
- Synthetic tests: t+1 fill / t+2 first P&L, flip size, blocked fills,
  expiry and forced exits, lossless P&L across gaps, spread execution halves
  the half-spread, square-root impact and impact-free first lot, k smoothing,
  fixed-pair forward returns, Newey-West, capacity re-costing = re-simulation.
- Carry (A), USD 10m, ADV >= 100: gross −0.48%/yr, − half-spread −0.84%,
  − fees −1.00%, − impact −2.61%; turnover 26x/yr. Signed forward return is
  negative at every horizon (t_NW −2.7 to −4.6); cross-sectional rank IC of
  annualised carry −0.031 (t_NW −6.2). Consistent with LOG-0012.

**Commit:** `feat(backtest): add holdings-based v2 framework with layered costs` (`0b3d947`)

**Next:** implement C/D/E signal functions on v2; calibrate `min_adv` and
impact volatility (leg vs spread) as robustness.

## LOG-0035 · 2026-10-19 · Phase 7b · Claude Code

**Goal:** Remove cross-sectional diagnostics (all strategies are time series)
and add liquidity-aware sizing.

**Actions:**
- `src/horizon.py`: replaced the cross-sectional rank IC and date-wise bins
  with `ts_ic` (per-root Spearman over time, NW t on standardised rank
  products), `rolling_ts_ic`, and `bin_returns` on each root's expanding
  (ex-ante) score percentile.
- `src/sizing.py`: `attach_leg_liquidity` adds `dollar_adv` (thinner leg);
  `scheme="liquidity"` sizes by dollar_ADV ** alpha; equal stays default.
- `src/report.py`: `plot_ts_ic`, `plot_capacity_compare`,
  `impact_bps_of_book` in `root_table`.
- Notebook 03: time-series IC/bins, new section 8 comparing equal vs
  liquidity sizing; D-016 and `docs/transaction_costs.md` updated.

**Files changed:** `src/horizon.py`, `src/sizing.py`, `src/report.py`,
`tests/test_simulate.py`, `notebooks/03_backtest_framework.ipynb`,
`docs/decisions.md`, `docs/transaction_costs.md`, `docs/logs/*`

**Commands:**
- `python -m pytest -q` → 52 passed
- notebook 03 executed top to bottom

**Why:** Settlement times differ across exchanges and the cross-section is
~20 markets; equal notional lets the thinnest markets set capacity.

**Validation:** Carry, USD 10m: mean per-root time-series IC −0.049 (18 of 24
roots negative); own-history quintile 1 +4.8 bps vs quintile 5 −2.7 bps over
t+1 -> t+6. Liquidity sizing (alpha 0.5): impact drag 161 -> 85 bps/yr,
net −2.61% -> −1.62%/yr; O participation 6.3% -> 0.4%.

**Commit:** `0b3d947` (with LOG-0029)

**Next:** C/D/E signal functions on v2.

## LOG-0036 · 2026-10-19 · Phase 7c · Claude Code

**Goal:** Journal-grade figures for the v2 framework.

**Actions:**
- New `src/plotstyle.py`: LaTeX text (Computer Modern) with mathtext
  fallback, 8-9 pt type, single/full column widths, hairline axes and grid,
  colour-blind-validated categorical order and an ordinal blue ramp, shared
  `finalize` layout (figure title, one legend below the panels), PDF + 600
  dpi PNG export to `output/figures/`.
- New `src/figures.py` with all figures; plotting removed from
  `src/report.py` (tables only). Titles state what is measured and how,
  axes carry units, estimated means show 95% Newey-West intervals, cost
  components keep one colour across figures, the test sample is shaded.
- `horizon.rolling_ts_ic`: full-window minimum and a date x root panel
  carried over market holidays, so dates are never averaged over one or two
  commodities (removed spikes from ICE-only trading days).
- Notebook 03 calls `figures` and saves every figure.

**Files changed:** `src/plotstyle.py`, `src/figures.py` (new),
`src/report.py`, `src/horizon.py`, `notebooks/03_backtest_framework.ipynb`,
`docs/logs/*`

**Commands:**
- `python -m pytest -q` → 52 passed
- notebook 03 executed top to bottom (9 figures, no errors)

**Why:** Figures go into the final presentation and report; each must be
self-explanatory from its title and labels.

**Validation:** Every figure rendered and inspected for overlap, clipping and
legend placement.

**Commit:** `0b3d947` (with LOG-0029)

**Next:** C/D/E signal functions on v2.

## LOG-0037 · 2026-10-19 · Phase 7d · Claude Code

**Goal:** Merge main (A diagnosis, B pre-test, C baselines and Kalman
close-out) into `jiaheng/backtest-v2`.

**Actions:**
- Merged `origin/main` (`cb755d0`). Main keeps its IDs; this branch's entries
  were renumbered: D-010/011/012 -> D-014/015/016 and LOG-0013..0016 ->
  LOG-0033..0036 (cross-references updated).
- `src/backtest.py`: kept the `_rebalance_dates` dispatcher; its weekly
  branch now calls main's shared `curve.weekly_rebalance_dates`.
- Renamed `notebooks/03_backtest_framework.ipynb` ->
  `notebooks/06_backtest_framework.ipynb` (main uses 03-05);
  `scripts/run_all.sh` runs 03-06. It was renamed again to 07 when merged
  into main (LOG-0039); earlier entries keep the then-name.
- D-014 gained a merge note: C was implemented and closed on main by Tian;
  the C ownership in D-014 is historical.

**Commands:**
- `python -m pytest -q` → 86 passed

**Why:** Keep the branch current with main before adding more v2 figures.

**Commit:** merge commit on `jiaheng/backtest-v2`

**Next:** marginal horizon and k-profile figures; per-commodity block
bootstrap of the time-series IC.

## LOG-0038 · 2026-10-19 · Phase 7e · Claude Code

**Goal:** Add the horizon-decay, dense k-profile and per-commodity
bootstrap-IC figures to notebook 06.

**Actions:**
- `horizon.marginal_horizons` / `cumulative_horizons`: windows
  [t+h, t+h+1] and [t+1, t+1+h], h = 1..20.
- `horizon.block_bootstrap_ic`: per-commodity moving-block bootstrap
  (21-day blocks, 2,000 draws) of the time-series rank IC; percentile CI and
  two-sided p-value.
- `report.k_sweep` reports Newey-West t per layer; `figures.k_sweep` adds
  95% bands; new `figures.horizon_decay` and
  `figures.bootstrap_ic_distribution` (one vertical histogram per
  commodity with p-values).
- `plotstyle.finalize` reads existing legends and sizes multi-line titles.
- Notebook 06: new cells in section 5, dense k grid (1..60), updated
  conclusions and next steps (Chinese narrative).

**Commands:**
- `python -m pytest -q` → 87 passed
- notebook 06 executed top to bottom (11 figures, no errors)

**Validation:** Carry: marginal signed return significant only on days 1-3
(t_NW −4.6, −3.5, −2.6); bootstrap p < 0.05 for 14 of 24 commodities
(13 at p < 0.01); k = 1 → 60 cuts turnover 26× → 14.5×.

**Commit:** `feat(figures): add horizon decay, k profile and bootstrap IC` (`95db2ee`)

**Next:** D/E signals on v2.

---

## LOG-0039 · 2026-10-19 21:30 · Phase 8f · Claude Code

**Goal:** Merge `origin/jiaheng/backtest-v2` into local `main` and reconcile
it with the completed A/B/C/D work.

**Actions:**
- Merged `origin/jiaheng/backtest-v2` (`c19088f`) into `main` with `--no-ff`;
  the branch was based on `origin/main` (`cb755d0`). It brings the v2
  holdings-based simulator, layered costs, horizon diagnostics, figures,
  `07_backtest_framework.ipynb`, contract specs, transaction-cost notes and
  the mid-term slide source.
- Resolved six conflicts by union:
  - `src/backtest.py`: kept their `_rebalance_dates` dispatcher and added our
    `last_trading_day_of_month` branch, so weekly/monthly/daily all work.
  - `docs/decisions.md`: kept our D-013 (D curve momentum); renumbered the
    incoming decisions to D-014 (ownership), D-015 (daily rebalance) and
    D-016 (backtest v2).
  - `docs/backtest_framework.md`, `scripts/run_all.sh`: kept both D and v2.
  - Logs: kept our LOG-0028–0032; renumbered incoming entries to
    LOG-0033–0038; added this entry as LOG-0039.
- Renamed `notebooks/06_backtest_framework.ipynb` to
  `07_backtest_framework.ipynb` (06 is our D notebook) and updated current
  references. Earlier log entries keep the then-name.
- Updated `AGENTS.md`, `README.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`
  and `docs/onboarding.md` for the v2 merge and the D-014–D-016 decisions.
- No push performed.

**Files changed:**
- Incoming: `src/{specs,marks,sizing,costs,simulate,horizon,report,figures,plotstyle}.py`,
  `tests/test_simulate.py`, `data/metadata/contract_specs.csv`,
  `docs/transaction_costs.md`, `presentations/mid/*`,
  `notebooks/07_backtest_framework.ipynb`.
- Conflict resolution and status: `src/backtest.py`, `scripts/run_all.sh`,
  `docs/decisions.md`, `docs/backtest_framework.md`, `docs/logs/*`,
  `AGENTS.md`, `README.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`,
  `docs/onboarding.md`.

**Commands:**
- `git merge --no-ff origin/jiaheng/backtest-v2` → 6 conflicts resolved
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 101 passed

**Why:** The user wants the collaborator's v2 backtest framework and ideas
integrated with the validated A/B/C/D work, and wants the validated ideas
re-run through v2 for comparison.

**Validation:**
- 101 tests pass on the merged tree (80 before the merge).
- D monthly and collaborator daily rebalance tests both pass.
- No conflict markers; stale references to the framework notebook were
  updated to 07.
- Notebook 07 was not re-executed in this merge commit; the incoming executed
  outputs are preserved. The v2 re-runs are the next phase.

**Commit:** `merge: integrate backtest v2 framework from jiaheng`

**Next:** Run A/B/C/D signals through v2 and compare v1 vs v2; implement E
(curve dynamics) on v2; keep local unless asked to push.

---

## LOG-0040 · 2026-10-19 21:50 · Phase 8g · Claude Code

**Goal:** Make the merged v2 figure stack run without a LaTeX installation.

**Actions:**
- `src/plotstyle.tex` no longer unescapes `\%` / `\&` when falling back to
  matplotlib mathtext. A bare `%` starts a mathtext comment and swallowed the
  closing `$`, so notebook 07 failed on the capacity title
  `Gross ($-0.48\%$ p.a., ...)`.
- Added `tests/test_plotstyle.py` for the two escape paths.
- Executed notebook 07 end to end into a temporary directory; no error
  outputs.

**Files changed:** `src/plotstyle.py`, `tests/test_plotstyle.py`,
`docs/logs/*`

**Commands:**
- `jupyter nbconvert --execute ... notebooks/07_backtest_framework.ipynb`
  → OK
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 103 passed
- `jq` check of the executed notebook → 0 error outputs

**Why:** The v2 framework must run in this environment, which has no LaTeX;
mathtext fallback is the supported path.

**Validation:**
- Notebook 07 executes top to bottom; A results match the incoming outputs
  (gross −0.48%/yr at USD 10m).
- 103 tests pass.

**Commit:** `fix(plotstyle): keep math escapes in mathtext fallback`

**Next:** Re-run A/B/C/D through v2; compare v1/v2.

---

## LOG-0041 · 2026-10-19 22:10 · Phase 9a · Claude Code

**Goal:** Pre-register the v2 extension and re-run conventions before
producing any A/D/C/B result.

**Actions:**
- Added D-017: optional hedge-ratio legs, `legs_from_rows`, `resize_key`,
  and B's within-root exception to D-016's time-series-only rule.
- Added D-018: v2 re-run universe, sizing, costs, calendar overrides and
  reporting conventions.
- No code, notebook or data changes; no results produced yet.

**Files changed:**
- `docs/decisions.md`, `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- none

**Why:** Avoid result-driven changes to the universe, costs or execution
once the v2 numbers are visible.

**Validation:**
- D-017/D-018 reference D-016 and the affected signals/variants.
- No locked D=10 / delivery-month / dollar-primary conventions changed.

**Commit:** `docs(decisions): pre-register v2 extensions and rerun conventions`

**Next:** Implement core v2 fixes and tests.

---

## LOG-0042 · 2026-10-19 22:30 · Phase 9b · Claude Code

**Goal:** Fix v2 reporting and resize-key correctness, and add hedge-ratio /
multi-leg leg-building support.

**Actions:**
- `SimResult.calendar`; `_daily` reindexes to the full marks calendar and
  zero-fills flat days, so `performance_table`, `root_table`,
  `capacity_curve` and figures annualise over the full sample.
- `_root_book` key is now `(group_id, target, resize_key)`. `resize_key`
  is optional and defaults to `""`; `_root_book` raises if a root-date has
  multiple non-flat groups or mixes flat and active rows.
- `sizing.LEG_COLUMNS` gains `resize_key`.
- `sizing.legs_from_signal` accepts an optional `hedge_ratio` column:
  far units = `-sign(target) * h`; invalid h -> explicit flat; `resize_key`
  = `_h{round(h, 6)}`.
- `sizing.legs_from_rows` maps explicit multi-leg rows (netting shared
  contracts) to `LEG_COLUMNS` with a composition `resize_key`.
- Empty-trade / pure-flat results now return typed empty tables instead of
  failing on dtype merges.
- Added tests in `tests/test_simulate.py` and `tests/test_sizing.py`.

**Files changed:** `src/simulate.py`, `src/sizing.py`, `src/report.py`,
`tests/test_simulate.py`, `tests/test_sizing.py`, `docs/logs/*`

**Commands:**
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 114 passed

**Why:** D-017/D-018 require hedge-ratio and multi-leg signals to resize
correctly, and flat days must not be dropped from annualisation.

**Validation:**
- Existing 103 tests plus 11 new tests pass.
- Flat-tail test annualises over 60 days; notional-ratio daily changes do
  not trigger resizes; `resize_key` changes trigger exactly one resize.
- Pure-flat result returns 10 zero-return days.

**Commit:** `fix(simulate): calendar annualization, resize keys, hedge legs`

**Next:** Add v2 signal adapters for A/D/C/C-OLS/C-Kalman/B.

---

## LOG-0043 · 2026-10-19 22:40 · Phase 9c · Claude Code

**Goal:** Add v2 adapters for A, D, C (1:1/OLS/Kalman) and B.

**Actions:**
- Added `src/v2_signals.py`: `load_v2_inputs`, `a_legs`, `d_legs`,
  `c_legs(method="1:1"|"ols"|"kalman")`, `b_legs`, plus explicit-flat,
  weekly-h-snap and pair-change helpers.
- A/D/C use `legs_from_signal`; C hedge passes an optional `hedge_ratio`
  (far units = `-sign(target) * h`) and snaps h to weekly evaluation dates.
- B reuses `b_pre_test.build_b_targets`, drops zero-unit validation rows,
  nets shared contracts, samples to weekly + main-pair change dates, and
  builds explicit multi-leg rows with `legs_from_rows`.
- Added `tests/test_v2_signals.py` (B netting, weekly h snap, flats).

**Files changed:** `src/v2_signals.py`, `tests/test_v2_signals.py`,
`docs/logs/*`

**Commands:**
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 117 passed
- Real-data smoke test: A/D/C/B/OLS/Kalman all produced legs and results.

**Why:** D-017/D-018 require the C hedge variants and B to run through v2.

**Validation:**
- B synthetic fixture nets P2 +1 / P3 −2 / P4 +1 and one group.
- Weekly snapshot uses evaluation and pair-change dates; invalid h flats.
- Real-data runs produced non-empty legs for all six strategies.

**Commit:** `feat(v2): add A/D/C/C-hedge/B signal adapters`

**Next:** Add the rerun driver, notebook 08 and refreshed notebook 07.

---

## LOG-0044 · 2026-10-19 22:55 · Phase 9d · Claude Code

**Goal:** Run the v2 re-runs and add notebook 08.

**Actions:**
- Added `src/v2_rerun.py` (`RerunSettings`, `run_strategy`, `run_all`,
  `save_results`) and `scripts/run_v2_rerun.py` with caching and
  `--strategies`.
- Ran A/D/C/C-OLS/C-Kalman/B at USD 10m; wrote `output/v2_rerun/*.csv`.
- Added `notebooks/08_v2_rerun.ipynb` (conventions, full/train/test tables,
  framework comparison, findings) and executed it.
- Re-executed notebook 07 after the calendar/resize fixes.
- Added the driver and notebook 08 to `scripts/run_all.sh`.

**Results (full sample, gross → all-in net):**
- A: −0.48% → −2.61%
- D: +0.22% → −1.42%
- C 1:1: +0.61% → −3.70%
- C OLS: +0.12% → −3.06%
- C Kalman: +0.61% → −6.10%
- B: −1.13% → −4.47%

Test gross: D −0.21%, B −1.23%; C +0.16%, C-Kalman +0.98%, C-OLS −0.01%.
All remain negative/mixed; no test tuning.

**Files changed:** `src/v2_rerun.py`, `scripts/run_v2_rerun.py`,
`scripts/run_all.sh`, `notebooks/07_backtest_framework.ipynb`,
`notebooks/08_v2_rerun.ipynb`, `docs/logs/*`

**Commands:**
- `~/miniconda3/envs/mfe/bin/python scripts/run_v2_rerun.py \
  --strategies a,d,c,c_ols,c_kalman,b --force`
- `jupyter nbconvert --execute ... notebooks/08_v2_rerun.ipynb` → OK
- `jupyter nbconvert --execute ... notebooks/07_backtest_framework.ipynb` → OK
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 117 passed

**Why:** The user asked to re-run A/D/C through v2 and integrate C hedge,
Kalman and B.

**Validation:**
- Notebooks 07/08 have zero error outputs.
- `output/v2_rerun/comparison.csv` has full/train/test × four layers for
  all six strategies.
- A's notebook 07 gross is unchanged at −0.48%; turnover 26.133× after
  the full-calendar fix.

**Commit:** `feat(v2): run A/D/C/C-hedge/B and add notebook 08`

**Next:** Write the v1/v2 comparison doc and update status docs.

---

## LOG-0045 · 2026-10-19 23:10 · Phase 9e · Claude Code

**Goal:** Document the v1/v2 comparison and close out the v2 re-run phase.

**Actions:**
- Added `docs/v1_v2_comparison.md` with the architecture table, v1 vs v2
  results, adapter mapping, fixed bugs and remaining caveats.
- Updated `docs/backtest_framework.md` for hedge_ratio, legs_from_rows,
  resize_key, full-calendar annualization, adapters and D-017/D-018.
- Updated `docs/data_dictionary.md` §10.4b for the v2 leg schema.
- Updated README/AGENTS/HANDOFF/PROGRESS/onboarding for notebook 08,
  D-017/D-018 and the negative/mixed results.
- No push.

**Files changed:** `docs/v1_v2_comparison.md`, `docs/backtest_framework.md`,
`docs/data_dictionary.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`,
`docs/onboarding.md`, `README.md`, `AGENTS.md`, `docs/logs/*`

**Commands:**
- `git diff --check` → clean
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 117 passed

**Why:** Close out the v2 re-run phase and give the next agent a single
comparison reference.

**Validation:**
- Results in the doc match `output/v2_rerun/comparison.csv`.
- Notebooks 07/08 have no error outputs.
- No locked conventions changed; D-017/D-018 are pre-registered.

**Commit:** `docs(v2): record v1/v2 comparison and close out reruns`

**Next:** E (Nelson–Siegel); H; no push.

---

## LOG-0046 · 2026-10-19 23:15 · Phase 9f · Claude Code

**Goal:** Record the agreed failure-diagnostics plan for A/B/D on top of the
v2 reruns before implementation.

**Actions:**
- Added `docs/diagnostics_plan.md`: scope, agreed decisions, per-idea cards,
  statistical rules, existing v2 diagnostics, caveats, proposed deliverables.
- Added a pointer in `docs/HANDOFF.md` §9.
- No code or result changes.

**Files changed:** `docs/diagnostics_plan.md`, `docs/HANDOFF.md`,
`docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `git diff --check` → clean
- No tests run; docs-only change.

**Why:** Preserve the discussion decisions so the next conversation can
confirm D-specific tests and implement without re-deriving the plan. The plan
uses the v2 reruns (`output/v2_rerun/`, `docs/v1_v2_comparison.md`) as input
and does not mix v1/v2 numbers.

**Validation:**
- Headline numbers match `output/v2_rerun/comparison.csv`.
- Scope follows D-014 (Tian: A/D; C/E cited) and D-016 (per-root time-series,
  no cross-sectional ranking).
- No locked convention changed.

**Commit:** `docs(diagnostics): record failure-diagnostics plan for A/B/D`

**Next:** Next conversation confirms D mechanism tests and whether to add the
A v1-aligned robustness; then implement `src/diagnostics.py` and notebook 09.

---

## LOG-0047 · 2026-10-19 23:30 · Phase 9g · Claude Code

**Goal:** Make the v2 re-runs the official/final results while keeping v1 as
a historical baseline, per the user's decision.

**Actions:**
- Added D-019: official results are v2 (`notebooks/08_v2_rerun.ipynb`,
  `output/v2_rerun/comparison.csv`, `docs/v1_v2_comparison.md`); v1
  notebooks/results are historical and must be labeled `v1`.
- README: replaced the headline status with the v2 final result table;
  v1 is explicitly historical.
- HANDOFF/PROGRESS/onboarding/backtest_framework: v2 official, v1 historical.
- No v1 notebook was rewritten or deleted; no code or data changed.
- No push.

**Files changed:** `docs/decisions.md`, `README.md`, `AGENTS.md`,
`docs/HANDOFF.md`, `docs/PROGRESS.md`, `docs/onboarding.md`,
`docs/backtest_framework.md`, `docs/v1_v2_comparison.md`, `docs/logs/*`

**Commands:**
- `git diff --check` → clean
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 117 passed (docs-only)

**Why:** The user chose the v2 results as the final version, with v1 kept
for traceability.

**Validation:**
- Headline numbers match `output/v2_rerun/comparison.csv`.
- D-019 is consistent with D-016/D-018 and does not change locked
  conventions.
- No v1 notebook was modified.

**Commit:** `docs(final): make v2 results the official results`

**Next:** E and H; no push.

---

## LOG-0048 · 2026-10-19 23:50 · Phase 10a · Claude Code

**Goal:** Make v2 holdings valuation and per-idea position charts reusable.

**Actions:**
- Added `SimResult.positions` (`date, root, contract, n, mark, point_value,
  signed_notional, gross_notional, pnl`) without changing `holdings`.
- Added `report.overall_sharpe(res, layer="ret_net_all")`.
- Added `figures.position_panel` and `figures.positions`: month-end signed
  gross-position heatmap (nearest-expiry leg direction) plus gross exposure /
  turnover.
- Added `v2_rerun.save_strategy` so one strategy cannot overwrite
  `comparison.csv`.
- Fixed `plotstyle.tex` to strip `\ ` spacing in the mathtext fallback.
- Added tests for positions, overall Sharpe, position panels, save_strategy
  and spacing.

**Files changed:**
- `src/simulate.py`, `src/report.py`, `src/figures.py`, `src/v2_rerun.py`,
  `src/plotstyle.py`
- `tests/test_simulate.py`, `tests/test_figures.py`,
  `tests/test_v2_rerun.py`, `tests/test_plotstyle.py`

**Commands:**
- `python -m pytest -q` → 124 passed
- A validation: gross −0.484%, all-in net −2.610%, overall Sharpe −2.595

**Why:** The per-idea notebooks need accurate positions; net signed notional
is near zero for calendar spreads, so the heatmap uses the nearest-expiry leg
direction and the root's gross notional.

**Validation:** tests pass; A performance unchanged; position panel is
24 roots × 490 months with a range of about ±25% of capital.

**Commit:** `feat(v2): expose valued positions and add position-book figure`

**Next:** Build notebooks 10–13.

---

## LOG-0049 · 2026-10-19 23:52 · Phase 10b · Claude Code

**Goal:** Add one notebook per trading idea, each with PnL, positions and one
overall Sharpe.

**Actions:**
- Added `10_idea_a_carry.ipynb`, `11_idea_b_adjacent_carry.ipynb`,
  `12_idea_c_mean_reversion.ipynb` (1:1 / rolling OLS / Kalman) and
  `13_idea_d_curve_momentum.ipynb`.
- Each notebook runs only its own v2 strategy, saves
  `output/v2_rerun/<name>_{performance,root}.csv` and
  `output/v2_rerun/<name>_positions_month_end.csv`, and displays
  `figures.nav_by_cost_layer` plus `figures.positions`.
- The C notebook runs the three pre-registered variants on one shared
  `load_v2_inputs` panel and reports one Sharpe per variant.
- Updated `scripts/run_all.sh` to execute 00/01 and 10–13; kept
  `scripts/run_v2_rerun.py` as the optional aggregate utility for
  `comparison.csv`.
- Executed all four notebooks and cleaned volatile metadata.

**Files changed:**
- `notebooks/10_idea_a_carry.ipynb`, `11_idea_b_adjacent_carry.ipynb`,
  `12_idea_c_mean_reversion.ipynb`, `13_idea_d_curve_momentum.ipynb`
- `scripts/run_all.sh`, `scripts/run_v2_rerun.py`

**Commands:**
- `jupyter nbconvert --execute --to notebook --inplace ...` for 10–13
- `python scripts/clean_notebook_metadata.py ...`
- `python -m pytest -q` → 124 passed

**Why:** The user wants each idea in one notebook, with the same three
deliverables, instead of the old multi-notebook layout.

**Validation:** all notebooks have zero error outputs; performance matches
the existing v2 tables (A −0.484 / −2.610, B −1.131 / −4.469, C1 +0.614 /
−3.695, C2 +0.124 / −3.060, C3 +0.613 / −6.099, D +0.219 / −1.418); figures
are in `output/figures/idea_*`.

**Commit:** `feat(notebooks): add one notebook per trading idea`

**Next:** Retire notebooks 02–08 and update docs/logs (D-020).

---

## LOG-0050 · 2026-10-19 23:55 · Phase 10c · Claude Code

**Goal:** Retire the superseded notebooks and record the one-notebook-per-idea
layout (D-020).

**Actions:**
- Deleted `02_carry`, `03_mean_reversion`, `04_a_diagnose`, `05_b_pretest`,
  `06_curve_momentum`, `07_backtest_framework`, `08_v2_rerun` from the working
  tree. They remain in git history with their original outputs.
- Added D-020: 00/01 are the data layer; 10–13 are one notebook per idea;
  each shows PnL, positions and one full-sample all-in net Sharpe. D-019
  clause 2 (keep v1 notebooks) is superseded for layout; v2 remains official.
- Added `docs/notebook_history.md` with the old-to-new mapping, last commits
  and `git show` recovery commands.
- Updated current-state docs and scripts: README, AGENTS, HANDOFF, PROGRESS,
  onboarding, backtest_framework, v1_v2_comparison, diagnostics_plan,
  a_negative_result, b_pretest, data_dictionary and project_brief.
- No push.

**Files changed:**
- Deleted: `notebooks/02_carry.ipynb` … `notebooks/08_v2_rerun.ipynb`
- Added: `docs/notebook_history.md`
- Updated: `README.md`, `AGENTS.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`,
  `docs/onboarding.md`, `docs/backtest_framework.md`,
  `docs/v1_v2_comparison.md`, `docs/diagnostics_plan.md`,
  `docs/a_negative_result.md`, `docs/b_pretest.md`,
  `docs/data_dictionary.md`, `docs/project_brief.md`, `docs/decisions.md`

**Commands:**
- `python -m pytest -q` → 124 passed
- `grep -rnE "02_carry|...|08_v2_rerun"` → only historical/retired notes
- `ls notebooks/*.ipynb` → 00, 01, 10, 11, 12, 13 only

**Why:** The user wants each idea in exactly one notebook and no historical
result tables in notebooks; history belongs in docs/logs and git.

**Validation:** all four idea notebooks execute with zero errors; A/B/C/D
performance matches the v2 tables; old notebooks recoverable via
`docs/notebook_history.md`.

**Commit:** `refactor(notebooks): retire superseded notebooks and document layout`

**Next:** Robustness/diagnostics later; no push.
## LOG-0051 · 2026-10-19 · Phase 8 · Claude Code

**Goal:** Fix the replication protocol for idea E (Bianchi et al. 2023)
before writing code.

**Actions:**
- Read §2, §3, §4.1, §5.5 and Tables 3, 9, 10 of `paper/predict_curve.pdf`.
- Added D-021: order of work, four-contract eligibility (skip for snapshot
  OLS, three allowed for Kalman), maturity to last trading day in months,
  λ_t = 1.7933 / M̄_t, S/C signals and instruments, tradable vs paper timing,
  time-series aggregation, samples, conditional extensions, costs.

**Why:** The paper's λ rule makes the fit a 1-dof OLS, its non-NS
benchmark already earns most of the Sharpe, and its trades fill at the
signal's own settle; each needs an explicit test.

**Commit:** `docs(decisions): add D-021 idea E replication protocol` (`6080881`)

**Next:** `src/nelson_siegel.py` and tests.

## LOG-0052 · 2026-10-19 · Phase 8b · Claude Code

**Goal:** Implement and run idea E (D-021) with λ as a causal
hyperparameter; resize the framework to a USD 1m book.

**Actions:**
- New `src/nelson_siegel.py`: last trading days (censored contracts by root
  median offset), eligible curve, four-contract wide panel, NS loadings,
  batched OLS with sub-model R², λ rules (`paper`, `fixed_m`,
  `rolling_ssr`), ΔβS/ΔβC and ΔS signals without differencing across gaps,
  S pair panel with explicit flats, C butterfly legs, coverage and Table 3
  summaries, strategy builder.
- `src/simulate.py`: `round_lots`; typed empty trade/status tables (a book
  that rounds to zero lots no longer crashes). `src/costs.py`:
  `proportional_bps`, `paper_scenarios()`. `src/report.py`:
  `execution_free_returns`, `return_summary`. `src/figures.py`: `ns_betas`,
  `lambda_validation`, `timing_comparison`; `[t, t+1]` tick label.
- `notebooks/14_idea_e_nelson_siegel.ipynb` (Chinese narrative); the v2 framework moved to
  USD 1m with a USD 100k–100m capacity grid; D-022; cost doc updated.

**Commands:**
- `python -m pytest -q` → 95 passed
- notebooks 06 and 07 executed top to bottom, no errors

**Validation:** NS R² 96.6% / 81.5% / 43.3% (paper 96.5 / 82.7 / 37.5).
Paper timing on the paper sample: 3.55%/yr, Sharpe 2.03; tradable: −0.18%/yr
(t = −0.6). Validation selects `rolling_ssr` (Sharpe 0.017); test gross
+0.15%/yr (t = 0.2). Whole lots at USD 100k: 2,957 root-days held vs
137,288 fractional.

**Commit:** `feat(nelson-siegel): replicate idea E; lambda selection; $1m book` (`56ecff6`)

**Next:** D (curve momentum) on v2.

## LOG-0053 · 2026-10-20 · Phase 8c · Claude Code

**Goal:** Idea E follow-ups requested after D-022 (D-023).

**Actions:**
- `nelson_siegel.fit_quality` (in-sample, adjusted and leave-one-out R² of
  nested models); `horizon.block_bootstrap_mean` (mean or median);
  `figures.bootstrap_distribution` (generic, signed colours) with the IC
  figure as a wrapper; `figures.k_sweep_timing`; sub-period NAV.
- `simulate.same_settle` and `report.k_sweep(same_settle=..., start, end)`
  for paper-timing diagnostics through the cost pipeline.
- New `src/ns_kalman.py`: random-walk DNS filter with causal (r, q)
  selection, LOO and one-step metrics, Kalman signal strategy, A/B table.
- Notebook 07: sections 2b, 5b, 5c and a full section 11 A/B; conclusions.
- Tests: fit quality, block bootstrap, same-settle timing, Kalman filter.

**Commands:**
- `python -m pytest -q` → 99 passed
- notebook 14 executed top to bottom (18 figures, no errors)

**Validation:** see D-023 numbers.

**Commit:** `feat(nelson-siegel): fit significance, paper-timing costs, Kalman A/B` (`aa28cd6`)

**Next:** merge into main; D (curve momentum).

## LOG-0054 · 2026-10-20 · Phase 11 · Claude Code

**Goal:** Merge the cloud E work into local `main` while keeping the D-020
per-idea notebook layout.

**Actions:**
- Merged `origin/main` (PR #1 + E follow-ups) into local `main`.
- Kept local D-001–D-020; imported E decisions as D-021–D-023 and added
  D-024 for the layout reconciliation.
- Renumbered E log entries to LOG-0051–LOG-0053; added this entry.
- Added `notebooks/14_idea_e_nelson_siegel.ipynb`; kept notebooks 02–08
  retired.
- Ported E method additions: `simulate.same_settle`, `simulate.round_lots`,
  `horizon.block_bootstrap_mean`, `report.execution_free_returns`,
  `report.return_summary`, `ns_kalman`, generic bootstrap/timing figures.
- Updated `scripts/run_all.sh`, docs and tests references.

**Why:** The cloud PR merged the E work while local main had the newer
D-020 layout; the two histories collided on decision, log and notebook IDs.

**Commands:**
- `python3 -m pytest -q`
- `git merge --no-ff origin/main`

**Validation:** tests pass; notebooks are not re-executed in this merge.

**Commit:** `merge: integrate cloud E work into the D-020 notebook layout`

**Next:** Align A's information tests with `horizon.horizon_profile`,
`ts_ic`/`block_bootstrap_ic`, and `block_bootstrap_mean`.

## LOG-0055 · 2026-10-20 · Phase 12 · Claude Code

**Goal:** Test the sign-flipped A carry as the adopted candidate signal using
gross, execution-free information diagnostics, without changing the official
v2 A result.

**Actions:**
- Added the period-sliced diagnostics layer `src/diagnostics.py` (full/train/
  test slicing, horizon profiles, IC, own-history bins, per-root IC/signed
  bootstraps, 0.5x signed returns, period summary) and
  `tests/test_diagnostics.py` (6 synthetic tests).
- Notebook 10: load `inputs` once and pass them to the official A rerun; added
  §7 with the flip signal, signed horizon profile, marginal/cumulative decay,
  IC and bins, block-bootstrap IC, same-settle vs t+1 timing, per-root signed
  returns/stability, and test-period MDE. Renamed the old reading to §8 and
  updated it.
- Adopted `target_flip = -sign(spread_dollar)` and
  `score_flip = -carry_ann`; masked illiquid pair-dates and non-positive leg
  prices to match the traded universe; no signal/universe/cost logic changes.
- Added D-025 and updated `docs/a_negative_result.md`,
  `docs/diagnostics_plan.md`, `README.md`, `docs/HANDOFF.md`,
  `docs/PROGRESS.md`.

**Files changed:**
- `src/diagnostics.py` (new)
- `tests/test_diagnostics.py` (new)
- `notebooks/10_idea_a_carry.ipynb`
- `docs/decisions.md`
- `docs/a_negative_result.md`
- `docs/diagnostics_plan.md`
- `README.md`
- `docs/HANDOFF.md`
- `docs/PROGRESS.md`
- `docs/logs/AGENT_LOG.md`
- `docs/logs/INDEX.md`

**Commands:**
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 142 passed
- `~/miniconda3/envs/mfe/bin/jupyter nbconvert --execute --to notebook
  --inplace --ExecutePreprocessor.timeout=900 notebooks/10_idea_a_carry.ipynb`
- `~/miniconda3/envs/mfe/bin/python scripts/clean_notebook_metadata.py
  notebooks/10_idea_a_carry.ipynb`

**Why:** The original A direction is a documented negative, but the observed
sign is opposite. The user adopted the sign-flipped rule as a candidate and
asked for gross signal-information tests before portfolio costs. Full is
descriptive and 2016–2026 is a post-hoc confirmatory slice; no parameter was
chosen on test.

**Validation:** official A v2 numbers unchanged (full gross −0.484%, all-in
−2.610%, overall net Sharpe −2.595; test gross −0.272%, all-in −1.464%).
Flip gross results: full +0.631%/yr (Sharpe 0.633, NW t 4.286), train
+0.694% (0.672, 4.056), test +0.455% (0.512, 1.580; 80% MDE Sharpe 0.843).
5-day ALL IC 0.048 / 0.045 / 0.071; per-root bootstrap p<0.05 11/24, 10/24,
8/24. Verdict: suggestive, not confirmed. Notebook executes with no errors;
figures `output/figures/idea_a_flip_*` and tables `output/v2_rerun/a_*.csv`
are gitignored.

**Commit:** `feat(diagnostics): add flip-carry information diagnostics to notebook 10`
(`this commit`).

**Next:** Review §7; then the final portfolio's cost/sizing layer. Do not tune
the flip on 2016–2026. The A failure-diagnostic card, B and D cards remain
deferred.

## LOG-0056 · 2026-10-20 · Phase 12 · Claude Code

**Goal:** Add B-flip as a post-hoc, gross-only signal-research headline in
notebook 11, with the original B negative result retained as history.

**Actions:**
- Defined D-026: long the lowest-carry adjacent spread, short the highest;
  D=10 eligible, `min_adv=100`, USD 10m, weekly, k=1; gross headline, v2
  cost layers as a diagnostic; raw exact flip as a reference; static
  front/back as the maturity control.
- Added `b_pre_test.build_adjacent_carries_from_pairs`,
  `select_adjacent`, and refactored `build_b_targets` to accept an eligible
  `adjacent` panel plus `long_rule`/`short_rule`; original defaults unchanged.
- Added `v2_signals.load_b_adjacent`, `b_flip_legs`, `b_static_legs`,
  `flip_legs`.
- Added `src/b_flip.py`: run helpers, horizon/timing profiles, per-root
  bootstrap, random-ranking placebo, root jackknife, raw exact-flip helper.
- Added `figures.nav_compare` and `figures.placebo_distribution`.
- Rewrote notebook 11: B-flip headline (gross-only), timing/horizon,
  static control, placebo, per-root bootstrap, annual/rolling, jackknife,
  default cost/capacity/$1m whole-lot profile, original B historical section,
  and a candidate-tuning list. No k/D/ADV grid in this pass.
- Added synthetic tests; updated README, AGENTS, HANDOFF, PROGRESS,
  `docs/b_pretest.md`, `docs/v1_v2_comparison.md`, `scripts/run_all.sh`.

**Files changed:**
- `src/b_pre_test.py`, `src/v2_signals.py`, `src/b_flip.py`,
  `src/figures.py`
- `tests/test_b_pre_test.py`, `tests/test_v2_signals.py`,
  `tests/test_b_flip.py`
- `notebooks/11_idea_b_adjacent_carry.ipynb`
- `docs/decisions.md`, `docs/logs/*`, `docs/HANDOFF.md`,
  `docs/PROGRESS.md`, `docs/b_pretest.md`, `docs/v1_v2_comparison.md`
- `README.md`, `AGENTS.md`, `scripts/run_all.sh`

**Commands:**
- `python -m pytest -q` → 147 passed
- `jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=1800 notebooks/11_idea_b_adjacent_carry.ipynb`

**Why:** B-flip is a new hypothesis prompted by the original B's precisely
estimated negative gross sign. The user wants a gross signal study for later
combination, not a standalone strategy and not a rescue of B.

**Validation:**
- B-flip D=10 + min_adv=100: gross +0.499%/yr, vol 0.469%, Sharpe 1.064,
  t_NW 7.14, turnover 31.4×; raw exact flip +1.131%/yr, Sharpe 1.263;
  static front/back +0.108%/yr, Sharpe 0.208.
- Signal level: 1:6 +3.98 bps (t 9.6), 1:21 +12.4 bps (t 8.6); same-settle
  0:1 +2.59 bps (not tradable); 37/41 positive years; 22/24 roots positive
  mean; random-ranking placebo p<0.001.
- Standalone net is negative: half-spread 84 bps/yr vs gross 50 bps/yr.
- Original B is unchanged: gross −1.131%/yr, all-in −4.469%/yr.

**Commit:** `feat(b-flip): add gross-only within-curve carry-reversal signal research`

**Next:** Review the default B-flip results; decide whether to run any of the
deferred tuning directions (k-smoothing, D=5/20, ADV=1000, rebalance
frequency, liquidity weighting). Then test B-flip correlation/incremental
value against A/C/D for combination.

---

## LOG-0057 · 2026-10-20 · Phase 12 · Claude Code

**Goal:** Pre-register and run the D-027 daily C information audit, isolated
from the parallel A/B/D worktrees.

**Actions:**
- Added D-027 (accepted) to `docs/decisions.md`: 1986–2005 train,
  2006–2015 validation, 2016–2026 test once; daily C1/C2/C3; sequential
  adoption with paired block bootstrap; alpha gate; stage firewall.
- `src/signals.py`: `evaluation="daily"` support in
  `mean_reversion_signal`; weekly default and behavior unchanged.
- `src/c_daily.py`: daily C1/C2/C3 legs, gross-only simulation, stage-1
  truncation, per-root metrics, paired bootstrap, sequential selection and
  validation/test gates.
- `src/c_audit.py`: event study, IC + block bootstrap, same-settle vs
  tradable timing, AR(1) persistence, nested predictive regressions,
  circular-shift placebo and jackknife.
- `scripts/run_c_daily_audit.py`: stage-1 (truncated at 2015-12-31) and
  stage-2 (one test read, marker file) runner; outputs under
  `output/c_daily_audit/` (gitignored).
- `notebooks/12_idea_c_mean_reversion.ipynb`: sections 9–11, separate from
  the official weekly D-019 results.
- Tests: `tests/test_c_daily.py`, `tests/test_c_audit.py`; updated
  `tests/test_signals.py` for daily evaluation.

**Files changed:**
- `docs/decisions.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`, `README.md`
- `src/signals.py`, `src/c_daily.py`, `src/c_audit.py`
- `scripts/run_c_daily_audit.py`
- `notebooks/12_idea_c_mean_reversion.ipynb`
- `tests/test_signals.py`, `tests/test_c_daily.py`, `tests/test_c_audit.py`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 145 passed
- `python scripts/run_c_daily_audit.py --stage stage1`

**Why:** The user wants C treated as a candidate alpha signal and switched to
daily for consistency with the other signals. The audit measures gross
information before any cost work and fixes the selection/gate rules ex ante.

**Validation:**
- Weekly C1/C2/C3 gross performance matches the existing
  `output/v2_rerun/c_*_performance.csv` within tolerance.
- Stage-1 artifacts use marks truncated at 2015-12-31; test not read.
- Daily validation gross SR: C1 0.240, C2 0.265, C3 −0.332; sequential
  selection keeps C1; alpha gate fails (0.240 < 0.4); 15/24 roots positive.
- Weekly validation gross SR: C1 0.046, C2 0.338, C3 −0.148; daily improves
  C1 but not C2/C3, and C1 remains below the gate.
- Diagnostics: ALL IC 0.0095/0.0027/−0.0009/0.0209 at 1/5/10/20 days;
  same-settle SR 0.419 vs tradable `[t+1,t+2]` 0.064; execution-free
  tradable SR 0.064 vs placebo mean −0.073, two-sided p 0.656; nested
  OOS R² negative for all models; jackknife SR 0.119–0.448.
- Diagnostics and weekly-vs-daily comparison are in notebook 12 §9–11 and
  `output/c_daily_audit/stage1_train_validation/`.

**Commit:** `feat(c-daily): add daily C information audit (D-027)` (`this commit`).

**Next:** C remains closed; daily results are retained. Any new C variant is a
separate pre-registered project; no grid search and no test tuning.

---

## LOG-0058 · 2026-10-20 · Phase 12 · Claude Code

**Goal:** Add a cost-free signal-validity study for idea D (D-028), keeping
the D-013 trading baseline unchanged and doing the work in an isolated
worktree because several agents share the repo.

**Actions:**
- Created worktree branch `feat/d-signal-validity` from `main` at
  `f624dd2`; symlinked the gitignored processed parquet into
  `data/processed/` (not committed).
- Added `src/d_validity.py`: monthly panel builder, rank-index t+1 forward
  returns at 1/3/6/12 months, same-close diagnostic, per-root IC/hit
  rate/expanding quantiles, nested adjusted R² and residual IC, stability,
  placebo, FDR, max-|IC| benchmark, and `save_tables`.
- Added `tests/test_d_validity.py` (9 synthetic tests).
- Added notebook 13 section 7 (“D signal validity”) and updated section 8
  (“Reading”) with the validity verdict; executed notebook 13.
- Added D-028 to `docs/decisions.md`; updated `docs/diagnostics_plan.md`
  §3.5 and §8, `docs/HANDOFF.md` §0c, `docs/PROGRESS.md`.
- Did not edit the main working tree; its uncommitted A/B peer work remains
  untouched. Did not import or depend on the untracked
  `src/diagnostics.py`/`src/b_flip.py`.

**Files changed:**
- `src/d_validity.py` (new)
- `tests/test_d_validity.py` (new)
- `notebooks/13_idea_d_curve_momentum.ipynb`
- `docs/decisions.md`, `docs/diagnostics_plan.md`, `docs/HANDOFF.md`,
  `docs/PROGRESS.md`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 145 passed
- `jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=900 notebooks/13_idea_d_curve_momentum.ipynb` → OK
- `python scripts/_run_d_validity.py` (temporary smoke driver, removed)

**Why:** D is a negative/mixed trading baseline. The user wants to know
whether the score contains valid information at all before deciding whether
to spend effort on costs or parameter choices. The study uses default D-013
params and no test-set tuning.

**Validation:**
- 1m mean per-root IC 0.049 (NW t 3.48); 79% of roots positive; only 2/24
  survive FDR (LC, W), 7/24 nominal p<0.05.
- IC rises with horizon: 0.140 / 0.173 / 0.190 at 3/6/12m.
- Expanding quintiles are non-monotonic.
- Incremental adjusted R²: +D 0.0069, +A 0.0143, +C 0.0158; all CIs include
  zero. Residual IC gain 0.0162 (18/24 roots positive, 2/24 significant).
- Static always-long 11.1 bp/month; D timing spread 11.2 bp/month.
- Stability: 1986–1999 0.013, high-vol −0.007, rolling 36m positive share
  39%.
- Placebo: block-shuffle p<0.001; lag 1/6m 0.016/0.018; future lead 0.028.
- Notebook 13 executes top-to-bottom; no errors.
- Tests are synthetic and need no raw data.

**Commit:** `feat(validity): add D signal-validity diagnostics`

**Next:** merged into `main` with the parallel A/B/C work; parameter response
curves and main-spec selection are a separate phase; do not tune on the
2016–2026 test sample.

---

## LOG-0059 · 2026-10-20 · Phase 13 · Claude Code

**Goal:** Merge the four parallel idea worktrees (A flip diagnostics, B-flip,
C daily audit, D signal validity) into local `main` after all agents finished.

**Actions:**
- Committed the two worktrees whose changes were still uncommitted: A
  `976e923` (D-025) and C `39d85a8` (D-027). B (`ee36a9e`) and D (`fd9a58d`)
  had already committed their work.
- Resolved the four-way decision/log ID collision (all four had claimed
  D-025 / LOG-0055): A keeps D-025 / LOG-0055; B is D-026 / LOG-0056
  (`76bb653`), C D-027 / LOG-0057 (`48d5b8f`), D D-028 / LOG-0058
  (`f907ea8`).
- Merged with `--no-ff` in order A (`0b231b2`), B (`e4ea216`), C
  (`4ec1129`), D (`b02c9dd`), combining every agent's README, HANDOFF,
  PROGRESS, decisions, diagnostics-plan and log edits.
- Added the missing D-026/D-027 summary rows, refreshed the INDEX hashes and
  the test count, and recorded this entry.

**Commands:**
- `python -m pytest -q` → 171 passed
- Four `git merge --no-ff` runs; conflict markers verified at zero.

**Why:** The user ran A/B/C/D in parallel worktrees and asked for one merge
into `main` once all agents were done.

**Validation:** All four feature branches are ancestors of `main`; the merged
tree passes the full synthetic suite. Notebooks were executed by the
individual agents and were not re-run during this merge. Nothing was pushed;
`main` is local only.

**Commit:** `this commit`.

**Next:** review the four merged sections; choose the next research step
(H holding-period scan, or the A-flip cost/sizing layer). Worktrees and their
branches are intentionally left in place.

---

## LOG-0060 · 2026-10-20 · Phase 13 · Claude Code

**Goal:** Persist the daily C artifacts that D-027 did not save and add a
descriptive full-sample presentation to notebook 12 (D-029), without changing
the D-027 gate/selection or the official weekly D-019 results.

**Actions:**
- Added `save_variant_artifacts`, `load_variant_artifacts` and
  `check_full_read_allowed` to `src/c_daily.py`. `run_variant` now retains the
  daily signal path and reuses it for leg construction (avoiding a second C3
  Kalman build). Artifacts: `signals/{c1,c2,c3}.parquet`,
  `legs/*.parquet`, `daily/*_pnl.csv`, `positions/*_positions.parquet`,
  `performance/*.csv` and `root/*.csv`.
- Added `--stage full --confirm-read-once` to
  `scripts/run_c_daily_audit.py`: full 1986–2026 marks, zero costs, USD 10m,
  `output/c_daily_audit/full/`, `manifest_full.json`, and the shared
  `test_readonce.json` marker. The full stage recomputes the validation
  selection/gate and verifies it against the frozen stage-1 gate; a second
  full read is refused unless `--force-test-read` is passed.
- Added notebook 12 section 12: gross NAV, `F.positions` with `ROOT_ORDER`
  (positions, exposure and turnover), and a full/train/validation/test
  summary (gross SR, turnover, active roots). The 2016–2026 slice is labeled
  descriptive; §10/§11 now explain that the marker may come from the
  descriptive full read and that this does not mean the gate passed.
- Added D-029 to `docs/decisions.md`; updated README, HANDOFF and PROGRESS.
- Copied the existing D-027 stage-1 artifacts from the `c-daily-audit`
  worktree into the main checkout's gitignored `output/c_daily_audit/` so
  notebook 12 §9–11 stays reproducible. Stage 1 was not rerun or overwritten.

**Files changed:**
- `src/c_daily.py`, `scripts/run_c_daily_audit.py`
- `tests/test_c_daily.py`
- `notebooks/12_idea_c_mean_reversion.ipynb`
- `docs/decisions.md`, `docs/HANDOFF.md`, `docs/PROGRESS.md`, `README.md`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `python -m pytest -q` → 175 passed
- `python scripts/run_c_daily_audit.py --stage full --confirm-read-once`
- `python scripts/run_c_daily_audit.py --stage full --confirm-read-once`
  again → refused because the marker exists
- `jupyter nbconvert --execute --to notebook --inplace
  notebooks/12_idea_c_mean_reversion.ipynb`
- `python scripts/clean_notebook_metadata.py
  notebooks/12_idea_c_mean_reversion.ipynb`

**Why:** D-027 built the daily C signal and gross P&L but left only summary
tables, so the notebook could not show daily NAV or positions and the signal,
legs, P&L and holdings were not auditable. D-029 fixes that presentation gap
while keeping C closed and the weekly official results untouched.

**Validation:**
- Full stage wrote all expected artifacts under
  `output/c_daily_audit/full/`: 3 signals, 3 legs, 3 daily P&L files, 3
  position files, 3 performance tables, 3 root tables, plus selection/gate.
  Signal row counts are 252,168 each; daily P&L covers 1986-01-02 to
  2026-10-13.
- The recomputed gate exactly matches D-027 stage 1
  (`stage1_gate_consistent: true`): C1 selected; validation gross SR 0.2398
  (<0.4); 15/24 roots positive; gate failed.
- Descriptive test gross SR: C1 −0.196, C2 +0.060, C3 +0.465. C3's test
  result is positive but its validation SR is −0.332, so the frozen
  selection remains C1; no reselection or tuning was done.
- The marker records `reason="descriptive full-sample presentation"`, the
  selected variant, gate result, commit and UTC timestamp; a second read was
  refused.
- Weekly D-019 regression: `output/v2_rerun/c_performance.csv` matched the
  pre-change checksum after notebook 12 re-ran the weekly strategies.
- Notebook 12 executed top-to-bottom and its volatile metadata was cleaned.

**Commit:** `feat(c-daily): persist daily signal artifacts and add descriptive full-sample view (D-029)` (`this commit`).

**Next:** C stays closed. The daily artifacts are available for inspection;
any new C hypothesis is a separate pre-registered project. The next research
step remains H (holding-period scan), and the 2016–2026 test slice must not be
used for tuning.

---

## LOG-0061 · 2026-10-20 · Phase 14 · Claude Code

**Task:** Alpha combination across ideas A–E (D-030): continuous factors,
per-root day-block bootstrap IC screen with a block-length experiment, model
zoo with paired bootstrap selection, time-series and cross-sectional
monetisation with layered costs, read-once test.

**What changed:**
- New `src/alpha_factors.py` (12 factors, targets, causal scaling),
  `src/alpha_screen.py` (joint date-block bootstrap, block sensitivity,
  screen, yearly IC), `src/alpha_models.py` (pooled zoo, OOS predictions,
  paired comparison), `src/alpha_portfolio.py` (sign/linear/band/xs rules,
  round-trip cost, root characteristics/contribution),
  `src/alpha_figures.py`.
- `scripts/run_alpha.py` with `--stage select` (marks truncated at
  2015-12-31) and `--stage test --confirm-read-once`
  (`output/alpha/test_readonce.json`).
- `notebooks/15_alpha_combination.ipynb` (Chinese narrative, 19 figures).
- `tests/test_alpha.py` (9 synthetic tests).
- D-030 in `docs/decisions.md`; README / HANDOFF pointers.

**Commands:**
- `python scripts/run_alpha.py --stage select` (~9 min)
- `python scripts/run_alpha.py --stage test --confirm-read-once` (~1 min)
- `python -m nbconvert --execute --to notebook --inplace notebooks/15_alpha_combination.ipynb`
- `python -m pytest -q`

**Why:** every idea alone is weak; the user asked whether combining them as
alpha factors yields a usable spread forecast and strategy.

**Validation / results:** block 10; A and C pass at all horizons, B at
long horizons, D never; validation IC 0.036–0.124 rising with horizon;
linear models ≥ trees; headline `[t+1,t+6]` linear validation net Sharpe
1.34; test gross −0.21 / net −0.61 although test IC stays positive (0.028
at 5 days, 0.141 at 21 days); LB alone −42 bp/yr gross in test.

**Commit:** `feat(alpha): combine A–E into alpha factors, screen, model zoo and monetisation (D-030)` (`08119e3`).

**Next:** liquidity- or risk-budgeted sizing and longer horizons as a new
pre-registered decision; evaluate with walk-forward since the test slice has
been read.

---

## LOG-0062 · 2026-10-20 · Phase 14 · Claude Code

**Task:** D-031 follow-ups to the alpha combination: IC term structure to
252 days, look-ahead check, pairwise model-difference grid, ex-LB reruns,
per-commodity cumulative P&L, low-frequency execution experiments.

**What changed:**
- `src/alpha_factors.rolled_forward`; `src/alpha_portfolio.hold_between_rebalances`
  and `run_rule(every=...)`; new figures in `src/alpha_figures.py`
  (`ic_term_structure`, `lookahead_check`, `pairwise_diff_grid`,
  `root_cumulative`, `lowfreq_grid`, `nav_configs`; rolling-IC labels).
- `scripts/run_alpha.py` stages `horizons`, `exlb`, `lowfreq`,
  `lowfreq_desc`.
- Notebook 15: §4 term structure and pairwise grid, §5 look-ahead check,
  §7 model-per-period note, §7b per-commodity / ex-LB, §7c low frequency,
  updated conclusions.
- `tests/test_alpha.py` (+2 tests), D-031, README/HANDOFF pointers.

**Commands:**
- `python scripts/run_alpha.py --stage horizons --n-boot 500`
- `python scripts/run_alpha.py --stage exlb`
- `python scripts/run_alpha.py --stage lowfreq`
- `python scripts/run_alpha.py --stage lowfreq_desc`
- `python -m nbconvert --execute --to notebook --inplace notebooks/15_alpha_combination.ipynb`
- `python -m pytest -q`

**Why:** user questions on the D-030 results (plateau, look-ahead, model
windows, lumber, per-commodity P&L, lower-frequency trading).

**Validation / results:** IC peaks ~42 days, annualised IC decays from day
1; look-ahead check passes; validation low-frequency choice (every 10 days)
net Sharpe 1.38 but negative in test; post-hoc `[t+1,t+22]` every-22-day
configuration +0.57%/yr net in test (Sharpe 0.45). All post-test runs are
labelled descriptive.

**Commit:** `feat(alpha): horizon term structure, low-frequency execution and post-test diagnostics (D-031)` (`f34c519`).

**Next:** pre-register a walk-forward study of long-horizon forecasts with
monthly rebalancing, rolled-return targets and liquidity/risk budgets.

---

## LOG-0063 · 2026-10-20 11:45 · Phase 15 · Claude Code

**Goal:** Build a simple, compilable LaTeX framework for the 20-minute final
presentation: setup and data first, then ideas A–D with robustness, a blank
section for E, and a placeholder for the portfolio combination.

**Actions:**
- Created `presentations/final/main.tex` from the mid-term deck's preamble and
  palette (metropolis, 16:9, navy/accent), with a title page for
  "Systematic Trading / Project 7 / Jiaheng Han & Tian Tian".
- Added a dedicated data section before the ideas: Bloomberg source, 1986–2026
  sample, 24 commodities by sector, M1–M4 slots vs real contracts, eligibility,
  and the common v2 engine.
- Added a roadmap table (A–E, reference, verdict) and one A/B/C/D idea slide
  plus one result/robustness slide per idea; C and D each get a paper slide and
  a replication-choice slide before the result.
- Rewrote A/B around the user's decision: the original assignment directions
  get one line each (negative), then A-flip / B-flip become the main design.
  Added related references (Koijen et al. 2018 for commodity carry; Masturzo &
  Leung 2025 for intra-commodity calendar-spread pairs) and the flip results.
- Used the official v2 numbers (D-019) in the original A/B/C/D result tables;
  labeled A flip and B flip as candidate/post-hoc gross-only signals; labeled
  the daily C audit as descriptive.
- Left E (slide 17) blank with a checklist for the teammate. Added a portfolio
  slide with a placeholder for the combined NAV/Sharpe/correlation figure.
- Added backup slides (data QA, cost model/definitions, references) and a
  `README.md` with build instructions, timing, and open questions.
- Copied `refs.bib` from the mid-term deck.

**Files changed:**
- `presentations/final/main.tex`
- `presentations/final/refs.bib`
- `presentations/final/README.md`
- `README.md` (repo map)
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `tectonic -X compile --outdir build main.tex` → 23 pages, PDF written to
  `presentations/final/build/main.pdf`
- Rendered pages with `pdftoppm` and checked title, data, roadmap, A–D,
  portfolio and appendix slides visually.

**Why:** The user asked for a framework first, not a finished deck. The deck
needs to establish the calendar-spread setting and the data before walking
through A–D, leave E to the teammate, and reserve the final section for the
portfolio combination. User decisions: English slides; the original A/B get one
line each and the flips are the main design; the portfolio section stays a
placeholder; the 20 minutes are talk time and Q&A is separate.

**Validation:**
- The deck compiles with Tectonic 0.17.0 (XeTeX) and BibTeX; no overfull hbox
  remains. The title page still reports a harmless 13.8pt overfull vbox from
  the metropolis title template; the rendered page is not clipped.
- All result numbers match `output/v2_rerun/comparison.csv`:
  A −0.48/−2.61, B −1.13/−4.47, C 1:1 +0.61/−3.70, C OLS +0.12/−3.06,
  C Kalman +0.61/−6.10, D +0.22/−1.42.
- A-flip numbers match D-025 (full +0.63%, Sharpe 0.63, NW t 4.29; test
  +0.46%, t 1.58). B-flip numbers match D-026 (full +0.50%, Sharpe 1.06,
  NW t 7.14; half-spread 84 bps vs 50 bps gross; all-in about −2.0%).
- The E and portfolio sections are visibly marked as placeholders, so the draft
  cannot be mistaken for a completed result.

**Commit:** `feat(presentation): add final deck framework with data setup and A/B flips` (`this commit`).

**Next:** Merge `origin/main` (D-030/D-031 alpha combination) into local main;
then fill figures, E and the portfolio section after the user's review.

---

## LOG-0064 · 2026-10-20 · Phase 15 · Claude Code

**Goal:** Merge `origin/main` (D-030/D-031 alpha combination) into the local
presentation branch, keep both sides' results, and make the merged tree
testable.

**Actions:**
- Merged `origin/main` (5 commits, including `08119e3` D-030 and `f34c519`
  D-031) into local `main` after the presentation commit.
- Resolved the `AGENT_LOG.md` and `INDEX.md` conflicts by keeping the remote
  entries as LOG-0061/0062 and appending the presentation entry as LOG-0063;
  the merge itself is LOG-0064.
- Kept both README changes: the D-030 alpha-combination note from the remote
  and the `presentations/final/` repo-map entry from the local branch.
- Added the missing alpha-model dependencies (`scikit-learn==1.9.1`,
  `xgboost==3.2.0`) to `requirements.txt`; the remote alpha code imported
  them but did not declare them.

**Files changed:**
- Merge brings in `src/alpha_*.py`, `scripts/run_alpha.py`,
  `notebooks/15_alpha_combination.ipynb`, `tests/test_alpha.py`,
  `docs/decisions.md` (D-030/D-031), `docs/HANDOFF.md`, `README.md` and
  `scripts/run_all.sh`.
- `requirements.txt`
- `docs/logs/AGENT_LOG.md`, `docs/logs/INDEX.md`

**Commands:**
- `git merge --no-ff origin/main`
- `~/miniconda3/envs/mfe/bin/python -m pytest -q` → 186 passed
- `tectonic -X compile --outdir build main.tex` → 23 pages

**Why:** The cloud main had the D-030 alpha-combination and D-031 follow-up
work; the local branch had the final presentation framework. The user asked to
merge both and push to origin main.

**Validation:**
- 186 tests pass after installing scikit-learn 1.9.1 and xgboost 3.2.0.
- The deck still compiles to 23 pages.
- Log IDs are ordered 0061 (D-030), 0062 (D-031), 0063 (presentation), 0064
  (merge); no collision.
- The merge keeps the official v2 results and the new alpha-combination
  results separate; the presentation's A/B flip numbers are unchanged.

**Commit:** `merge: integrate origin/main alpha combination into final-presentation branch` (`this commit`).

**Next:** Push to `origin main`; then fill the E and portfolio slides and the
result figures.

---

## LOG-0065 · 2026-10-20 · Phase 15 · Claude Code

**Task:** Final deck edits (user request): academic punctuation, numbered
captions, data-table slide, white closing slide, and the first three idea-E
slides with journal-style vector figures.

**What changed:**
- `presentations/final/main.tex`: no visible semicolons, em dashes or vertical
  bars in any slide (Tian's and Jiaheng's parts); every table and figure in a
  numbered `table`/`figure` with a caption below; slide 3 lists all 24 codes
  with underlying, exchange and sample; Figure 1 redrawn; closing slide is
  white with "Questions and comments are welcomed."; E slides 1–3 (method with
  numbered Eq. (1), fit-significance test with Eq. (2) and Figure 4,
  replication/transfer table).
- `scripts/make_slide_figures.py` (vector PDFs in `presentations/final/figures/`)
  and `scripts/make_slide_tables.py` (bare tabulars in
  `presentations/final/tables/`, raw CSV in `output/slides/`).
- `src/nelson_siegel.fit_quality` / `_loo_press`: optional `holdout` (e.g.
  interior contracts only); default behaviour unchanged; new test.

**Why:** the user is preparing the final presentation; the interior
leave-one-contract-out R² separates interpolation (what a curve model is for)
from end-point extrapolation, which drove the earlier "curvature hurts"
reading.

**Validation / results:** deck compiles with XeLaTeX; rendered text has no
`;`, `—` or `|`. Interior LOO: adding β_S helps 24/24 commodities, adding β_C
23/24 (none worse); all-contract LOO: β_C helps 10, hurts 10. Replication grid
(paper universe, 1992–2019, $1m): paper timing gross +3.11%/yr (Sharpe 1.95),
tradable t+1 gross −0.18% (−0.11); k = 5/20 do not turn it positive.
`python -m pytest -q` passes.

**Commit:** `feat(slides): final-deck formatting and idea-E slides with vector figures` (`cb0822e`).

**Next:** E evaluation-figure slide and per-commodity discussion slide;
notebook 14 should add the interior-LOO result.

---

## LOG-0066 · 2026-10-20 · Phase 15 · Claude Code

**Task:** Final deck, continued: trading-environment slide and idea-E slides
4–5 (evaluation figures, per-commodity discussion), highlights, TC1–TC3 note.

**What changed:**
- `presentations/final/main.tex`: new slide "The simulated trading
  environment" after the engine slide (fill at the t+1 settle with TAS
  availability by exchange and year, cost table with calibration sources,
  portfolio size $100k–$30m, default $1m equal 1/N); E slide 4 (horizon
  decay and cumulative return at both timings); E slide 5 (per-commodity
  Sharpe vs interior LOO R², λ dependence); paper λ explained; TC1–TC3 in the
  Table 14 caption; key phrases highlighted; "E · Results" placeholder removed.
- `presentations/final/refs.bib`: Szakmary et al. (2010), Wang, Garcia and
  Irwin (2014), Gao et al. (2018), Tóth et al. (2011), Bouchaud et al. (2018).
- `scripts/make_slide_figures.py`: `e_horizon_decay`, `e_nav_timing`,
  `e_root_data`, `e_root_discussion`.

**Why:** user request while preparing the final presentation.

**Validation / results:** deck compiles. TAS (CME/ICE notices): energy 2006,
ICE softs 2008–09, metals ~2010–11, grains and livestock June 2015; none found
for oats, rough rice, lumber. Paper-timing gross Sharpe by λ rule
(1992–2019): paper 1.88, fixed 4 0.64, rolling SSR −0.25. Rank correlation of
per-commodity paper-timing Sharpe with interior LOO R²: −0.16; livestock fits
worst but is strongest. `python -m pytest -q` passes.

**Commit:** `feat(slides): trading-environment slide and idea-E evaluation and discussion slides` (`540b009`).

**Next:** fill the E rows in the roadmap and conclusion tables; portfolio
slide; notebook 14 should record the interior-LOO and λ-dependence findings.

---

## LOG-0067 · 2026-10-20 · Phase 15 · Claude Code

**Task:** Final deck: starred idea-E slide on the Kalman dynamic Nelson–Siegel
attempt.

**What changed:** `presentations/final/main.tex` adds "E* · Can a Kalman filter
stabilize the betas?" after the per-commodity slide: motivation (four prices,
three betas and λ), state and observation equations (3)–(4), how (r, q) were
chosen (one-step likelihood on 1986–2005) and the A/B design (2006–2026,
paired 21-day block bootstrap), Table 15 with the D-023 numbers, and the
reason it is not adopted (the signal lives one day, so shrinking toward
yesterday's betas removes it).

**Why:** user request.

**Validation / results:** numbers copied from notebook 14 §11 (D-023): LOO R²
0.72 → 0.95 (24/24 better), one-step forecast R² 0.53 → 0.45 (20/24 worse),
[t+1, t+2] −0.04 → −0.57 bp, tradable gross +0.18 → −0.31 %/yr. Deck compiles,
no `;`, `—` or `|` in rendered text.

**Commit:** `feat(slides): starred idea-E slide on the Kalman dynamic NS` (`3e611fb`).

**Next:** E rows in the roadmap and conclusion tables, portfolio slide.

---

## LOG-0068 · 2026-10-20 · Phase 15 · Claude Code

**Task:** Final deck, combination section (Jiaheng's second part): from
strategies to alphas, block-bootstrap screen, model comparison, ridge
rebalancing schemes, lumber diagnosis. D-032.

**What changed:**
- `presentations/final/main.tex`: replaces the portfolio placeholder with
  seven slides (alpha definitions as formulas, metric and bootstrap pseudocode
  with the block-length figure, screen heatmap, model comparison, ridge table,
  cumulative-return figures, lumber before/after).
- `scripts/make_slide_figures.py` (`f_block_length`, `f_screen_heatmap`,
  `f_model_ic`, `f_ridge_nav`, `f_ridge_layers`, `f_lumber`) and
  `scripts/make_slide_tables.py --ridge`.
- `scripts/run_alpha.py` stages `ridge`, `lbfix`, `model_notes`;
  `src/alpha_portfolio.run_rule(scheme=...)` (default unchanged).
- D-032 in `docs/decisions.md`.

**Why:** user request for the final presentation.

**Validation / results:** see D-032. Deck compiles, no `;`, `—` or `|` in
rendered text. `python -m pytest -q` passes.

**Commit:** `feat(slides): alpha-combination section with ridge schemes and lumber diagnosis (D-032)` (`dbf8958`).

**Next:** E and combination rows in the roadmap and conclusion tables.

---

## LOG-0069 · 2026-10-20 · Phase 15 · Claude Code

**Task:** Fill the E and combination results in the roadmap and conclusion
slides. Kept on branch `jiaheng/final-deck` (not main) at the user's request,
because Tian may be editing the deck; the two versions are merged later.

**What changed:** `presentations/final/main.tex`: roadmap verdict for E is
"replicated, not tradable"; conclusion table E row uses the D-022 official
full-sample tradable result (gross −0.07%/yr, all-in −9.77%/yr, Sharpe
−3.36) and a new row for the combined alphas (ridge, every 22 days: gross
+0.57%, all-in +0.23%, Sharpe 0.23); the outdated "Next" bullet is replaced
by the combination finding, and E's verdict is added to the C/D bullet.

**Why:** user request.

**Validation / results:** deck compiles, no overflow on the edited slides.

**Commit:** `feat(slides): E and combination results in roadmap and conclusion` (`faeff26`).

**Next:** merge with Tian's slide edits; then merge the branch into main.

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







## LOG-0013 · 2026-10-19 · Phase 6 · Claude Code

**Goal:** Record the C/E ownership split and let the engine rebalance daily,
which C (Lubnau & Todorova) and E (Bianchi et al.) need.

**Actions:**
- Added D-010 (Tian: A, D; Jiaheng: C, E; Nelson–Siegel back in scope) and
  D-011 (daily rebalance option) to `docs/decisions.md`.
- Added `REBALANCE_RULES` and `_rebalance_dates` to `src/backtest.py`;
  `BacktestConfig(rebalance="daily")` now rebalances on every trading day.
  The default stays weekly.
- Updated the config guard test and added two daily-rebalance tests.
- Updated the config section of `docs/backtest_framework.md`.

**Files changed:**
- `src/backtest.py` — rebalance dispatcher, config guard
- `tests/test_backtest.py` — `rebalance` arg in `_run`, two new tests
- `docs/decisions.md` — D-010, D-011
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

**Commit:** `feat(backtest): add daily rebalance option` (pending)

**Next:** plan and implement the C and E signal modules on the shared engine.

## LOG-0014 · 2026-10-19 · Phase 7 · Claude Code

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
  `scripts/run_all.sh`; D-012 in `docs/decisions.md`.
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

**Commit:** `feat(backtest): add holdings-based v2 framework with layered costs` (pending)

**Next:** implement C/D/E signal functions on v2; calibrate `min_adv` and
impact volatility (leg vs spread) as robustness.

## LOG-0015 · 2026-10-19 · Phase 7b · Claude Code

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
  liquidity sizing; D-012 and `docs/transaction_costs.md` updated.

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

**Commit:** pending (with LOG-0014)

**Next:** C/D/E signal functions on v2.

## LOG-0016 · 2026-10-19 · Phase 7c · Claude Code

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

**Commit:** `feat(figures): add publication figure style and figure module`

**Next:** C/D/E signal functions on v2.

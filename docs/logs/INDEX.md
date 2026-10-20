# Agent Log Index

| ID | Date | Phase | Actor | Summary | Files | Commit |
|---|---|---|---|---|---|---|
| LOG-0001 | 2026-10-17 | Phase 0 | Claude Code | Read-only raw-data audit and panel design findings | none | pre-repo |
| LOG-0002 | 2026-10-17 | Phase R | Claude Code | Repo scaffold, docs, metadata, log protocol | README, AGENTS.md, CLAUDE.md, docs/*, data/metadata/* | `f8d1472` + `a821af6` |
| LOG-0003 | 2026-10-17 | Phase 1 | Claude Code | Raw loader, contract parser, rank panel, tests | src/config.py, src/load.py, tests/* | `95f2ac5` |
| LOG-0004 | 2026-10-17 | Phase 2 | Claude Code | Contract/return panels, roll-aware QA, spread tests | src/curve.py, src/panel.py, src/qa.py, tests/test_spread.py | `3e5d3f0` |
| LOG-0005 | 2026-10-17 | Phase 3 | Claude Code | Liquidity universe, pair episodes, adjacency guard | src/panel.py, src/curve.py, src/qa.py, tests/test_spread.py | `7b90d5c` |
| LOG-0006 | 2026-10-17 | Phase 3b | Claude Code | Adjacent-pair robustness panel | src/panel.py, tests/test_spread.py, docs/data_dictionary.md | `6c6a055` |
| LOG-0007 | 2026-10-17 | Phase 4 | Claude Code | Data audit and panel-build notebooks, viz, status | src/viz.py, notebooks/*, README.md, AGENTS.md, docs/onboarding.md | `73fff88` |
| LOG-0008 | 2026-10-17 | Phase 4b | Claude Code | Handoff snapshot, research notes, run script, bilingual notebooks | docs/HANDOFF.md, docs/research_notes.md, data/processed/README.md, scripts/run_all.sh, notebooks/* | `664506c` |
| LOG-0009 | 2026-10-17 | Phase 4c | Claude Code | Strip volatile notebook execution timestamps | scripts/clean_notebook_metadata.py, scripts/run_all.sh, notebooks/* | `716e7bc` |
| LOG-0010 | 2026-10-19 | Phase 5 | Claude Code | K=5 backtest panel, per-contract mark state, carry signal | src/curve.py, src/panel.py, src/signals.py, docs/PROGRESS.md, docs/decisions.md | `f2c4771` |
| LOG-0011 | 2026-10-19 | Phase 5b | Claude Code | Return-based calendar-spread engine, metrics, tests | src/backtest.py, src/metrics.py, tests/*, docs/backtest_framework.md, docs/data_dictionary.md | `1b833c9` |
| LOG-0012 | 2026-10-19 | Phase 5c | Claude Code | Idea A baseline notebook and negative result | notebooks/02_carry.ipynb, scripts/run_all.sh, README.md, AGENTS.md, docs/HANDOFF.md, docs/PROGRESS.md | `bd6691b` |
| LOG-0013 | 2026-10-19 | Phase 6a | Claude Code | Share weekly rebalance calendar across engine and signals | src/curve.py, src/backtest.py, src/metrics.py, tests/test_backtest.py | `fea95d1` |
| LOG-0014 | 2026-10-19 | Phase 6b | Claude Code | Roll-chained continuous leg price indices | src/continuous.py, tests/test_continuous.py | `5c8c25d` |
| LOG-0015 | 2026-10-19 | Phase 6c | Claude Code | Weekly mean-reversion signal and D-010 | src/signals.py, tests/test_signals.py, tests/test_backtest.py, docs/decisions.md, docs/backtest_framework.md, docs/data_dictionary.md | `8ac3487` |
| LOG-0016 | 2026-10-19 | Phase 6d | Claude Code | Idea C baseline notebook and negative result | notebooks/03_mean_reversion.ipynb, scripts/run_all.sh, docs/backtest_framework.md | `47fae2e` |
| LOG-0017 | 2026-10-19 | Phase 6e | Claude Code | Record idea C baseline in status docs | docs/PROGRESS.md, docs/HANDOFF.md, README.md, AGENTS.md, docs/onboarding.md | `3930bac` |
| LOG-0018 | 2026-10-19 | Phase 6f | Claude Code | Cover later-start weekly calendar in signal test | tests/test_signals.py | `59accfc` |
| LOG-0019 | 2026-10-19 | Phase 6b | Claude Code | A negative-result diagnosis (side/sector/era, K=5 vs K=10, costs) | src/a_diagnostics.py, tests/test_a_diagnostics.py, notebooks/04_a_diagnose.ipynb, docs/a_negative_result.md | `f02f18b` |
| LOG-0020 | 2026-10-19 | Phase 6c | Claude Code | Cheap B pre-test (adjacent carry rank) — negative | src/b_pre_test.py, tests/test_b_pre_test.py, notebooks/05_b_pretest.ipynb, docs/b_pretest.md | `d257e0e` |
| LOG-0021 | 2026-10-19 | Phase 6g | Claude Code | Merge A and B into main; close A/B as negative; reserve 03/LOG-0013–0018 for C | src/a_diagnostics.py, src/b_pre_test.py, tests/*, notebooks/04_a_diagnose.ipynb, notebooks/05_b_pretest.ipynb, docs/*, README.md, AGENTS.md, scripts/run_all.sh | `a15541e` + `7d1d626` |
| LOG-0022 | 2026-10-19 | Phase 6g | Claude Code | Rolling OLS hedge ratio on continuous leg indices | src/continuous.py, tests/test_continuous.py | `069da35` |
| LOG-0023 | 2026-10-19 | Phase 6h | Claude Code | Hedge-ratio leg weights and D-011 | src/backtest.py, tests/test_backtest.py, docs/decisions.md, docs/data_dictionary.md, docs/backtest_framework.md | `8e738d7` |
| LOG-0024 | 2026-10-19 | Phase 6i | Claude Code | Gross hedge-ratio comparison (negative) | notebooks/03_mean_reversion.ipynb | `ee3bab9` |
| LOG-0025 | 2026-10-19 | Phase 6j | Claude Code | Reconcile C branch with A/B main after rebase | AGENTS.md, README.md, docs/HANDOFF.md, docs/PROGRESS.md, scripts/run_all.sh | `f68822b` |
| LOG-0026 | 2026-10-19 | Phase 6k | Claude Code | Kalman hedge-ratio variant and C close-out | src/kalman.py, tests/test_kalman.py, docs/decisions.md, docs/*.md | `48ae998` |
| LOG-0027 | 2026-10-19 | Phase 7 | Claude Code | Merge idea C into main and reconcile A/B docs | AGENTS.md, README.md, docs/HANDOFF.md, docs/PROGRESS.md, docs/onboarding.md, docs/logs/* | `86dd750` |
| LOG-0028 | 2026-10-19 | Phase 8a | Claude Code | Monthly engine + curve-momentum / basis-momentum signal | src/curve.py, src/backtest.py, src/signals.py, tests/test_backtest.py, tests/test_curve_momentum.py | `4db6849` |
| LOG-0029 | 2026-10-19 | Phase 8b | Claude Code | Idea D baseline notebook and diagnostics | notebooks/06_curve_momentum.ipynb, scripts/run_all.sh | `cf94b1f` |
| LOG-0030 | 2026-10-19 | Phase 8c | Claude Code | Record idea D baseline and close-out docs | README.md, AGENTS.md, paper/README.md, docs/* | `8a92198` |
| LOG-0031 | 2026-10-19 | Phase 8d | Claude Code | Record idea D local merge handoff and done/not-done state | docs/HANDOFF.md, docs/PROGRESS.md, docs/logs/* | `3bb0f36` |
| LOG-0032 | 2026-10-19 | Phase 8e | Claude Code | Merge idea D curve-momentum baseline into main | merge of feat/idea-d-curve-momentum; src/*, tests/*, notebooks/06_curve_momentum.ipynb, docs/* | `08de3e7` |
| LOG-0033 | 2026-10-19 | Phase 6 | Claude Code | C/E ownership (D-014), daily rebalance option (D-015) | src/backtest.py, tests/test_backtest.py, docs/decisions.md, docs/backtest_framework.md | `0b3d947` |
| LOG-0034 | 2026-10-19 | Phase 7 | Claude Code | Backtest v2: holdings simulator, layered costs, horizon diagnostics, capacity | src/{specs,marks,sizing,costs,simulate,horizon,report}.py, tests/test_simulate.py, notebooks/03_backtest_framework.ipynb, docs/transaction_costs.md, docs/decisions.md | `0b3d947` |
| LOG-0035 | 2026-10-19 | Phase 7b | Claude Code | Time-series-only diagnostics; liquidity-weighted sizing | src/horizon.py, src/sizing.py, src/report.py, notebooks/03_backtest_framework.ipynb, docs/decisions.md | `0b3d947` |
| LOG-0036 | 2026-10-19 | Phase 7c | Claude Code | Journal-grade figures: plotstyle + figures modules, stable rolling IC | src/plotstyle.py, src/figures.py, src/report.py, src/horizon.py, notebooks/03_backtest_framework.ipynb | `0b3d947` |
| LOG-0037 | 2026-10-19 | Phase 7d | Claude Code | Merge main into backtest-v2; renumber D-014–016, LOG-0033–0036; notebook 07 | src/backtest.py, scripts/run_all.sh, docs/*, notebooks/07_backtest_framework.ipynb | merge |
| LOG-0038 | 2026-10-19 | Phase 7e | Claude Code | Horizon decay, dense k profile, per-commodity block-bootstrap IC | src/horizon.py, src/report.py, src/figures.py, src/plotstyle.py, tests/test_simulate.py, notebooks/07_backtest_framework.ipynb | `95db2ee` |
| LOG-0039 | 2026-10-19 | Phase 8f | Claude Code | Merge jiaheng/backtest-v2 into main; resolve rebalance, decision, log and notebook numbering | src/backtest.py, scripts/run_all.sh, docs/*, docs/logs/*, notebooks/07_backtest_framework.ipynb | `8baeda1` |
| LOG-0040 | 2026-10-19 | Phase 8g | Claude Code | Keep math escapes in mathtext fallback; run notebook 07 without LaTeX | src/plotstyle.py, tests/test_plotstyle.py, docs/logs/* | this commit |
| LOG-0041 | 2026-10-19 | Phase 9a | Claude Code | Pre-register v2 extensions (D-017) and rerun conventions (D-018) | docs/decisions.md, docs/logs/* | `9108cd3` |
| LOG-0042 | 2026-10-19 | Phase 9b | Claude Code | Full-calendar annualization, resize keys, hedge-ratio and multi-leg legs | src/simulate.py, src/sizing.py, src/report.py, tests/test_simulate.py, tests/test_sizing.py | `116ec12` |
| LOG-0043 | 2026-10-19 | Phase 9c | Claude Code | v2 adapters for A/D/C/C-OLS/C-Kalman/B | src/v2_signals.py, tests/test_v2_signals.py | `9116883` |
| LOG-0044 | 2026-10-19 | Phase 9d | Claude Code | v2 re-runs A/D/C/C-hedge/B; notebook 08; refreshed 07 | src/v2_rerun.py, scripts/run_v2_rerun.py, scripts/run_all.sh, notebooks/07, notebooks/08 | `3d5019b` |
| LOG-0045 | 2026-10-19 | Phase 9e | Claude Code | v1/v2 comparison doc and status close-out | docs/v1_v2_comparison.md, docs/backtest_framework.md, docs/data_dictionary.md, docs/HANDOFF.md, docs/PROGRESS.md, README.md, AGENTS.md | this commit |
| LOG-0046 | 2026-10-19 | Phase 9f | Claude Code | Failure-diagnostics plan for A/B/D on v2 reruns | docs/diagnostics_plan.md, docs/HANDOFF.md, docs/logs/* | this commit |
| LOG-0047 | 2026-10-19 | Phase 9g | Claude Code | Make v2 results official (D-019); keep v1 as historical | docs/decisions.md, README.md, AGENTS.md, docs/HANDOFF.md, docs/PROGRESS.md, docs/onboarding.md, docs/backtest_framework.md, docs/v1_v2_comparison.md | this commit |
| LOG-0048 | 2026-10-19 | Phase 10a | Claude Code | v2 valued positions, overall Sharpe, position-book figure | src/simulate.py, src/report.py, src/figures.py, src/v2_rerun.py, src/plotstyle.py, tests/* | this commit |
| LOG-0049 | 2026-10-19 | Phase 10b | Claude Code | One notebook per idea: A/B/C/D with PnL, positions, Sharpe | notebooks/10_idea_a_carry.ipynb, notebooks/11_idea_b_adjacent_carry.ipynb, notebooks/12_idea_c_mean_reversion.ipynb, notebooks/13_idea_d_curve_momentum.ipynb, scripts/run_all.sh, scripts/run_v2_rerun.py | this commit |
| LOG-0050 | 2026-10-19 | Phase 10c | Claude Code | Retire notebooks 02–08; document D-020 layout and recovery | notebooks/02–08 (deleted), docs/notebook_history.md, README.md, AGENTS.md, docs/*, docs/decisions.md | this commit |

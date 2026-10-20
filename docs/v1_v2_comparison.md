# v1 vs v2 backtest frameworks

This note records how the original event-loop engine (`v1`) and the
holdings-based simulator merged from `jiaheng/backtest-v2` (`v2`) differ, and
what the v2 re-runs of A, D, C, C-hedge and B show. It is a comparison of two
frameworks, not a claim that one number is the "same strategy computed twice".

**Status (D-019): v2 is the official/final result.** v1 is retained as a
historical baseline and must be labeled `v1`; do not use v1 numbers in
headline tables.

## 1. Architecture

| Dimension | v1 (`src/backtest.py`) | v2 (`src/simulate.py`) |
|---|---|---|
| Core | Daily event loop with pending orders | Per-root holdings simulator |
| Timing | Signal at t close, fill at t+1 close; mark old position before fill | Signal at t settle, fill at t+1 settle; first P&L t+1→t+2 |
| Position | 1:1 contract units (optional hedge ratio) | Fractional contracts; gross budget × capital |
| Capital | None; returns on gross notional | `SimConfig.capital`; P&L / capital, non-compounding |
| Return | P&L / previous gross notional; portfolio equal-weight mean | USD P&L / capital; group budget 1/N |
| Annualisation | Geometric (`cumprod`) | Arithmetic mean × 252; zero-filled calendar |
| Pair rule | Nearest two eligible adjacent contracts; A/D use `d=None`, K=5 | Same `select_pairs`, `d=5`, K=5, plus `min_adv=100` |
| Sizing | Equal weight active roots; fixed units between rebalances | Equal 1/N_max5, inverse vol, or dollar-ADV^alpha; budget-scaled |
| Cost | Flat 5 bps per traded leg | Half-spread + USD 1.5/contract fee + square-root impact |
| Rebalance | Weekly or monthly calendar + pair-change rolls | `on_change` (target/group/resize_key) or daily |
| Roll | Pending order is pair-bound; cancel if pair changed before fill | New group_id/resize_key trades old out and new in |
| Missing/stale | Last valid mark; blocked entries dropped; force-flat after 5 invalid (delayed to rebalance) | `tradable` flag; blocked fills retry; force-flat every fill |
| No signal | Missing target row → empty/flat order on a rebalance | Missing row = keep holdings; explicit flat = exit |
| Multi-leg / hedge | `build_target_legs` can emit arbitrary legs | `legs_from_signal` (two-leg) + optional hedge ratio; `legs_from_rows` for explicit multi-leg |
| Diagnostics | Summary, sector, weekly conditional mean, plot | Layered performance, per-root costs, k sweep, capacity, horizon, IC, bootstrap |
| Negative prices | Supported | Positive-price-only; CL 2020-04-20 excluded |
| Test period | Separate flat-start backtest from 2016 | Post-hoc slice of the full simulation |

## 2. Results (v2 official; v1 historical)

**Read this table as two different accounting systems.** v1 net is a flat
5 bps/leg; v2 shows gross → half-spread → fees → impact. v1 uses
`d=None` and 1:1 contracts; v2 uses `d=5`, `min_adv=100` and equal-notional
legs. The v2 columns are the primary result of this phase (D-018).

### 2.1 Full sample, annualised %

| Strategy | v1 gross | v1 net | v2 gross | v2 half-spread | v2 fees | v2 all-in | v2 turnover |
|---|---:|---:|---:|---:|---:|---:|---:|
| A carry | −0.53 | −1.90 | −0.48 | −0.84 | −1.00 | −2.61 | 26.1× |
| D curve momentum | +0.55 | −0.99 | +0.22 | −0.07 | −0.20 | −1.42 | 22.1× |
| C mean reversion 1:1 | +0.53 | −1.67 | +0.61 | +0.03 | −0.23 | −3.70 | 43.2× |
| C rolling-OLS hedge | +0.20 | n/a (0 bps) | +0.12 | −0.45 | −0.69 | −3.06 | 42.7× |
| C Kalman hedge | +0.98 | n/a (0 bps) | +0.61 | −0.18 | −0.50 | −6.10 | 54.7× |
| B adjacent carry | −1.14 | −2.84 | −1.13 | −2.18 | −2.37 | −4.47 | 31.0× |

### 2.2 Train / test gross, annualised %

| Strategy | v1 train | v1 test | v2 train | v2 test |
|---|---:|---:|---:|---:|
| A carry | −0.44 | −0.76 | −0.56 | −0.27 |
| D curve momentum | +0.85 | −0.28 | +0.37 | −0.21 |
| C mean reversion 1:1 | +0.87 | −0.39 | +0.78 | +0.16 |
| C rolling-OLS hedge | +0.29 | −0.06 | +0.17 | −0.01 |
| C Kalman hedge | +1.17 | +0.52 | +0.48 | +0.98 |
| B adjacent carry | −1.10 | −1.25 | −1.10 | −1.23 |

v1 train/test are from separate flat-start runs; v2 train/test are post-hoc
slices of the full simulation. Do not compare them as if they had the same
starting positions.

## 3. Adapter mapping

| Strategy | v1 source | v2 path |
|---|---|---|
| A | `signals.carry_signal(pairs)` → `build_target_legs` | `a_legs` → `legs_from_signal` |
| D | `panel.build_return_panel` + `signals.curve_momentum_signal` → monthly `run_backtest` | `d_legs` → `legs_from_signal`; on_change, large band |
| C 1:1 | `continuous.build_continuous_leg_prices` + `build_spread_index` + `mean_reversion_signal` | `c_legs("1:1")` → `legs_from_signal` |
| C OLS | `continuous.rolling_ols_hedge_ratio` + `mean_reversion_signal` | `c_legs("ols")`, far units = `-sign(target)*h`, weekly h snap |
| C Kalman | `kalman.kalman_hedge_ratio` + `mean_reversion_signal` | `c_legs("kalman")`, same |
| B | `b_pre_test.build_b_targets` → weekly v1 engine | `b_legs` → `legs_from_rows`, weekly + main-pair change dates, `execution="legs"` |

Adapters live in `src/v2_signals.py`; orchestration is in `src/v2_rerun.py`
and `scripts/run_v2_rerun.py`.

## 4. v2 fixes made in this phase

1. **Flat-day annualisation.** `_daily` now reindexes to the full marks
   calendar and zero-fills flat days. Before the fix, `performance_table`
   annualised over active observations only and overstated return, vol,
   Sharpe and cost ratios.
2. **Resize key.** `on_change` previously keyed on `(group_id, target)` and
   ignored units, contracts and hedge ratio. The key is now
   `(group_id, target, resize_key)`; `resize_key` is optional and defaults to
   `""`. This makes weekly h changes and B composition changes trigger a
   resize without daily notional churn.
3. **Explicit flats.** `legs_from_signal` and `legs_from_rows` emit explicit
   flat rows for target-zero/no-pair/non-positive-price dates; the simulator
   treats a missing row as "keep holdings".
4. **Multi-leg rows.** `legs_from_rows` nets shared contracts, requires one
   non-flat group per `(date, root)`, and derives a composition `resize_key`.

## 5. Remaining caveats

- **`d=5` is not point-in-time.** `curve.add_contract_calendar` uses
  `last_trade_proxy` (the contract's last observed date), so D-016's
  "exchange calendar, hence ex ante" claim is too strong. Report v2 results
  with this caveat.
- **Post-hoc train/test slices.** v2 does not restart flat in 2016.
- **Negative prices.** v2 refuses non-positive settles; CL 2020-04-20 is
  excluded, which can change worst-day and tail statistics.
- **B universe.** B keeps the v1 raw-rank adjacent universe, not the v2
  `d=5` universe; it is a within-root cross-sectional exception (D-017), not
  a cross-commodity ranking.
- **B costs.** `execution="legs"` is conservative because the listed-spread
  pairing in `costs._spread_execution_factor` groups by `(date, root)`, not
  by group.
- **Liquidity threshold.** `min_adv=100` is now pre-registered in D-018; it
  appears in the v2 notebook and in the driver, not in D-016.
- **v1 known issues** (unchanged): forced-exit delay, `conditional_mean`
  misnamed as a block bootstrap, and the C invalid-h doc/code mismatch.

## 6. Reproduction

```bash
python -m pytest -q
python scripts/run_v2_rerun.py --strategies a,d,c,c_ols,c_kalman,b --force
jupyter nbconvert --execute --to notebook --inplace \
  --ExecutePreprocessor.timeout=900 notebooks/10_idea_a_carry.ipynb
# 11/12/13 同理；或者直接跑 bash scripts/run_all.sh
```

`output/v2_rerun/comparison.csv` contains the tidy full/train/test × cost-layer
table; notebooks 10–13 are the narrative versions. No push is performed.

## 7. Conclusion

- v1 remains the original A benchmark and the historical source of the closed
  A/B/C/D results. It is not the final reported result.
- **v2 is the official/final result (D-019).** It is a better accounting
  framework: it separates spread, fees and impact, exposes horizon decay,
  and supports capacity analysis.
- The v2 re-runs do not rescue any idea: A/B gross is negative; D/C/C-hedge
  gross is weak and the layered costs turn every net result negative.
- The main value of v2 is diagnostic, not a new positive result.

E (Nelson–Siegel) is not part of this v1/v2 comparison;
see `notebooks/14_idea_e_nelson_siegel.ipynb` and D-021–D-023.

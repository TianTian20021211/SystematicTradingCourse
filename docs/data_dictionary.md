# Data Dictionary

This file defines the raw fields, contract-code conventions, and the derived
panels. The implementation lives in `src/load.py`, `src/curve.py`,
`src/panel.py`, and `src/qa.py`.

## 1. Raw Bloomberg bulk export

File: `data/raw/bloomberg_commodity_bulk_tickers_1986_2026.csv` (primary;
not committed). The XLSX has the same data plus `Universe_Details`.

Layout:

- 6 header rows: `Start Date`, `End Date`, blank, generic tickers, field labels,
  Bloomberg mnemonics.
- 96 generic tickers, each with 4 columns:
  `PX_SETTLE`, `PX_VOLUME`, `OPEN_INT`, `FUT_CUR_GEN_TICKER`.
- Data starts on row 7 (1-indexed); 10,640 weekday rows, 1986-01-01 to
  2026-10-13.

Raw fields:

| Field | Meaning | Units / notes |
|---|---|---|
| `PX_SETTLE` | Daily settlement price | Contract quotation units (e.g. USD/bbl, cents/bu) |
| `PX_VOLUME` | Daily volume | Contracts; blank = missing/not reported |
| `OPEN_INT` | Open interest | Contracts; blank = missing/not reported |
| `FUT_CUR_GEN_TICKER` | Actual contract code for this generic rank | e.g. `CLG86`, `C H86`, `CLX6`; `.NA.` = missing |

Missing sentinels: blank strings and `.NA.` only. No `#N/A` in the CSV.

## 2. Contract code format

Format: `<root><month-code><year>`; spaces are allowed in the raw code
(`C H86`, `S F86`, `W H86`) and are removed for parsing.

Month codes:

| Code | F | G | H | J | K | M | N | Q | U | V | X | Z |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Month | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |

Year rules for this dataset:

- 2-digit year: `86`–`99` → 1986–1999; `00`–`26` → 2000–2026.
- 1-digit year appears from 2022-09 onward (e.g. `CLX6` → Nov 2026,
  `LBK3` → May 2023). Resolve as 2020 + digit.
- A robust parser may also use the observation date (`as_of`) to choose the
  nearest plausible non-past delivery month.

Derived contract identity:

- `delivery_year`, `delivery_month`
- `expiry_id = delivery_year * 12 + delivery_month - 1` (sort key)
- `contract_code` is unique per `(root, expiry_id)` in this dataset.

## 3. Rank panel (`rank_panel`)

One row per `date × commodity × rank` (24 × 4 × trading dates). Raw values are
preserved; no price forward-fill.

| Column | Description |
|---|---|
| `date` | Trading date (exchange/union calendar) |
| `root` | Generic root, e.g. `CL`, `C`, `SB` |
| `commodity` | Human-readable commodity |
| `sector` | Energy / Grains / Oilseeds / Softs / Livestock / Metals / Industrials |
| `exchange` | CME / CBOT / NYMEX / COMEX / ICE US / ICE |
| `rank` | 1–4 (generic nearby rank) |
| `ticker` | Raw generic ticker, e.g. `CL1 Comdty` |
| `contract_code` | Raw actual contract code, normalized |
| `delivery_year`, `delivery_month`, `expiry_id` | Parsed contract month |
| `settle` | `PX_SETTLE` |
| `volume` | `PX_VOLUME` |
| `open_interest` | `OPEN_INT` |
| `is_roll` | Contract changed vs previous valid date for this rank |
| `stale` | Settle unchanged vs previous valid date |
| `stale_run` | Consecutive stale sessions |
| `code_missing` | Settle present but contract code missing/`.NA.` |
| `volume_missing`, `oi_missing` | Raw fields blank |
| `negative_price` | Settle < 0 (CL 2020-04-20) |

## 4. Contract panel (`contract_panel`)

One row per `date × contract_code`; each contract's life as it moves from M4
to M1.

| Column | Description |
|---|---|
| `date` | Trading date |
| `root`, `commodity`, `sector`, `exchange` | Metadata |
| `contract_code` | Actual contract |
| `delivery_year`, `delivery_month`, `expiry_id` | Delivery month |
| `rank` | Current generic rank on this date |
| `settle`, `volume`, `open_interest` | Market fields |
| `first_date`, `last_date` | First/last observation of this contract |
| `last_trade_proxy` | Last observed date (proxy for last trading day) |
| `days_to_last_trading` | Trading sessions from `date` to `last_trade_proxy` |
| `is_censored` | Contract still alive at sample end (2026-10-13) |

`last_trade_proxy` is not an exchange calendar; it is the last date the
contract appears in this Bloomberg extract.

## 5. Return panel (`return_panel`)

| Column | Description |
|---|---|
| `date`, `root`, `rank`, `contract_code` | Keys |
| `settle` | Current settlement |
| `ret_contract` | `settle_t / settle_{t-1} - 1` within the same contract |
| `ret_rank` | Return mapped to the rank slot; on a roll date it uses the new contract's `ret_contract` |
| `is_roll` | Rank contract changed on this date |
| `ret_naive` | Diagnostic only: generic rank price change across the roll (not a tradable return) |
| `negative_price` | Settle < 0; percentage returns are flagged |

## 6. Spread panels (`spread`, `adjacent_spread`)

`spread` is the main selected pair (nearest two eligible adjacent contracts).
`adjacent_spread` contains every eligible adjacent pair (M1–M2, M2–M3, M3–M4)
for robustness/alternative-pair analysis; `is_main_pair` marks the main subset.

| Column | Description |
|---|---|
| `date`, `root` | Keys |
| `rank_near`, `rank_far` | Rank labels at this date |
| `contract_near`, `contract_far` | Actual contract codes (T1, T2) |
| `settle_near`, `settle_far` | Raw settlement prices |
| `spread_dollar` | `settle_near - settle_far` (primary) |
| `spread_log` | `log(settle_near) - log(settle_far)`; NaN if either ≤ 0 |
| `spread_pct` | `spread_dollar / settle_near` when near > 0 |
| `months_between` | Delivery-month distance |
| `days_to_last_near`, `days_to_last_far` | Trading-session distances |
| `is_selected_pair` | Main pair selected by the nearest-two-eligible rule |
| `eligible` | Both legs priced and pass the no-delivery-month + D rule |
| `liquidity_*` | Trailing median volume/OI per leg and pair min |
| `negative_price` | Either leg ≤ 0 |
| `stale_near`, `stale_far` | Stale flags |

## 7. Pair episodes (`pair_episodes`)

A maximal run of dates holding the same `(contract_near, contract_far)` pair
under the selected rule.

| Column | Description |
|---|---|
| `episode_id` | Stable ID |
| `root` | Commodity |
| `contract_near`, `contract_far` | Fixed contracts |
| `entry_date`, `exit_date` | First/last date of the episode |
| `holding_days` | Number of trading sessions |
| `entry_spread`, `exit_spread` | Dollar spread at entry/exit |
| `spread_change` | `exit_spread - entry_spread` |
| `pair_rank_mix` | e.g. `M1-M2`, `M2-M3` at episode start |
| `n_obs` | Valid observations |
| `mean_liq_volume`, `min_liq_volume` | Pair volume liquidity within the episode |
| `mean_liq_oi`, `min_liq_oi` | Pair OI liquidity within the episode |
| `flags` | stale/negative/missing |

## 8. Universe (`universe`)

| Column | Description |
|---|---|
| `date`, `root` | Keys |
| `pair` | e.g. `M1-M2` |
| `liq_volume_near`, `liq_volume_far` | Trailing 252-session median volume |
| `liq_volume_pair` | `min(near, far)` |
| `liq_oi_near`, `liq_oi_far`, `liq_oi_pair` | Same for open interest |
| `liq_proxy_near`, `liq_proxy_far`, `liq_proxy` | Rank-level fallback used because a leg had <60 observations |
| `pass_vol_1k`, `pass_vol_5k`, `pass_vol_10k`, `pass_vol_20k` | Volume threshold booleans; not applied by default |
| `pass_oi_1k`, `pass_oi_5k`, `pass_oi_10k`, `pass_oi_20k` | OI threshold booleans; not applied by default |

## 9. Missing, stale, and event conventions

- Missing prices: never forward-fill. A gap is carried as a multi-session
  return if needed and flagged; gaps >5 sessions are excluded from signals.
- Missing contract code: row cannot be aligned; drop from alignment and flag.
- Missing volume/OI: missing, not zero. Liquidity metrics use available
  observations; if both are missing, the leg fails liquidity.
- Stale: settle unchanged and volume zero/missing; flag; do not open new
  positions on stale prices.
- Negative price: CL 2020-04-20 = -37.63. Keep it. `spread_log` is NaN; dollar
  spread is still defined.
- Holidays: 128 all-blank weekdays are US market holidays; drop them from the
  union calendar. Per-commodity calendars may have additional closed days.
- Delistings/launches: XB starts 2005-10; LB ends 2023-05; CO/HG/RR start
  1988; NG starts 1990. Do not splice XB/HU or LB/LBR.

## 10. Backtest panels and tables

### 10.1 `backtest_pairs.parquet` / `backtest_spread.parquet`

K=5 ex-ante backtest universe, generated by
`src.panel.build_backtest_panel(rank, d=None, k=5)`. They are separate from the
D=10 research panels and are **not** substitutes for them.

- `backtest_pairs`: the main pair selected with
  `days_to_delivery_start >= 5` and no `days_to_last_trading` condition.
  Includes a `pair_rank_mix` and the same pair columns as `pairs.parquet`.
- `backtest_spread`: the pair panel plus `spread_dollar`, `spread_log`,
  `spread_pct`, `months_between`, and `negative_price`.
- K=5 has more M1–M2 exposure than D=10; the pair mix must be reported.

### 10.2 `contract_mark_state`

`src.panel.build_contract_mark_state()` produces one row per contract × union
trading day:

| Column | Description |
|---|---|
| `date`, `root`, `contract_code` | Keys |
| `settle`, `volume` | Raw values, if present |
| `settle_mark` | Last valid settle (carried through invalid rows) |
| `last_valid_settle` | Same as `settle_mark` |
| `sessions_since_valid` | Consecutive missing + stale + absent sessions |
| `is_valid` | Settle present and not stale |
| `is_stale` | Settle unchanged vs last valid and volume zero/missing |
| `is_missing` | Settle absent on a row that exists |
| `is_absent` | Contract has no row on that union-calendar date |

The rank-level `stale` / `stale_run` columns from `load.py` are not used by the
backtest; they are computed by `(root, rank)` and reset on rolls.

### 10.3 Signal panel

`src.signals.carry_signal()` returns:

| Column | Description |
|---|---|
| `date`, `root` | Keys |
| `commodity`, `sector` | Labels |
| `spread_dollar` | `P_near − P_far` |
| `carry_ann` | Annualized `(P_near − P_far) / P_far`; NaN if either leg ≤ 0 or days ≤ 0 |
| `score` | Raw signal used for position construction |
| `target` | +1 (long spread), −1 (short spread), 0 (no position) |

### 10.3b Continuous index (idea C)

`src.continuous.build_continuous_leg_prices()` returns one row per
`date × root` on the pair panel:

| Column | Description |
|---|---|
| `date`, `root` | Keys |
| `commodity`, `sector` | Labels |
| `contract_near`, `contract_far` | Current main pair |
| `settle_near`, `settle_far` | Raw settles for the pair |
| `raw_spread` | `settle_near − settle_far` |
| `near_index`, `far_index` | Additively chained leg indices |
| `spread_index` | `near_index − far_index`; NaN when either change is missing |
| `delta_near`, `delta_far` | Contract-level `settle_t − settle_{t−1}` |
| `prev_settle_near`, `prev_settle_far` | Previous observed settle per contract |
| `is_pair_change` | Fixed contract pair changed vs the previous date |
| `near_price_change_missing`, `far_price_change_missing` | Change unavailable; index held |
| `zero_prev_settle_near`, `zero_prev_settle_far` | Previous settle was zero; change treated as missing |

Construction: initialize each leg at the first observed settle, then add the
current contract's own price change. On a roll date the new pair's changes are
used, so the index has no level jump. The index is signal-only; backtest P&L
still uses the raw dollar spread.

`build_spread_index()` returns the same keys plus `spread_index`.
`roll_diagnostics()` adds `raw_spread_change`, `spread_index_change`, and
`expected_change = delta_near − delta_far`.

`rolling_ols_hedge_ratio()` estimates `h_t = Cov(near, far) / Var(far)` on the
trailing window (default 60 days, `min_periods=60`) and returns
`hedge_ratio`, `spread_index = near_index − h_t·far_index`,
`hedge_ratio_valid`, and `hedge_window_count`. Non-positive or non-finite `h`
is invalid and the hedge index is NaN there.

`kalman.kalman_hedge_ratio()` fits the paper's two-state DLM
(`near = β0 + β1·far`, random-walk β) with a 252-observation warm-up,
rolling 252-observation likelihood for `q` every 60 observations, and
`W = qV·I`. It returns the same keys plus `kalman_intercept`,
`kalman_observation_var`, `kalman_q`, `kalman_loglik`,
`kalman_is_reestimate`, and `kalman_pair_count`. `h` is NaN during the
warm-up; only finite positive `h` produces a hedge index.

### 10.3c Mean-reversion signal (idea C)

`src.signals.mean_reversion_signal()` returns a complete daily target path:

| Column | Description |
|---|---|
| `date`, `root` | Keys |
| `commodity`, `sector` | Labels |
| `spread_index` | Continuous dollar spread index |
| `score` | z-score of `spread_index` |
| `target` | +1 (long spread), −1 (short spread), 0 (flat); forced 0 when `has_pair=False` |
| `state` | Internal state before the `has_pair` filter |
| `evaluation_date` | Most recent weekly evaluation date; NaT before the first |
| `is_evaluation` | Last trading day of the week on the engine calendar |
| `z_valid` | Spread present and rolling window meets `min_periods` |
| `window_count` | Non-NaN observations in the trailing window |
| `has_pair` | A tradable pair exists for this date/root |

Conventions:

- z = (spread_index − rolling mean) / rolling std; L=20, `min_periods=16`,
  `ddof=1`; `std<=0` gives NaN.
- Entry at z crossing ±2; exit at z crossing 0; a flip is emitted as a direct
  ±1 target on the same evaluation date.
- The state updates only on `is_evaluation` dates; `target` is held between
  them. NaN windows do not open new positions and do not force an exit.
- `evaluation="daily"` raises `NotImplementedError` in the current baseline.

### 10.3d Curve-momentum / basis-momentum signal (idea D)

`src.signals.curve_momentum_signal()` returns a complete daily target path:

| Column | Description |
|---|---|
| `date`, `root` | Keys |
| `commodity`, `sector` | Labels |
| `target` | +1 (long near / short far), −1 (reverse), 0 (flat); forward-filled from the last month-end |
| `score` | `mom_near − mom_far` on signal dates; NaN otherwise |
| `is_signal_date` | The root's last pair date in a month, or a global month-end used to reset a month with no pair |
| `rank_near`, `rank_far` | Ranks used at the signal date; NaN otherwise |
| `mom_near`, `mom_far` | 12-month rank-slot returns at the signal date; NaN otherwise |

Construction:

- Build a rank return index per `(root, rank)` by compounding
  `1 + ret_rank`; NaN and negative-price/`ret_rank <= -1` days are held flat.
- At each month-end, compare the trailing 12-month index returns of the
  current `rank_near` and `rank_far`.
- A window needs at least 80% valid returns; a window containing
  `negative_price` or `ret_rank <= -1` is invalid.
- A month with no pair gets an explicit zero target; a NaN month-end score
  also sets the next month to zero.
- The signal is mathematically basis-momentum; P&L still uses the raw dollar
  spread through the engine.

### 10.4 Target legs

`src.backtest.build_target_legs()` returns one row per leg:

| Column | Description |
|---|---|
| `date`, `root` | Signal keys |
| `commodity`, `sector` | Labels |
| `group_id` | `root_contract_near_contract_far`; stable until a roll |
| `contract` | Actual contract code |
| `units` | Signed spread units |
| `leg` | `near` / `far` |
| `target` | Signal target |
| `hedge_ratio` | Optional; far units = `−target × hedge_ratio`; absent for the 1:1 baseline |

### 10.5 `BacktestResult`

- `positions`: date, root, commodity, sector, group_id, contract, units, mark,
  sessions_since_valid, is_valid, flag. End-of-day leg-level positions.
- `daily_returns`: date, root, commodity, sector, group_id, return_gross,
  return_net, gross_notional, cost, is_cost_row, sessions_since_valid, is_valid.
  `return_gross = Σ units × ΔP / Σ |units × P_prev|`; `is_cost_row=True` rows
  carry transition costs and are excluded from active-return averages.
- `portfolio_returns`: date, return_gross, return_net, cost, N_t, net_exposure.
  Equal-weight across active groups; `N_t = max(active groups, groups after
  trades)`; cost is `total_traded_notional × 5 bps / N_t`.
- `trades`: date, root, group_id, contract, units, price, reason, flag.
  Reasons: entry, exit, roll, rebalance, entry_blocked, pending_canceled.
  Flags: roll_leg_missing, exit_stale, forced_exit, pair_changed_before_fill.

Conventions:

- Signal at t close, fill at t+1 settlement close. `PX_SETTLE` is treated as the
  close/fill price.
- `BacktestConfig.rebalance` supports `last_trading_day_of_week` (default) and
  `last_trading_day_of_month`; the signal layer must use the same
  `curve.weekly_rebalance_dates` / `curve.monthly_rebalance_dates` helper.
- Gross-notional return uses the previous day's last valid prices.
- Costs are 5 bps per leg of that leg's notional, applied to actual net traded
  legs; a two-leg entry/exit ≈ 5 bps of gross, a four-leg roll/flip ≈ 10 bps.
- The 6th consecutive invalid session triggers a forced exit on the next
  trading day at the last valid mark.

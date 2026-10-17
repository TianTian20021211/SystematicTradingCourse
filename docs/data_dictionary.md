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

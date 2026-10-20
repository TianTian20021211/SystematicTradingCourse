# Transaction Costs — Model, Sources, Defaults

The backtest v2 (`src/costs.py`) charges three layers on every traded leg, per
side, and reports returns after each layer: gross → minus half-spread (the
first-order cost) → minus fees → minus market impact. Our Bloomberg extract has
settlement prices, volume and open interest only — no quotes and no depth — so
each layer is a model calibrated to published evidence rather than a
measurement.

## 1. How the three papers build positions and charge costs

| Paper | Position | Rebalance | Cost assumption |
|---|---|---|---|
| Paschke, Prokopczuk & Wese Simen (2020), *Curve Momentum* | Long the nearby with the higher 12-month signal, short the other (1st vs 2nd nearby); fully collateralised; equal-weighted within and across sectors | Monthly (1-month hold); alternative holds 1–24 months with overlapping portfolios | Three specs: 0.033% round trip per nearby (Locke & Venkatesh 1997); `(10 + Tick × M) / (F × M)` round trip (Szakmary et al. 2010, bid-ask = 1 tick, USD 10 fee); and `(10 + i × Tick × M)/(F × M)` for the i-th nearby. Net SR 0.85–0.93 vs gross 1.28. |
| Lubnau & Todorova (2015), *Mean Reversion* | One spread per commodity: front vs 2nd–5th contract, Kalman hedge ratio; Bollinger z-score entry at \|z\| > 2, exit at z = 0 or 0.2 | Event driven, daily checks; 2–21 day holds | 0.1% of the futures price per trade, four trades per round turn (deliberately above Locke & Venkatesh's 0.0004–0.033% to cover rolls and hedge-ratio changes). |
| Bianchi, Fan, Miffre & Zhang (2023), *Curve Dynamics* | S strategy: sign of ΔβS → long 1st / short 4th (or reverse); \|w\| = 1/(2N) per leg so Σ\|w\| = 1; fully collateralised | Daily, 1-day hold; daily turnover ≈ 1.2 | Turnover `TO = |w_t − w_{t−1+}|` with drifted weights; net return `r − 0.5 × Σ TO × TC`, with `TC1 = C/(F×M)`, `TC2 = 0.0167%`, `TC3 = (C + ¼ Tick × M)/(F×M)`, C = USD 1.5. Assumes listed spreads, which cross the bid-ask once (footnote 11). Net SR 0.44–1.04 vs gross 1.41. |

None of the three models market impact, and all treat the bid-ask spread as
roughly one tick. The v2 framework nests their assumptions (tick-based
half-spread, per-contract fee, listed-spread execution) and adds a
size-dependent impact layer.

## 2. Half-spread (first-order cost)

Default: 0.5 tick per contract for liquid contracts, i.e. a one-tick quoted
spread. Evidence:

- Szakmary, Shen & Sharma (2010) and Paschke et al. (2020): the bid-ask spread
  of the first nearby generally equals the minimum tick; a Bloomberg snapshot
  (Jan 2016) shows the same spread for the first two nearbys.
- Wang, Garcia & Irwin (2014, *AJAE*; 2012 NCCC-134 version): electronically
  traded corn, nearby and next-nearby BAS "well below two ticks"; average
  0.314 c/bu ≈ 1.26 ticks in the last 40 days before the delivery month;
  BAS widens sharply inside the delivery month (which our pairs avoid). Volume
  elasticity of the BAS ≈ −0.18.
- Locke & Venkatesh (1997, *JFM*), CME audit-trail data (1992): round-trip
  costs 0.0004–0.033%; Ferguson & Mann (2001) proportional spreads 0.59–5.56
  bps.

Thin contracts get a wider spread: `ticks = 0.5 × clip((ADV_ref / ADV)^0.18,
1, 10)` with `ADV_ref = 10,000` contracts and ADV the trailing 20-day mean
volume (lagged). A 100-lot ADV gives ≈ 1.15 ticks; 10 lots ≈ 1.7 ticks.
Missing volume is imputed with the root's median ADV (unknown ≠ zero).

Execution: by default legs are matched into listed calendar-spread orders, so
a balanced pair trade pays one half-spread per spread instead of one per leg
(`execution="spread"`, Bianchi et al. footnote 11). `execution="legs"` legs
each contract separately (twice the half-spread cost).

## 3. Fees

Default: USD 1.5 per contract per side on every leg (exchanges charge per leg
even for spread orders). This is the all-in retail-broker figure of Gao,
Han, Li & Zhou (2018) used by both Paschke et al. and Bianchi et al.; current
CME/ICE non-member exchange + clearing fees are of the same order (≈ USD
1–2.5 per side by product; see the CME fee schedules), and Szakmary et al.'s
USD 10 is a conservative upper bound. Fees are proportional to contracts, so
they do not depend on capital once positions are fractional.

## 4. Market impact

Default: square-root law (Tóth et al. 2011, *PRX*; Bouchaud, Bonart, Donier &
Gould 2018):

`impact_USD = Y × σ_daily × sqrt(Q / ADV) × notional_traded`, `Y = 0.5`,

with σ the leg's trailing 60-day daily return volatility and ADV its trailing
20-day mean volume, both lagged one day. Y is of order one in CFM's futures
metaorders; public EuroStoxx futures data give Y ≈ 0.5. The law describes
metaorders, and impact is closer to linear for very small participation, so
the first contract of every order is impact free
(`impact_free_contracts = 1`): a one-lot fills at the touch and pays only the
half-spread.

Conservative choices to keep in mind: σ is the outright leg volatility (a
listed spread order would move a much less volatile instrument), and impact is
charged per leg. Thin markets that pass the liquidity filter (oats, rough
rice, orange juice, lumber) dominate impact at USD 10m; raise
`sizing.filter_liquid(min_adv=...)` to exclude them.

## 5. Capital and sizing

Positions are fully collateralised: each active root gets a gross-notional
budget (default 1/N with N the 5-day max of active roots), legs have equal
notional (as in the papers) or 1:1 contracts, and returns are P&L / capital.
Capital is the total for the portfolio, not per commodity. Under equal weight
every root gets the same notional, so the thinnest markets (oats, orange
juice, rough rice, lumber) trade several percent of their daily volume at USD
10m while CL or GC trade 0.01%; capacity is set by the thin markets.
`scheme="liquidity"` sizes each root by dollar ADV ** alpha (alpha = 0 equal
weight, alpha = 1 equal participation); at alpha = 0.5 the carry example's
impact drag at USD 10m falls from ~161 to ~85 bps/yr.

Default capital is USD 1m for the whole portfolio (D-017). Contracts are
fractional by default; `SimConfig(round_lots=True)` rounds every leg to whole
contracts and skips a spread whose smallest leg is below half a lot, which
shows how few positions a USD 100k book can actually hold. The paper's own
cost scenarios are available as `costs.paper_scenarios()` (TC1–TC3 of
Bianchi et al. 2023, per side, legs costed individually, no impact).

Contracts are fractional, so gross returns, half-spread and fees in % of
capital do not depend on capital; only impact does. `report.capacity_curve`
rescales every trade by C/C₀ and re-costs it, which is exact under linear
scaling (tested against a full re-simulation).

## References

- Bianchi, R. J., Fan, J. H., Miffre, J., & Zhang, T. (2023). Exploiting the dynamics of commodity futures curves. *JBF* 154, 106965.
- Bouchaud, J.-P., Bonart, J., Donier, J., & Gould, M. (2018). *Trades, Quotes and Prices.* Cambridge University Press.
- Ferguson, M. F., & Mann, S. C. (2001). Execution costs and their intraday variation in futures markets. *Journal of Business* 74(1).
- Gao, L., Han, Y., Li, S. Z., & Zhou, G. (2018). Market intraday momentum. *JFE* 129(2).
- Locke, P. R., & Venkatesh, P. C. (1997). Futures market transaction costs. *JFM* 17(2).
- Lubnau, T., & Todorova, N. (2015). Trading on mean-reversion in energy futures markets. *Energy Economics* 51.
- Marshall, B. R., Nguyen, N. H., & Visaltanachoti, N. (2012). Commodity liquidity measurement and transaction costs. *RFS* 25(2). (Low-frequency proxies; Amihud correlates best with intraday benchmarks.)
- Paschke, R., Prokopczuk, M., & Wese Simen, C. (2020). Curve momentum. *JBF* 113, 105718.
- Szakmary, A. C., Shen, Q., & Sharma, S. C. (2010). Trend-following trading strategies in commodity futures: A re-examination. *JBF* 34(2).
- Tóth, B., Lempérière, Y., Deremble, C., de Lataillade, J., Kockelkoren, J., & Bouchaud, J.-P. (2011). Anomalous price impact and the critical nature of liquidity in financial markets. *Physical Review X* 1, 021006.
- Wang, X., Garcia, P., & Irwin, S. H. (2014). The behavior of bid-ask spreads in the electronically-traded corn futures market. *AJAE* 96(2).

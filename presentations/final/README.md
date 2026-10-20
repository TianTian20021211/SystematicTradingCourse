# Final presentation — merged draft

Status: **draft for review**. 38 pages (33 numbered main frames + closing and
4 backup/reference pages), compiled locally. The deck is intentionally simple:
one table or a few bullets per slide, with the key numbers on the slide.
A–D each use three pages: idea, gross backtest + robustness, position + gross
P&L. E and the alpha-combination section were merged from `origin/main`.

## Build

```bash
cd presentations/final
tectonic -X compile --outdir build main.tex
open build/main.pdf
```

Alternative, if a full TeX Live with `metropolis` is installed:

```bash
latexmk -xelatex -outdir=build main.tex
```

`build/` and the PDF are gitignored. `main.tex`, `refs.bib`, `figures/` and
`tables/` are the source.

## Structure and timing (20 minutes)

| Part | Slides | Content | Time |
|---|---|---|---:|
| Setup | 1–7 | Title, question, data, panel, engine, trading environment, roadmap | ~3.5 min |
| A | 8–10 | Spread convergence: idea, gross backtest, position/P&L | ~2.5 min |
| B | 11–13 | Curve relative-value convergence: idea, backtest, position/P&L | ~2 min |
| C | 14–16 | Mean reversion: idea, gross backtest + robustness, position/P&L | ~2.5 min |
| D | 17–19 | Curve momentum: trade idea + parameters, backtest + robustness, position/P&L | ~2.5 min |
| E | 20–25 | Nelson–Siegel: paper, replication, timing, commodities, Kalman | ~3 min |
| Combining alphas | 26–32 | IC screen, model choice, ridge schemes, lumber diagnosis | ~3 min |
| Conclusion | 33–34 | Summary, thank you, Q&A | ~1 min |
| Backup | 35–38 | Data QA, cost definitions, A-flip IC, references | — |

The 20 minutes are tight: A–D alone are about 13 minutes, and E plus the
combination section add about 6 minutes. If the talk runs long, the
position/P&L pages (10, 13, 16, 19) and the alpha detail pages (27–29, 31–32)
are the easiest to skip or move to backup.

## What is real, what is placeholder

- All result tables use the **official v2 figures (D-019)** from
  `output/v2_rerun/comparison.csv`; v1 numbers are not mixed in.
- A/B are presented directly as **convergence designs**; the original
  assignment directions are not mentioned.
  A: spread convergence (contango → long spread, backwardation → short spread).
  B: curve relative-value convergence (long lowest-carry adjacent spread,
  short highest).
- A/B are labeled **candidate (gross)**. They are not standalone strategies;
  transaction costs are deferred to the portfolio.
- A has a related reference, not a paper replication: **Kanamura, Rachev &
  Fabozzi (2010)**. B has no related-paper block; its idea page is a pure
  design statement. C is the direct replication of **Lubnau & Todorova
  (2015)**.
- C follows the same three-page pattern as A/B: **idea, gross backtest +
  robustness, position/gross P&L**. The backtest page keeps the six-row
  robustness table (three hedge ratios, train/test, daily validation gate,
  execution lag/placebo, breadth/jackknife, IC/OOS R²). C is evaluated
  **gross-only**: the table has no net or cost column, and the slide says costs
  are deferred to the portfolio. The weekly table is the official D-019
  result; the daily audit is validation-only; the test read is
  **descriptive** and not a new selection input. The validation gate failed.
- C page 3 uses regenerated official weekly C1 figures
  (`figures/c_mean_reversion_positions.pdf` and
  `figures/c_mean_reversion_pnl.pdf`) in the same simple style as A/B/D: a
  single-panel year-end signed-position heatmap and one cumulative gross P&L
  line. The P&L figure is gross by design, matching the gross-only result.
- D follows the same three-page pattern: **trade idea + parameters**
  (signal construction, N=2, 12-month formation, monthly hold, eligibility),
  **gross backtest + robustness**, and **position book + gross P&L**. The
  paper is cited in one line on the idea page. The robustness table keeps the
  D-028 numbers; the static always-long comparison is 11.1 vs D timing
  11.2 bp/month.
- E is no longer blank. It reproduces the paper's slope strategy (21
  commodities, 1992–2019, $1m) and separates the paper's same-settle timing
  from a tradable t+1 fill. Paper timing gross is +3.11%/yr; the tradable
  [t+1, t+2] gross is −0.18%/yr, so the signal lives for one day and is
  **not tradable**. The roadmap marks E `not tradable`.
- The alpha-combination section is implemented, not a placeholder. It builds
  12 alpha factors from A–E, screens them on 1986–2005, compares linear and
  tree models on validation, and reports four ridge rebalancing schemes. The
  22-day scheme is the only one that stays positive after all costs in the
  test slice (net +0.32%/yr, Sharpe 0.30); the test column is descriptive,
  read once before the ridge choice. The lumber diagnosis is included.
- A's backtest slide includes the **horizon-decay figure** (1–20 day marginal
  and cumulative gross return); the per-root 5-day IC bootstrap is a backup
  slide after the appendix.
- The position/P&L slides (A, B, C, D) use the v2 holdings simulator. D's
  figure is a **gross-only** cumulative return, matching the gross table. B's
  gross P&L matches the +0.50% table. A's figure uses a 0.5× target and is
  illustrative; the +0.63% table is the execution-free 5-day information
  test, not the holdings path. C's figure and table are **gross-only**. Keep
  these distinctions if the slides are edited.

## Decisions already taken

- Slides are in **English** (same as the mid-term deck).
- A/B are presented as convergence strategies; no original version or "flip"
  wording appears in the deck.
- A–D are evaluated **gross-only**; costs are deferred to the portfolio.
  C follows the same convention.
- E is presented as a replication with a timing diagnostic, and is labeled
  **not tradable**.
- The alpha-combination section uses the D-030/D-031/D-032 results; its test
  read is descriptive and was not used for tuning.
- The 20 minutes are **talk time**; Q&A is separate.

## Remaining questions

1. The merged deck is 38 pages. Which position/P&L and alpha-detail pages
   should be cut or moved to backup for the 20-minute talk?
2. Who presents E and the combination section: the teammate only, Jiaheng, or
   Tian? Do you want Chinese speaker notes for the A–D part?
3. Should the A/B related papers be full citations on the slides (current:
   author-year inline) or only in the References backup?
4. A/B/C/D remain gross-only. Keep the gross framing for the talk, or add a
   net-of-cost summary slide at the end?

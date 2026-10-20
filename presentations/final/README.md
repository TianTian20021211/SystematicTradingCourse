# Final presentation — framework draft

Status: **draft for review**. 26 pages (21 main frames + backup), compiled
locally, not committed. The deck is intentionally simple: one table or a few
bullets per slide, with the key numbers on the slide. Each idea uses three
main pages: idea, backtest + robustness, position/P\&L.

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

`build/` and the PDF are gitignored. `main.tex` and `refs.bib` are the source.

## Structure and timing (20 minutes)

| Part | Slides | Content | Time |
|---|---|---|---:|
| Setup | 1–6 | Title, project question, data, panel, engine, roadmap | ~3.5 min |
| A | 7–9 | Spread convergence: idea, gross backtest, position/P&L | ~2.5 min |
| B | 10–12 | Curve relative-value convergence: idea, backtest, position/P&L | ~2 min |
| C | 13–15 | Mean reversion: idea, backtest + robustness, position/P&L | ~2.5 min |
| D | 16–18 | Curve momentum: trade idea + parameters, backtest + robustness, position/P&L | ~2.5 min |
| **Tian to D** | **1–18** | | **~13 min** |
| E | 19 | Reserved for teammate | ~3 min |
| Portfolio | 20 | Combining the alphas — placeholder | ~3 min |
| Conclusion | 21–22 | Summary, thank you, Q&A | ~1.5 min |

The A–D block is now about 13 minutes, slightly over the original 12-minute
target. If the talk runs long, the position/P&L slides (9, 12, 18) are the
easiest to skip or move to backup; the roadmap (6) and the D robustness
table (17) are the next to compress.

## What is real, what is placeholder

- All result tables use the **official v2 figures (D-019)** from
  `output/v2_rerun/comparison.csv`; v1 numbers are not mixed in.
- A/B are presented directly as **convergence designs**; the original
  assignment directions are not mentioned.
  A: spread convergence (contango → long spread, backwardation → short spread).
  B: curve relative-value convergence (long lowest-carry adjacent spread,
  short highest).
- Both are labeled **candidate (gross)**. They are not standalone strategies;
  A's transaction costs are still deferred, and B's half-spread alone exceeds
  its gross return.
- A has a related reference, not a paper replication: **Kanamura, Rachev &
  Fabozzi (2010)** for spread trading as a mean-reverting process. B has no
  related-paper block; its idea page is a pure design statement. C is the
  direct replication of **Lubnau & Todorova (2015)**.
- C now follows the same three-page pattern as A/B: **idea, gross backtest +
  robustness, position/gross P&L**. The backtest page keeps the six-row
  robustness table (three hedge ratios, train/test, daily validation gate,
  execution lag/placebo, breadth/jackknife, IC/OOS R²). C is evaluated
  **gross-only**: the table has no net or cost column and the slide says costs
  are deferred to the portfolio. The weekly table is the official D-019
  result; the daily audit is validation-only; the test read is
  **descriptive** and not a new selection input. The validation gate failed.
- C page 3 uses regenerated official weekly C1 figures
  (`figures/c_mean_reversion_positions.pdf` and
  `figures/c_mean_reversion_pnl.pdf`) in the same simple style as A/B/D: a
  single-panel year-end signed-position heatmap and one cumulative gross P&L
  line. The P&L figure is gross by design, matching the gross-only result.
- D now follows the same three-page pattern: **trade idea + parameters**
  (signal construction, N=2, 12-month formation, monthly hold, eligibility),
  **gross backtest + robustness**, and **position book + gross P&L**. The
  paper is cited in one line on the idea page, not discussed as a separate
  replication frame. The robustness table keeps the D-028 numbers, with a
  one-line conclusion per check and no takeaway box; the static always-long
  comparison is 11.1 vs D timing 11.2 bp/month. The old `+0.108%/yr` static
  bullet was B's D=10 static front/back and is removed from D.
- **E (slide 19) is intentionally blank** and reserved for the teammate.
- **The portfolio figure on slide 20 is a placeholder.** The combination model
  is the remaining research step, not a finished result.
- A's backtest slide includes the **horizon-decay figure** (1–20 day marginal
  and cumulative gross return); the per-root 5-day IC bootstrap is a backup
  slide after the appendix.
- The position/P&L slides (A, B, C, D) use the v2 holdings simulator. D's
  figure is a **gross-only** cumulative return, matching the gross table; no
  cost layer is shown. B's gross P&L matches the +0.50% table. A's figure uses
  a 0.5× target and is illustrative; the +0.63% table is the execution-free
  5-day information test, not the holdings path. C's figure and table are
  **gross-only**, regenerated from the same v2 run as the D-019 table; costs
  are deferred to the portfolio. Keep these distinctions if the slides are
  edited.

## Decisions already taken

- Slides are in **English** (same as the mid-term deck).
- A/B are presented as convergence strategies; no original version or "flip"
  wording appears in the deck.
- The portfolio slide stays a **placeholder**.
- The 20 minutes are **talk time**; Q&A is separate.

## Remaining questions

1. Title: keep "Systematic Trading / Project 7: Commodity Futures Calendar
   Spreads", or use a shorter final title?
2. Who presents E and the portfolio section: the teammate only, or Jiaheng?
   Do you want Chinese speaker notes for the Tian part?
3. Should the A/B related papers be full citations on the slides (current:
   author-year inline) or only in the References backup?
4. A still has **gross-only** results. Run the v2 all-in net backtest, or keep
   the gross table with the explicit "costs deferred" caveat?

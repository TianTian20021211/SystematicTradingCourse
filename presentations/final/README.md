# Final presentation — framework draft

Status: **draft skeleton for review**. 23 pages, compiled locally, not committed.
The deck is intentionally simple: one table or a few bullets per slide, with the
key numbers on the slide.

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
| A | 7–8 | Original A one line negative; A-flip as main design + result | ~2 min |
| B | 9–10 | Original B one line negative; B-flip as main design + result | ~1.5 min |
| C | 11–13 | Lubnau–Todorova paper, replication choices, results | ~2.5 min |
| D | 14–16 | Paschke et al. paper, replication choices, results/validity | ~2.5 min |
| **Tian to D** | **1–16** | | **~12 min** |
| E | 17 | Reserved for teammate | ~3 min |
| Portfolio | 18 | Combining the alphas — placeholder | ~3 min |
| Conclusion | 19–20 | Summary, thank you, Q&A | ~2 min |

The 12-minute split for A–D leaves about 8 minutes for E, the portfolio and the
conclusion. If the talk runs long, the roadmap slide (6) and the two
"what we replicated" slides (12, 15) are the easiest to compress.

## What is real, what is placeholder

- All result tables use the **official v2 figures (D-019)** from
  `output/v2_rerun/comparison.csv`; v1 numbers are not mixed in.
- The original A/B directions are disposed of in **one line each** (negative).
  A-flip / B-flip are presented as **our main design**, but labeled
  **candidate / post-hoc, gross-only**. They are not standalone strategies.
- A/B have related references, not paper replications: **Koijen et al. (2018)**
  for commodity carry and **Masturzo & Leung (2025)** for intra-commodity
  calendar-spread pairs. The slides say the flip is our data-driven reversal,
  not the paper's design.
- The daily C audit is labeled **descriptive**; the validation gate failed.
- **E (slides 17) is intentionally blank** and reserved for the teammate.
- **The portfolio figure on slide 18 is a placeholder.** The combination model
  is the remaining research step, not a finished result.
- Result slides currently use tables, not figures. Figures from
  `output/figures/` can be added later once the story is fixed.

## Decisions already taken

- Slides are in **English** (same as the mid-term deck).
- A-flip / B-flip stay in the **main story**; the original A/B get one line each.
- The portfolio slide stays a **placeholder**.
- The 20 minutes are **talk time**; Q&A is separate.

## Remaining questions

1. Title: keep "Systematic Trading / Project 7: Commodity Futures Calendar
   Spreads", or use a shorter final title?
2. Result slides: keep the current tables, or add the NAV/positions figures
   from `output/figures/`?
3. Who presents E and the portfolio section: the teammate only, or Jiaheng?
   Do you want Chinese speaker notes for the Tian part?
4. Should the A/B related papers be full citations on the slides (current:
   author-year inline) or only in the References backup?

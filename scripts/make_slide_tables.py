"""LaTeX tables for the final deck (presentations/final/tables/*.tex).

Each table is written as a bare ``tabular`` so the slide controls the float,
caption and font size; the raw numbers go to ``output/slides/*.csv``.

Usage:
    python scripts/make_slide_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config, costs, marks, nelson_siegel as ns, panel, report, simulate, specs  # noqa: E402

OUT_TEX = ROOT / "presentations" / "final" / "tables"
OUT_CSV = config.OUTPUT_DIR / "slides"
PAPER_SAMPLE = ("1992-01-02", "2019-06-28")
# (label, fill at the signal's own settle?, sleeves k)
E_ROWS = [
    (r"$[t,\,t+1]$, paper timing", True, 1),
    (r"$[t+1,\,t+2]$", False, 1),
    (r"$[t+1,\,t+6]$, $k=5$", False, 5),
    (r"$[t+1,\,t+21]$, $k=20$", False, 20),
]
V2_LAYERS = ["gross", "- half-spread", "- fees", "- impact (all)"]


def e_backtest_grid() -> pd.DataFrame:
    """Annualised return and Sharpe of the NS slope strategy by timing, holding and cost model.

    Paper universe (21 roots), paper lambda, paper sample 1992-2019, USD 1m.
    """

    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    contract = panel.build_backtest_panel(rank, d=5, k=5)["contract"]
    mk = marks.build_marks(contract, specs.load_contract_specs())
    st = ns.build_slope_strategy(contract, mk, rule="paper", roots=ns.PAPER_ROOTS)
    rows = []
    for label, same, k in E_ROWS:
        sweep = lambda cost: report.k_sweep(st["signal"], st["pairs"], mk, [k],
                                            simulate.SimConfig(capital=1e6, cost=cost), same_settle=same,
                                            start=PAPER_SAMPLE[0], end=PAPER_SAMPLE[1]).iloc[0]
        v2 = sweep(costs.CostParams())
        row = {"row": label, "turnover_x": v2["turnover_x"]}
        for layer in V2_LAYERS:
            row[f"ret|{layer}"], row[f"sr|{layer}"] = v2[f"ret_{layer}"], v2[f"sr_{layer}"]
        for name, cost in costs.paper_scenarios().items():
            r = sweep(cost)
            row[f"ret|{name}"], row[f"sr|{name}"] = r["ret_- impact (all)"], r["sr_- impact (all)"]
        rows.append(row)
        print("done", label)
    return pd.DataFrame(rows)


def _signed(x: float) -> str:
    """Two decimals with an explicit sign; a value that rounds to zero prints as 0.00."""

    return "0.00" if round(x, 2) == 0 else f"{x:+.2f}"


def _cell(ret: float, sr: float) -> str:
    return rf"${_signed(ret)}$ $({_signed(sr)})$"


def e_backtest_tex(grid: pd.DataFrame) -> Path:
    """Write the grid as a bare tabular: annualised return % with annualised Sharpe in parentheses."""

    cols = ["gross", "TC1", "TC2", "TC3", "- half-spread", "- fees", "- impact (all)"]
    lines = [
        r"\begin{tabular}{@{}l r r r r r r r@{}}",
        r"\toprule",
        r" & & \multicolumn{3}{c}{Paper cost scenarios} & \multicolumn{3}{c}{Our v2 costs, cumulative} \\",
        r"\cmidrule(lr){3-5}\cmidrule(l){6-8}",
        r"Fill and holding window & Gross & TC1 & TC2 & TC3 & Half-spread & $+$ fees & $+$ impact \\",
        r"\midrule",
    ]
    for i, (_, r) in enumerate(grid.iterrows()):
        rets = [rf"${_signed(r[f'ret|{c}'])}$" for c in cols]
        srs = [rf"$({_signed(r[f'sr|{c}'])})$" for c in cols]
        if i:
            lines.append(r"\addlinespace[2pt]")
        lines.append(" & ".join([r["row"]] + rets) + r" \\")
        lines.append(" & ".join([""] + srs) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    OUT_TEX.mkdir(parents=True, exist_ok=True)
    path = OUT_TEX / "e_backtest.tex"
    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> None:
    cached = OUT_CSV / "e_backtest_grid.csv"
    grid = pd.read_csv(cached) if "--cached" in sys.argv and cached.exists() else e_backtest_grid()
    OUT_CSV.mkdir(parents=True, exist_ok=True)
    grid.to_csv(OUT_CSV / "e_backtest_grid.csv", index=False)
    print(grid.round(3).to_string())
    print(e_backtest_tex(grid))


if __name__ == "__main__":
    main()

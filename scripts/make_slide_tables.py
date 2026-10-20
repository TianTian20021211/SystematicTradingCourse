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
        r" & & \multicolumn{3}{c}{Paper cost scenarios} & \multicolumn{3}{c}{Our costs, cumulative} \\",
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


RIDGE_ORDER = [("daily", "Daily"), ("every 5 days", "Every 5 days"), ("every 22 days", "Every 22 days"),
               ("XS, every 5 days", "Cross-section, 5 days")]


def f_ridge_tex() -> Path:
    """Ridge rebalancing schemes: full-sample cost layers and net-of-all-cost by period."""

    perf = pd.read_parquet(config.OUTPUT_DIR / "alpha" / "perf_ridge.parquet")
    get = lambda run, per, layer, col: perf.loc[perf["run"].eq(run) & perf["period"].eq(per)
                                                & perf["layer"].eq(layer), col].iat[0]
    layers = ["gross", "- half-spread", "- fees", "- impact (all)"]
    lines = [
        r"\begin{tabular}{@{}l r r r r r r r r@{}}",
        r"\toprule",
        r" & & \multicolumn{4}{c}{Full sample 1986--2026} & \multicolumn{3}{c}{All costs, by period} \\",
        r"\cmidrule(lr){3-6}\cmidrule(l){7-9}",
        r"Rebalance & Turnover & Gross & Half-spread & $+$ fees & $+$ impact & Train & Valid & Test \\",
        r"\midrule",
    ]
    for i, (run, label) in enumerate(RIDGE_ORDER):
        cells = [(get(run, "full", l, "ann_ret_pct"), get(run, "full", l, "sharpe")) for l in layers]
        cells += [(get(run, p, "- impact (all)", "ann_ret_pct"), get(run, p, "- impact (all)", "sharpe"))
                  for p in ("train", "valid", "test")]
        turn = get(run, "full", "gross", "turnover_x")
        if i:
            lines.append(r"\addlinespace[2pt]")
        lines.append(" & ".join([label, rf"${turn:.0f}\times$"] + [rf"${_signed(r)}$" for r, _ in cells]) + r" \\")
        lines.append(" & ".join(["", ""] + [rf"$({_signed(sr)})$" for _, sr in cells]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    path = OUT_TEX / "f_ridge.tex"
    path.write_text("\n".join(lines) + "\n")
    return path


CASH_SETTLED = {"CO", "FC", "LH"}
MONTHS_PER_YEAR = {"CL": 12, "CO": 12, "HO": 12, "NG": 12, "XB": 12, "BO": 8, "FC": 8, "LH": 8, "SM": 8, "S": 7,
                   "GC": 6, "JO": 6, "LB": 6, "LC": 6, "RR": 6, "C": 5, "CC": 5, "CT": 5, "HG": 5, "KC": 5,
                   "O": 5, "SI": 5, "W": 5, "SB": 4}


def f_groups_tex(run: str = "every 22 days | equal") -> Path:
    """Net-of-all-cost contribution of the 22-day ridge book by contract structure and settlement."""

    import numpy as np

    b = pd.read_parquet(config.OUTPUT_DIR / "alpha" / "by_root_lbfix.parquet")
    b = b.loc[b["run"].eq(run)].assign(date=lambda d: pd.to_datetime(d["date"]))
    b["net"] = b["pnl_gross"] - b[["cost_half_spread", "cost_fee", "cost_impact"]].sum(axis=1)
    dates = pd.DatetimeIndex(sorted(b["date"].unique()))
    m = b["root"].map(MONTHS_PER_YEAR)
    groups = [("12 contracts a year", m.eq(12)), ("6 to 8 a year", m.between(6, 8)), ("4 to 5 a year", m.le(5)),
              None, ("Cash settled", b["root"].isin(CASH_SETTLED)), ("Physically delivered", ~b["root"].isin(CASH_SETTLED))]
    periods = [("1986-01-01", "2005-12-31"), ("2006-01-01", "2015-12-31"), ("2016-01-01", "2026-12-31")]
    lines = [r"\begin{tabular}{@{}l r r r r@{}}", r"\toprule",
             r"Group & Roots & Train & Valid & Test \\", r"\midrule"]
    for g in groups:
        if g is None:
            lines.append(r"\midrule")
            continue
        name, mask = g
        d = b.loc[mask].groupby("date")["net"].sum().reindex(dates, fill_value=0.0) / 1e6
        cells = []
        for lo, hi in periods:
            x = d.loc[lo:hi]
            cells.append((x.mean() * 252 * 1e4, x.mean() / x.std() * np.sqrt(252)))
        lines.append(" & ".join([name, str(b.loc[mask, "root"].nunique())] + [rf"${_signed(r)}$" for r, _ in cells]) + r" \\")
        lines.append(" & ".join(["", ""] + [rf"$({_signed(sr)})$" for _, sr in cells]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    path = OUT_TEX / "f_groups.tex"
    path.write_text("\n".join(lines) + "\n")
    return path


SUMMARY_ROWS = [("a", "A spread convergence (flip)"), ("b", "B relative value (flip)"), ("c", "C mean reversion"),
                ("d", "D curve momentum"), ("e", "E Nelson--Siegel slope")]


def summary_grid(capital: float = 1e6) -> pd.DataFrame:
    """Gross and all-in net of every idea's headline strategy, one engine, USD 1m, full sample, t+1 fill."""

    from src import b_flip, sizing, v2_rerun, v2_signals

    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    inputs = v2_signals.load_v2_inputs(rank, d=5, k=5, min_adv=100)
    settings = v2_rerun.RerunSettings(capital=capital)
    results = {
        "a": simulate.simulate(v2_signals.flip_legs(v2_signals.a_legs(inputs)), inputs.marks,
                               v2_rerun._config("a", settings)),
        "b": b_flip.run_b_flip(inputs, rank, capital=capital)["result"],
        "c": v2_rerun.run_strategy("c", rank, settings, inputs=inputs)["result"],
        "d": v2_rerun.run_strategy("d", rank, settings, inputs=inputs)["result"],
    }
    st = ns.build_slope_strategy(inputs.bt["contract"], inputs.marks, rule="rolling_ssr")
    legs = sizing.legs_from_signal(st["signal"], st["pairs"], k=1)
    results["e"] = simulate.simulate(legs, inputs.marks, simulate.SimConfig(capital=capital))
    rows = []
    for key, label in SUMMARY_ROWS:
        perf = report.performance_table(results[key]).set_index("layer")
        rows.append({"row": label, "turnover_x": perf.loc["gross", "turnover_x"],
                     "gross": perf.loc["gross", "ann_ret_pct"], "sr_gross": perf.loc["gross", "sharpe"],
                     "net": perf.loc["- impact (all)", "ann_ret_pct"], "sr_net": perf.loc["- impact (all)", "sharpe"]})
        print("done", label, rows[-1])
    return pd.DataFrame(rows)


SUMMARY_NOTES = {
    "A spread convergence (flip)": "gross edge, costs take all of it",
    "B relative value (flip)": "best gross Sharpe, half-spread exceeds it",
    "C mean reversion": "costs are 2.7 times the gross",
    "D curve momentum": "weak gross, unstable across periods",
    "E Nelson--Siegel slope": "no edge with a $t+1$ fill",
    "Combined alphas, ridge, every 22 days": "net positive in every period",
}


def summary_tex(grid: pd.DataFrame) -> Path:
    """Write the cross-idea summary (gross and all-in net at USD 1m) plus the 22-day ridge row."""

    perf = pd.read_parquet(config.OUTPUT_DIR / "alpha" / "perf_ridge.parquet")
    p = perf.loc[perf["run"].eq("every 22 days") & perf["period"].eq("full")].set_index("layer")
    ridge = {"row": "Combined alphas, ridge, every 22 days", "turnover_x": p.loc["gross", "turnover_x"],
             "gross": p.loc["gross", "ann_ret_pct"], "sr_gross": p.loc["gross", "sharpe"],
             "net": p.loc["- impact (all)", "ann_ret_pct"], "sr_net": p.loc["- impact (all)", "sharpe"]}
    lines = [r"\begin{tabular}{@{}l r r r l@{}}", r"\toprule",
             r"Strategy & Turnover & Gross & All-in net & Bottom line \\", r"\midrule"]
    for i, r in enumerate([*grid.to_dict("records"), ridge]):
        if i == len(grid):
            lines.append(r"\midrule")
        lines.append(" & ".join([r["row"], rf"${r['turnover_x']:.0f}\times$",
                                 rf"${_signed(r['gross'])}$ $({_signed(r['sr_gross'])})$",
                                 rf"${_signed(r['net'])}$ $({_signed(r['sr_net'])})$",
                                 SUMMARY_NOTES[r["row"]]]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    path = OUT_TEX / "summary.tex"
    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> None:
    if "--summary" in sys.argv:
        cached = OUT_CSV / "summary_grid.csv"
        grid = pd.read_csv(cached) if "--cached" in sys.argv and cached.exists() else summary_grid()
        OUT_CSV.mkdir(parents=True, exist_ok=True)
        grid.to_csv(cached, index=False)
        print(grid.round(3).to_string())
        print(summary_tex(grid))
        return
    if "--groups" in sys.argv:
        print(f_groups_tex())
        return
    if "--ridge" in sys.argv:
        print(f_ridge_tex())
        return
    cached = OUT_CSV / "e_backtest_grid.csv"
    grid = pd.read_csv(cached) if "--cached" in sys.argv and cached.exists() else e_backtest_grid()
    OUT_CSV.mkdir(parents=True, exist_ok=True)
    grid.to_csv(OUT_CSV / "e_backtest_grid.csv", index=False)
    print(grid.round(3).to_string())
    print(e_backtest_tex(grid))


if __name__ == "__main__":
    main()

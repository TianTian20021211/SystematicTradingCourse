"""Alpha-combination pipeline (D-030): screen factors, fit models, backtest.

Stage ``select`` uses data up to 2015-12-31 only (train 1986-2005, validation
2006-2015): factor panel, block-length experiment, per-horizon screen, model
zoo, paired model comparison, validation backtests and ``selection.json``.
Stage ``test`` reads the frozen selection, refits on 1986-2015, runs the full
sample once and writes ``test_readonce.json``.

Usage:
    python scripts/run_alpha.py --stage select
    python scripts/run_alpha.py --stage test --confirm-read-once
    python scripts/run_alpha.py --stage horizons   # IC term structure to 252 days (<= 2015)
    python scripts/run_alpha.py --stage exlb       # descriptive post-test rerun without LB (D-031)
    python scripts/run_alpha.py --stage lowfreq    # low-frequency execution grid on validation (D-031)
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import (  # noqa: E402
    alpha_factors as af, alpha_models as M, alpha_portfolio as P, alpha_screen as S,
    c_daily, config, report, v2_signals,
)

OUT = config.OUTPUT_DIR / "alpha"
SELECT_END = "2015-12-31"
TRADABLE = [t for t in af.TARGETS if not t.startswith("fwd_0_")]
TS_RULES = ("sign", "linear", "band")
CAPITAL = 1e6
log = logging.getLogger("run_alpha")


def horizon_len(target: str) -> int:
    a, b = (int(x) for x in target.split("_")[1:])
    return b - a


def block_for(target: str, base: int) -> int:
    """Block length for a horizon: at least the chosen base and the window length."""

    return max(base, horizon_len(target))


def load_inputs():
    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    return rank, v2_signals.load_v2_inputs(rank, d=5, k=5, min_adv=100)


def screen_all(panel: pd.DataFrame, base_block: int, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-horizon screen on the usable train rows."""

    train = S.slice_period(panel.loc[panel["usable"]], "train")
    cols, screens, roots = list(af.FACTORS), [], []
    for tgt in af.TARGETS:
        mats = S.rank_matrices(train, cols, tgt)
        boot = S.joint_bootstrap(mats, cols, block_for(tgt, base_block), n_boot)
        tab = pd.concat([S.ic_table(mats, boot, c) for c in cols], ignore_index=True)
        screens.append(S.screen(tab).assign(target=tgt))
        roots.append(tab.assign(target=tgt))
        log.info("screen %s: %s", tgt, screens[-1].loc[screens[-1]["selected"], "score"].tolist())
    return pd.concat(screens, ignore_index=True), pd.concat(roots, ignore_index=True)


def fit_zoo(panel: pd.DataFrame, features: dict, fit_periods: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    """Predictions of every model for every horizon (one frame per horizon)."""

    out = {}
    for tgt in af.TARGETS:
        f = panel[["date", "root"]].copy()
        for m in M.MODEL_ZOO:
            t0 = time.time()
            f[m] = M.fit_predict(panel, features[tgt], tgt, m, fit_periods)
            log.info("fit %s %s %.1fs", tgt, m, time.time() - t0)
        out[tgt] = f
    return out


def compare_all(panel: pd.DataFrame, preds: dict, base_block: int, n_boot: int):
    """Paired model comparison on usable validation rows, per horizon."""

    pairs, summ, draws, chosen = [], [], {}, {}
    models = list(M.MODEL_ZOO)
    for tgt, pr in preds.items():
        v = panel[["date", "root", "usable", tgt]].merge(pr, on=["date", "root"])
        v = S.slice_period(v.loc[v["usable"]], "valid")
        p, s, d = M.compare_models(v, models, tgt, block_for(tgt, base_block), n_boot)
        pairs.append(p.assign(target=tgt))
        summ.append(s.assign(target=tgt))
        draws[tgt] = d
        chosen[tgt] = M.select_model(s)
        log.info("models %s: chosen %s", tgt, chosen[tgt])
    return pd.concat(pairs, ignore_index=True), pd.concat(summ, ignore_index=True), draws, chosen


def backtest_valid(panel, preds, chosen, inputs) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validation backtests of every tradable horizon x rule at $1m (marks cut at 2015)."""

    mk = c_daily.truncate_marks(inputs.marks, SELECT_END)
    pairs = inputs.pairs.loc[inputs.pairs["date"] <= SELECT_END]
    perf, daily = [], []
    for tgt in TRADABLE:
        pred = preds[tgt][chosen[tgt]]
        fc = P.forecast_frame(panel, pred, tgt)
        scale = fc.loc[fc["date"] <= S.PERIODS["train"][1], "pred"].std()
        for rule in P.RULES:
            res = P.run_rule(fc, rule, pairs, mk, k=horizon_len(tgt), capital=CAPITAL, scale=scale)
            for per in ("train", "valid"):
                perf.append(report.performance_table(res, *S.PERIODS[per]).assign(target=tgt, rule=rule, period=per))
            daily.append(res.daily.assign(target=tgt, rule=rule))
            log.info("backtest %s %s done", tgt, rule)
    return pd.concat(perf, ignore_index=True), pd.concat(daily, ignore_index=True)


def choose_strategies(perf: pd.DataFrame) -> dict:
    """Best time-series and best cross-sectional configuration by validation net Sharpe."""

    v = perf.loc[perf["period"].eq("valid") & perf["layer"].eq("- impact (all)")]
    ts = v.loc[v["rule"].isin(TS_RULES)].sort_values("sharpe", ascending=False).iloc[0]
    xs = v.loc[v["rule"].eq("xs")].sort_values("sharpe", ascending=False).iloc[0]
    return {"ts": {"target": ts["target"], "rule": ts["rule"], "valid_net_sharpe": float(ts["sharpe"])},
            "xs": {"target": xs["target"], "rule": "xs", "valid_net_sharpe": float(xs["sharpe"])}}


def stage_select(n_boot: int) -> None:
    rank, inputs = load_inputs()
    # Firewall: marks and pairs end at 2015-12-31, so forward returns that
    # would need 2016 settles are NaN rather than leaking into validation.
    inputs = v2_signals.V2Inputs(
        bt=inputs.bt,
        marks=c_daily.truncate_marks(inputs.marks, SELECT_END),
        pairs=inputs.pairs.loc[inputs.pairs["date"] <= SELECT_END].reset_index(drop=True),
    )
    panel = af.build_factor_panel(inputs, rank)
    assert panel["date"].max() <= pd.Timestamp(SELECT_END)
    panel.to_parquet(OUT / "panel_select.parquet")
    train = S.slice_period(panel.loc[panel["usable"]], "train")
    sens = S.block_sensitivity(train, list(af.FACTORS), "fwd_1_6", n_boot=n_boot)
    sens.to_parquet(OUT / "block_sensitivity.parquet")
    base = S.choose_block(sens)
    log.info("chosen block %d", base)
    screen, roots = screen_all(panel, base, n_boot)
    screen.to_parquet(OUT / "screen.parquet")
    roots.to_parquet(OUT / "screen_roots.parquet")
    features = {t: screen.loc[screen["target"].eq(t) & screen["selected"], "score"].tolist() for t in af.TARGETS}
    preds = fit_zoo(panel, features, ("train",))
    for tgt, f in preds.items():
        f.to_parquet(OUT / f"preds_select_{tgt}.parquet")
    pairs, summ, draws, chosen = compare_all(panel, preds, base, n_boot)
    pairs.to_parquet(OUT / "model_pairs.parquet")
    summ.to_parquet(OUT / "model_summary.parquet")
    with open(OUT / "model_draws.pkl", "wb") as fh:
        pickle.dump(draws, fh)
    coefs = pd.concat([M.coefficients(panel, features[t], t, m).rename("value").reset_index()
                       .rename(columns={"index": "factor"}).assign(target=t, model=m)
                       for t in af.TARGETS for m in dict.fromkeys(("ols", chosen[t]))], ignore_index=True)
    coefs.to_parquet(OUT / "coefficients.parquet")
    perf, daily = backtest_valid(panel, preds, chosen, inputs)
    perf.to_parquet(OUT / "perf_select.parquet")
    daily.to_parquet(OUT / "daily_select.parquet")
    selection = {"block": base, "features": features, "models": chosen, **choose_strategies(perf)}
    (OUT / "selection.json").write_text(json.dumps(selection, indent=2))
    log.info("selection: %s", selection)


def run_full(panel, inputs, cfg: dict, model: str, features: list[str], capital: float, round_lots=False):
    """Full-sample simulation of one frozen configuration."""

    tgt = cfg["target"]
    pred = M.oos_predictions(panel, features, tgt, model)
    fc = P.forecast_frame(panel, pred, tgt)
    scale = fc.loc[fc["date"] <= S.PERIODS["train"][1], "pred"].std()
    res = P.run_rule(fc, cfg["rule"], inputs.pairs, inputs.marks, k=horizon_len(tgt),
                     capital=capital, scale=scale, round_lots=round_lots)
    return res, pred


def stage_test(force: bool) -> None:
    marker = OUT / "test_readonce.json"
    if marker.exists() and not force:
        raise SystemExit(f"test already read ({marker}); pass --force to override and log it")
    sel = json.loads((OUT / "selection.json").read_text())
    rank, inputs = load_inputs()
    panel = af.build_factor_panel(inputs, rank)
    panel.to_parquet(OUT / "panel_full.parquet")
    preds = panel[["date", "root"]].copy()
    for tgt in af.TARGETS:
        preds[tgt] = M.oos_predictions(panel, sel["features"][tgt], tgt, sel["models"][tgt])
    preds.to_parquet(OUT / "preds_full.parquet")
    perf, results = [], {}
    runs = [("ts", CAPITAL, False), ("xs", CAPITAL, False), ("ts", 1e5, False), ("ts", 1e5, True)]
    for key, cap, lots in runs:
        cfg = sel[key]
        model, feats = sel["models"][cfg["target"]], sel["features"][cfg["target"]]
        res, _ = run_full(panel, inputs, cfg, model, feats, cap, lots)
        name = f"{key}_{int(cap):d}{'_lots' if lots else ''}"
        results[name] = res
        for per in ("full", "train", "valid", "test"):
            rng = (None, None) if per == "full" else S.PERIODS[per]
            perf.append(report.performance_table(res, *rng).assign(run=name, period=per))
        log.info("full run %s done", name)
    pd.concat(perf, ignore_index=True).to_parquet(OUT / "perf_full.parquet")
    report.capacity_curve(results[f"ts_{int(CAPITAL)}"], (1e5, 3e5, 1e6, 3e6, 1e7, 3e7)).to_parquet(
        OUT / "capacity_ts.parquet")
    with open(OUT / "results_full.pkl", "wb") as fh:
        pickle.dump(results, fh)
    marker.write_text(json.dumps({"read_at": pd.Timestamp.now().isoformat(), "selection": sel, "force": force}, indent=2))


TERM_HORIZONS = (1, 2, 5, 10, 21, 42, 63, 126, 252)
TERM_SCORES = {"pred_fwd_1_22": "Forecast fitted for [t+1, t+22]", "pred_fwd_1_6": "Forecast fitted for [t+1, t+6]",
               "a_carry": "a_carry", "b_rel_carry": "b_rel_carry", "c_rev5": "c_rev5", "d_mom252": "d_mom252"}


def stage_horizons(n_boot: int) -> None:
    """IC term structure on rolled returns up to 252 days and a look-ahead check (data <= 2015)."""

    sel = json.loads((OUT / "selection.json").read_text())
    panel = pd.read_parquet(OUT / "panel_select.parquet")
    for t in ("fwd_1_6", "fwd_1_22"):
        pr = pd.read_parquet(OUT / f"preds_select_{t}.parquet")[["date", "root", sel["models"][t]]]
        panel = panel.merge(pr.rename(columns={sel["models"][t]: f"pred_{t}"}), on=["date", "root"])
    panel = panel.merge(af.rolled_forward(panel, TERM_HORIZONS), on=["date", "root"])
    usable = panel.loc[panel["usable"]]
    rows = []
    for per in ("train", "valid"):
        f = S.slice_period(usable, per)
        for h in TERM_HORIZONS:
            mats = S.rank_matrices(f, list(TERM_SCORES), f"roll_{h}")
            boot = S.joint_bootstrap(mats, list(TERM_SCORES), max(sel["block"], h), n_boot)
            for c in TERM_SCORES:
                a = S.ic_table(mats, boot, c).query("root == 'ALL'").iloc[0]
                rows.append(dict(period=per, h=h, score=c, ic=a["ic"], ci_lo=a["ci_lo"], ci_hi=a["ci_hi"]))
            log.info("term structure %s h=%d", per, h)
    term = pd.DataFrame(rows).assign(ic_ann=lambda d: d["ic"] * np.sqrt(252 / d["h"]))
    term.to_parquet(OUT / "ic_term_structure.parquet")
    # Look-ahead check: lag the forecast by L extra root days; a leak would make IC collapse.
    f = S.slice_period(usable, "valid").sort_values(["root", "date"]).copy()
    rows = []
    for t in ("fwd_1_6", "fwd_1_22"):
        for lag in (0, 1, 2, 5):
            f["lagged"] = f.groupby("root")[f"pred_{t}"].shift(lag)
            mats = S.rank_matrices(f, ["lagged"], t)
            boot = S.joint_bootstrap(mats, ["lagged"], max(sel["block"], horizon_len(t)), n_boot)
            a = S.ic_table(mats, boot, "lagged").query("root == 'ALL'").iloc[0]
            rows.append(dict(target=t, lag=lag, ic=a["ic"], ci_lo=a["ci_lo"], ci_hi=a["ci_hi"]))
    pd.DataFrame(rows).to_parquet(OUT / "lookahead_check.parquet")


def stage_exlb(drop: tuple[str, ...] = ("LB",)) -> None:
    """Descriptive post-test rerun of the frozen TS/XS configurations without ``drop`` roots.

    Reuses the frozen out-of-sample forecasts in ``preds_full.parquet``; no
    selection is changed (D-031).
    """

    sel = json.loads((OUT / "selection.json").read_text())
    rank, inputs = load_inputs()
    panel = pd.read_parquet(OUT / "panel_full.parquet")
    preds = pd.read_parquet(OUT / "preds_full.parquet")
    keep = ~panel["root"].isin(drop)
    pairs = inputs.pairs.loc[~inputs.pairs["root"].isin(drop)]
    perf, results = [], {}
    for key in ("ts", "xs"):
        tgt = sel[key]["target"]
        pred = panel[["date", "root"]].merge(preds[["date", "root", tgt]], on=["date", "root"], how="left")[tgt]
        fc = P.forecast_frame(panel, pred.to_numpy(), tgt)
        scale = fc.loc[fc["date"] <= S.PERIODS["train"][1], "pred"].std()
        fc = fc.loc[keep.reindex(fc.index)]
        res = P.run_rule(fc, sel[key]["rule"], pairs, inputs.marks, k=horizon_len(tgt), capital=CAPITAL, scale=scale)
        name = f"{key}_{int(CAPITAL)}_ex{'_'.join(drop)}"
        results[name] = res
        for per in ("full", "train", "valid", "test"):
            rng = (None, None) if per == "full" else S.PERIODS[per]
            perf.append(report.performance_table(res, *rng).assign(run=name, period=per))
        log.info("ex-%s run %s done", drop, name)
    pd.concat(perf, ignore_index=True).to_parquet(OUT / "perf_full_exLB.parquet")
    with open(OUT / "results_full_exLB.pkl", "wb") as fh:
        pickle.dump(results, fh)


LOWFREQ_TARGETS = ("fwd_1_6", "fwd_1_11", "fwd_1_22")
LOWFREQ_EXEC = (("k", 1), ("k", 5), ("k", 10), ("k", 22), ("k", 44), ("every", 5), ("every", 10), ("every", 22))


def _full_run(panel, preds, inputs, tgt, rule, k, every, drop=()):
    """Full-sample run of one configuration from the frozen OOS forecasts."""

    pred = panel[["date", "root"]].merge(preds[["date", "root", tgt]], on=["date", "root"], how="left")[tgt]
    fc = P.forecast_frame(panel, pred.to_numpy(), tgt)
    scale = fc.loc[fc["date"] <= S.PERIODS["train"][1], "pred"].std()
    fc = fc.loc[~fc["root"].isin(drop)]
    pairs = inputs.pairs.loc[~inputs.pairs["root"].isin(drop)]
    return P.run_rule(fc, rule, pairs, inputs.marks, k=k, every=every, capital=CAPITAL, scale=scale)


def stage_lowfreq() -> None:
    """Low-frequency execution grid on validation, then a descriptive full-sample run (D-031)."""

    sel = json.loads((OUT / "selection.json").read_text())
    rank, inputs = load_inputs()
    mk = c_daily.truncate_marks(inputs.marks, SELECT_END)
    pairs = inputs.pairs.loc[inputs.pairs["date"] <= SELECT_END]
    panel = pd.read_parquet(OUT / "panel_select.parquet")
    perf = []
    for tgt in LOWFREQ_TARGETS:
        pr = pd.read_parquet(OUT / f"preds_select_{tgt}.parquet")[sel["models"][tgt]]
        fc = P.forecast_frame(panel, pr, tgt)
        scale = fc.loc[fc["date"] <= S.PERIODS["train"][1], "pred"].std()
        for rule in ("linear", "sign"):
            for kind, n in LOWFREQ_EXEC:
                k, every = (n, 1) if kind == "k" else (1, n)
                res = P.run_rule(fc, rule, pairs, mk, k=k, every=every, capital=CAPITAL, scale=scale)
                for per in ("train", "valid"):
                    perf.append(report.performance_table(res, *S.PERIODS[per]).assign(
                        target=tgt, rule=rule, kind=kind, n=n, period=per))
                log.info("lowfreq %s %s %s=%d done", tgt, rule, kind, n)
    perf = pd.concat(perf, ignore_index=True)
    perf.to_parquet(OUT / "perf_lowfreq.parquet")
    v = perf.loc[perf["period"].eq("valid") & perf["layer"].eq("- impact (all)")]
    best = v.sort_values("sharpe", ascending=False).iloc[0]
    choice = {"target": best["target"], "rule": best["rule"], "kind": best["kind"], "n": int(best["n"]),
              "valid_net_sharpe": float(best["sharpe"])}
    (OUT / "lowfreq_selection.json").write_text(json.dumps(choice, indent=2))
    log.info("lowfreq choice %s", choice)
    full = pd.read_parquet(OUT / "panel_full.parquet")
    preds = pd.read_parquet(OUT / "preds_full.parquet")
    k, every = (choice["n"], 1) if choice["kind"] == "k" else (1, choice["n"])
    results, perf_full = {}, []
    for name, drop in (("lowfreq", ()), ("lowfreq_exLB", ("LB",))):
        res = _full_run(full, preds, inputs, choice["target"], choice["rule"], k, every, drop)
        results[name] = res
        for per in ("full", "train", "valid", "test"):
            rng = (None, None) if per == "full" else S.PERIODS[per]
            perf_full.append(report.performance_table(res, *rng).assign(run=name, period=per))
    pd.concat(perf_full, ignore_index=True).to_parquet(OUT / "perf_lowfreq_full.parquet")
    with open(OUT / "results_lowfreq.pkl", "wb") as fh:
        pickle.dump(results, fh)


LOWFREQ_DESC = (("fwd_1_6", "linear", "k", 5), ("fwd_1_6", "linear", "k", 22), ("fwd_1_6", "linear", "k", 44),
                ("fwd_1_6", "linear", "every", 22), ("fwd_1_22", "linear", "k", 22), ("fwd_1_22", "sign", "every", 22))


def stage_lowfreq_desc() -> None:
    """Descriptive full-sample runs of representative low-frequency configurations (post-test, D-031)."""

    rank, inputs = load_inputs()
    full = pd.read_parquet(OUT / "panel_full.parquet")
    preds = pd.read_parquet(OUT / "preds_full.parquet")
    perf, daily = [], []
    for tgt, rule, kind, n in LOWFREQ_DESC:
        k, every = (n, 1) if kind == "k" else (1, n)
        for drop in ((), ("LB",)):
            res = _full_run(full, preds, inputs, tgt, rule, k, every, drop)
            name = f"{tgt}|{rule}|{kind}={n}" + ("|exLB" if drop else "")
            for per in ("full", "train", "valid", "test"):
                rng = (None, None) if per == "full" else S.PERIODS[per]
                perf.append(report.performance_table(res, *rng).assign(run=name, period=per))
            daily.append(res.daily.assign(run=name))
            log.info("lowfreq desc %s done", name)
    pd.concat(perf, ignore_index=True).to_parquet(OUT / "perf_lowfreq_desc.parquet")
    pd.concat(daily, ignore_index=True).to_parquet(OUT / "daily_lowfreq_desc.parquet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("select", "test", "horizons", "exlb", "lowfreq", "lowfreq_desc"), required=True)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--confirm-read-once", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.FileHandler(OUT / f"run_alpha_{args.stage}.log"), logging.StreamHandler()])
    if args.stage == "select":
        stage_select(args.n_boot)
    elif args.stage == "horizons":
        stage_horizons(args.n_boot)
    elif args.stage == "exlb":
        stage_exlb()
    elif args.stage == "lowfreq":
        stage_lowfreq()
    elif args.stage == "lowfreq_desc":
        stage_lowfreq_desc()
    else:
        if not args.confirm_read_once:
            raise SystemExit("stage test reads 2016-2026 once; pass --confirm-read-once")
        stage_test(args.force)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()

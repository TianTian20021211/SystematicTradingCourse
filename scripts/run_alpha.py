"""Alpha-combination pipeline (D-030): screen factors, fit models, backtest.

Stage ``select`` uses data up to 2015-12-31 only (train 1986-2005, validation
2006-2015): factor panel, block-length experiment, per-horizon screen, model
zoo, paired model comparison, validation backtests and ``selection.json``.
Stage ``test`` reads the frozen selection, refits on 1986-2015, runs the full
sample once and writes ``test_readonce.json``.

Usage:
    python scripts/run_alpha.py --stage select
    python scripts/run_alpha.py --stage test --confirm-read-once
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("select", "test"), required=True)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--confirm-read-once", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.FileHandler(OUT / f"run_alpha_{args.stage}.log"), logging.StreamHandler()])
    if args.stage == "select":
        stage_select(args.n_boot)
    else:
        if not args.confirm_read_once:
            raise SystemExit("stage test reads 2016-2026 once; pass --confirm-read-once")
        stage_test(args.force)


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()

"""Run the D-027 daily C information audit and the D-029 full-sample view.

Stage 1 uses marks truncated at 2015-12-31, so it cannot read test P&L. It
selects the variant on validation and writes a gate. Stage 2 reads the test
sample once, only if the validation gate passed, and writes a marker. Stage
``full`` (D-029) reads the test once as a descriptive presentation, persists
the daily artifacts and writes the same one-read marker.

Usage:
    python scripts/run_c_daily_audit.py --stage stage1
    python scripts/run_c_daily_audit.py --stage stage2 --selected c1 --confirm-read-once
    python scripts/run_c_daily_audit.py --stage full --confirm-read-once
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import c_audit, c_daily, config, signals, v2_rerun, v2_signals  # noqa: E402

OUT = config.OUTPUT_DIR / "c_daily_audit"
STAGE1 = OUT / "stage1_train_validation"
STAGE2 = OUT / "stage2_test"
FULL = OUT / "full"
GATE_FILE = STAGE1 / "gate.json"
MARKER = OUT / "test_readonce.json"
FULL_REASON = "descriptive full-sample presentation"

NAME_TO_METHOD = c_daily.NAME_TO_METHOD
METHOD_TO_NAME = c_daily.METHOD_TO_NAME
WEEKLY_NAMES = {"1:1": "c", "ols": "c_ols", "kalman": "c_kalman"}


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _stage1_inputs(inputs: v2_signals.V2Inputs) -> v2_signals.V2Inputs:
    return v2_signals.V2Inputs(
        bt=inputs.bt,
        marks=c_daily.truncate_marks(inputs.marks),
        pairs=inputs.pairs,
    )


def _weekly_table(
    rank: pd.DataFrame,
    inputs_stage1: v2_signals.V2Inputs,
    settings: v2_rerun.RerunSettings,
) -> pd.DataFrame:
    rows = []
    for method, name in WEEKLY_NAMES.items():
        item = v2_rerun.run_strategy(name, rank, settings, inputs=inputs_stage1)
        stats = c_daily.gross_summary(
            item["result"], c_daily.VALIDATION_PERIOD[0], c_daily.VALIDATION_PERIOD[1]
        )
        rows.append({"method": method, "frequency": "weekly", **stats})
    return pd.DataFrame(rows)


def run_stage1(args: argparse.Namespace) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGE1.mkdir(parents=True, exist_ok=True)

    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    settings = v2_rerun.RerunSettings()
    inputs = v2_signals.load_v2_inputs(
        rank, d=settings.d, k=settings.k, min_adv=settings.min_adv
    )
    audit_settings = c_daily.DailyCSettings(
        block=args.block,
        n_boot=args.n_boot,
        seed=args.seed,
    )

    print("stage 1: running daily C1/C2/C3 (marks truncated at 2015-12-31)")
    results = c_daily.run_stage1(inputs, settings=audit_settings)
    selection, selected = c_daily.selection_steps(results, audit_settings)
    gate = c_daily.validation_gate(results, selected, audit_settings)
    gate["test_read"] = False

    for method, item in results.items():
        _write(item["performance"].reset_index(), STAGE1 / f"{METHOD_TO_NAME[method]}_performance.csv")
        _write(item["root"].reset_index(), STAGE1 / f"{METHOD_TO_NAME[method]}_root.csv")
        c_daily.assert_stage1_only(item["result"].daily)

    _write(selection, STAGE1 / "selection.csv")
    (STAGE1 / "gate.json").write_text(json.dumps(gate, indent=2, default=str))

    # Weekly reference on the same truncated sample.
    inputs_stage1 = _stage1_inputs(inputs)
    weekly = _weekly_table(rank, inputs_stage1, settings)
    daily = pd.DataFrame(
        [
            {
                "method": method,
                "frequency": "daily",
                **c_daily.gross_summary(
                    item["result"], *c_daily.VALIDATION_PERIOD
                ),
            }
            for method, item in results.items()
        ]
    )
    _write(pd.concat([weekly, daily], ignore_index=True), STAGE1 / "weekly_vs_daily.csv")

    # Diagnostics on the truncated marks panel.
    fwd = c_daily.forward_panel(
        inputs,
        [(0, 1), (1, 2), (1, 6), (1, 11), (1, 21)],
        marks=inputs_stage1.marks,
        end="2015-12-31",
    )
    for method, item in results.items():
        sig = c_daily.daily_signal(inputs, method)
        name = METHOD_TO_NAME[method]
        _write(
            c_audit.event_study(
                sig, fwd, *c_daily.VALIDATION_PERIOD
            ),
            STAGE1 / f"{name}_event_study.csv",
        )
        _write(
            c_audit.timing_table(
                sig,
                fwd,
                {
                    "train 1986-2005": c_daily.TRAIN_PERIOD,
                    "validation 2006-2015": c_daily.VALIDATION_PERIOD,
                },
            ),
            STAGE1 / f"{name}_timing.csv",
        )
        _write(
            c_audit.persistence_table(
                sig, {"validation 2006-2015": c_daily.VALIDATION_PERIOD}
            ),
            STAGE1 / f"{name}_persistence.csv",
        )

    # IC and nested regressions for the selected variant (and C1 as reference).
    carry = signals.carry_signal(inputs.pairs)
    for method in dict.fromkeys(["1:1", selected]):
        sig = c_daily.daily_signal(inputs, method)
        name = METHOD_TO_NAME[method]
        _write(
            c_audit.ic_table(
                sig,
                fwd,
                *c_daily.VALIDATION_PERIOD,
                block=args.block,
                n_boot=args.n_boot,
                seed=args.seed,
            ),
            STAGE1 / f"{name}_ic.csv",
        )
        _write(
            c_audit.nested_predictive_table(
                sig, fwd, carry, *c_daily.VALIDATION_PERIOD
            ),
            STAGE1 / f"{name}_nested_r2.csv",
        )

    sig_c1 = c_daily.daily_signal(inputs, "1:1")
    placebo, draws = c_audit.placebo_table(
        sig_c1,
        fwd,
        *c_daily.VALIDATION_PERIOD,
        n_draws=args.n_placebo,
        seed=args.seed,
    )
    (STAGE1 / "c1_placebo.json").write_text(json.dumps(placebo, indent=2, default=str))
    np.save(STAGE1 / "c1_placebo_draws.npy", draws)
    _write(
        c_audit.jackknife_table(
            results[selected]["result"], *c_daily.VALIDATION_PERIOD
        ),
        STAGE1 / f"{METHOD_TO_NAME[selected]}_jackknife.csv",
    )

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(),
        "stage": "stage1",
        "settings": audit_settings.__dict__,
        "selected": selected,
        "validation_gate": gate,
    }
    (OUT / "manifest_stage1.json").write_text(json.dumps(manifest, indent=2, default=str))

    print(selection.round(3).to_string(index=False))
    print(json.dumps(gate, indent=2, default=str))
    print(f"stage 1 written to {STAGE1}")
    if not gate["pass_validation"]:
        print("validation gate failed: stage 2 will not read the test sample")


def run_stage2(args: argparse.Namespace) -> None:
    if not GATE_FILE.exists():
        raise SystemExit("stage 1 gate.json not found")
    gate = json.loads(GATE_FILE.read_text())
    if not gate.get("pass_validation"):
        raise SystemExit("validation gate failed; refusing to read test")
    if args.selected != gate.get("selected"):
        raise SystemExit(
            f"--selected {args.selected!r} does not match stage-1 {gate.get('selected')!r}"
        )
    if not args.confirm_read_once:
        raise SystemExit("pass --confirm-read-once to read the test sample")
    if MARKER.exists() and not args.force_test_read:
        raise SystemExit("test already read; refusing without --force-test-read")

    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    settings = v2_rerun.RerunSettings()
    inputs = v2_signals.load_v2_inputs(
        rank, d=settings.d, k=settings.k, min_adv=settings.min_adv
    )
    audit_settings = c_daily.DailyCSettings(
        block=args.block, n_boot=args.n_boot, seed=args.seed
    )
    method = NAME_TO_METHOD[args.selected]
    item = c_daily.run_variant(inputs, method, audit_settings)
    test = c_daily.test_gate(item["result"], audit_settings)

    STAGE2.mkdir(parents=True, exist_ok=True)
    _write(item["performance"].reset_index(), STAGE2 / "performance.csv")
    _write(item["root"].reset_index(), STAGE2 / "root.csv")
    _write(
        c_audit.event_study(
            c_daily.daily_signal(inputs, method),
            c_daily.forward_panel(
                inputs, [(0, 1), (1, 2), (1, 6), (1, 11), (1, 21)]
            ),
            *c_daily.TEST_PERIOD,
        ),
        STAGE2 / "event_study.csv",
    )
    (STAGE2 / "gate.json").write_text(json.dumps(test, indent=2, default=str))
    mark = {
        "read_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected": args.selected,
        "commit": _git_commit(),
        "validation_gate": gate,
        "test_gate": test,
    }
    MARKER.write_text(json.dumps(mark, indent=2, default=str))
    print(json.dumps(test, indent=2, default=str))


def _stage1_gate_check(gate: dict) -> bool | None:
    """Verify that the full-sample validation gate matches D-027 stage 1.

    The full run rebuilds the frozen validation signal path and simulates it on
    the full marks; validation P&L must therefore be identical to stage 1.
    Returns ``None`` when the stage-1 artifacts are not present (for example a
    fresh checkout with gitignored outputs).
    """

    if not GATE_FILE.exists():
        return None
    frozen = json.loads(GATE_FILE.read_text())
    mismatches = []
    for key in ("selected", "pass_validation"):
        if frozen.get(key) != gate.get(key):
            mismatches.append(
                f"{key}: stage1={frozen.get(key)!r} full={gate.get(key)!r}"
            )
    for key in ("validation_sr", "validation_breadth"):
        left, right = frozen.get(key), gate.get(key)
        if left is None or right is None or not np.isclose(
            float(left), float(right), rtol=1e-9, atol=1e-12
        ):
            mismatches.append(f"{key}: stage1={left!r} full={right!r}")
    if mismatches:
        raise SystemExit(
            "full-sample validation gate disagrees with D-027 stage 1: "
            + "; ".join(mismatches)
        )
    return True


def run_full(args: argparse.Namespace) -> None:
    """Descriptive full-sample run (D-029).

    Runs C1/C2/C3 on the full 1986–2026 marks with zero costs and USD 10m
    capital, saves the daily signal/leg/P&L/position artifacts, and writes the
    shared one-read marker. This does not change the D-027 gate/selection or
    the official weekly D-019 results; the 2016–2026 slice is descriptive only.
    """

    try:
        c_daily.check_full_read_allowed(
            MARKER, args.confirm_read_once, args.force_test_read
        )
    except ValueError as exc:
        raise SystemExit(str(exc))

    previous = json.loads(MARKER.read_text()) if MARKER.exists() else None

    rank = pd.read_parquet(config.PROCESSED_DIR / "rank.parquet")
    settings = v2_rerun.RerunSettings()
    inputs = v2_signals.load_v2_inputs(
        rank, d=settings.d, k=settings.k, min_adv=settings.min_adv
    )
    audit_settings = c_daily.DailyCSettings(
        block=args.block,
        n_boot=args.n_boot,
        seed=args.seed,
    )

    print("full: running daily C1/C2/C3 on 1986-2026 marks (zero cost, USD 10m)")
    results = {
        method: c_daily.run_variant(inputs, method, audit_settings)
        for method in c_daily.METHODS
    }
    selection, selected = c_daily.selection_steps(results, audit_settings)
    gate = c_daily.validation_gate(results, selected, audit_settings)
    if args.selected is not None and args.selected != selected:
        raise SystemExit(
            f"--selected {args.selected!r} does not match the D-027 selection "
            f"{selected!r}"
        )
    stage1_consistent = _stage1_gate_check(gate)

    FULL.mkdir(parents=True, exist_ok=True)
    for method, item in results.items():
        c_daily.save_variant_artifacts(item, FULL)
    _write(selection, FULL / "selection.csv")
    (FULL / "gate.json").write_text(json.dumps(gate, indent=2, default=str))

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(),
        "stage": "full",
        "reason": FULL_REASON,
        "test_read": True,
        "sample": "1986-01-01..2026-10-13",
        "settings": audit_settings.__dict__,
        "selected": selected,
        "gate": gate,
        "stage1_gate_consistent": stage1_consistent,
        "artifacts": sorted(
            str(path.relative_to(OUT)) for path in FULL.rglob("*") if path.is_file()
        ),
    }
    (OUT / "manifest_full.json").write_text(
        json.dumps(manifest, indent=2, default=str)
    )

    mark = {
        "read_at_utc": datetime.now(timezone.utc).isoformat(),
        "reason": FULL_REASON,
        "stage": "full",
        "selected": selected,
        "gate": gate,
        "test_read": True,
        "commit": _git_commit(),
    }
    if previous is not None:
        mark["previous_read"] = {
            key: previous.get(key)
            for key in ("read_at_utc", "reason", "stage", "selected", "commit")
        }
    MARKER.write_text(json.dumps(mark, indent=2, default=str))

    print(selection.round(3).to_string(index=False))
    print(json.dumps(gate, indent=2, default=str))
    print(f"full artifacts written to {FULL}")
    print(f"test read marker written to {MARKER}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["stage1", "stage2", "full"], default="stage1")
    parser.add_argument("--selected", choices=sorted(NAME_TO_METHOD), default=None)
    parser.add_argument("--confirm-read-once", action="store_true")
    parser.add_argument("--force-test-read", action="store_true")
    parser.add_argument("--block", type=int, default=21)
    parser.add_argument("--n-boot", type=int, default=2_000)
    parser.add_argument("--n-placebo", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.stage == "stage1":
        run_stage1(args)
    elif args.stage == "stage2":
        run_stage2(args)
    else:
        run_full(args)


if __name__ == "__main__":
    main()

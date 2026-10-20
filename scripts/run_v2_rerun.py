#!/usr/bin/env python
"""Run the v2 A/D/C/C-hedge/B re-runs and cache the tables.

Usage:
    python scripts/run_v2_rerun.py --strategies a,d,c --force
    python scripts/run_v2_rerun.py --strategies c_kalman --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src import v2_rerun  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strategies",
        default=",".join(v2_rerun.STRATEGIES),
        help="comma-separated subset of " + ",".join(v2_rerun.STRATEGIES),
    )
    parser.add_argument(
        "--force", action="store_true",
        help="recompute even if output/v2_rerun/comparison.csv exists",
    )
    parser.add_argument("--capital", type=float, default=10_000_000.0)
    parser.add_argument("--min-adv", type=float, default=100.0)
    args = parser.parse_args()

    out = ROOT / "output" / "v2_rerun"
    if (out / "comparison.csv").exists() and not args.force:
        print(f"Found {out / 'comparison.csv'}; use --force to recompute.")
        return

    rank_path = ROOT / "data" / "processed" / "rank.parquet"
    if not rank_path.exists():
        raise SystemExit(
            f"Missing {rank_path}. Run notebooks/01_panel_build.ipynb first."
        )
    rank = pd.read_parquet(rank_path)
    names = tuple(n.strip() for n in args.strategies.split(",") if n.strip())
    settings = v2_rerun.RerunSettings(capital=args.capital, min_adv=args.min_adv)
    results = v2_rerun.run_all(names, rank, settings)
    path = v2_rerun.save_results(results, out)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()

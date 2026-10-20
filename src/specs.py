"""Contract specifications (point value, tick size) in Bloomberg quote units."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config

CONTRACT_SPECS_CSV = config.METADATA_DIR / "contract_specs.csv"


def load_contract_specs(path: str | Path | None = None) -> pd.DataFrame:
    """Load the per-root contract specification table.

    Args:
        path: CSV path; defaults to ``data/metadata/contract_specs.csv``.

    Returns:
        DataFrame indexed by ``root`` with ``point_value_usd`` (USD per one
        quote unit), ``tick_size`` (quote units) and ``tick_value_usd``.

    Raises:
        ValueError: If tick value is inconsistent with point value x tick size.
    """

    specs = pd.read_csv(path or CONTRACT_SPECS_CSV).set_index("root")
    implied = specs["point_value_usd"] * specs["tick_size"]
    bad = (implied - specs["tick_value_usd"]).abs() > 1e-6
    if bad.any():
        raise ValueError(f"Inconsistent tick value for: {list(specs.index[bad])}")
    return specs

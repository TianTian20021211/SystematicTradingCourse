"""Remove volatile execution timestamps from executed notebooks.

nbconvert records per-cell wall-clock metadata (``metadata.execution``). Those
timestamps change every run and create noisy git diffs even when the code and
outputs are identical. This script removes only that metadata; outputs stay.

Usage:
    python scripts/clean_notebook_metadata.py notebooks/*.ipynb
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat


def clean(path: Path) -> None:
    notebook = nbformat.read(path, as_version=4)
    changed = False
    for cell in notebook.cells:
        if cell.cell_type == "code" and "execution" in cell.metadata:
            del cell.metadata["execution"]
            changed = True
    if changed:
        nbformat.write(notebook, path)
        print(f"cleaned {path}")


def main(paths: list[str]) -> None:
    for value in paths:
        clean(Path(value))


if __name__ == "__main__":
    main(sys.argv[1:])

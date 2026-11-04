"""Compare the regenerated tables in output/tables with the published ones.

``tests/reference/`` holds the .tex tables as published. Each table that
exists in both places must match exactly (ignoring whitespace). Run after
``uv run pipeline/run_all.py``.
"""

import re
from pathlib import Path

import pytest

from ev_congestion.config import CFG

REFERENCE = Path(__file__).parent / "reference"
TABLES = sorted(p.name for p in REFERENCE.glob("*.tex")) if REFERENCE.exists() else []


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.parametrize("name", TABLES)
def test_table_matches_published(name):
    out = CFG.tables_dir / name
    if not out.exists():
        pytest.skip(f"{name} not generated yet")
    assert _norm(out.read_text()) == _norm((REFERENCE / name).read_text())

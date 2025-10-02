from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from module_3_1 import ClauseSegmenter, segment_text


@pytest.fixture
def sample_text() -> str:
    return Path("samples/sample_lease_contract.txt").read_text(encoding="utf-8")


def test_segmenter_produces_expected_hierarchy(sample_text: str) -> None:
    clauses = ClauseSegmenter().segment(sample_text)

    clause_ids = [clause.id for clause in clauses]
    assert clause_ids[0] == "PREFACE"
    assert "A1" in clause_ids
    assert "A3" in clause_ids
    assert "A3-1" in clause_ids
    item_id = "A3-2-" + "\uac00"
    assert item_id in clause_ids

    deposit_clause = next(clause for clause in clauses if clause.id == "A3-1")
    assert "lease_hint_deposit" in deposit_clause.tags
    assert "\ubcf4\uc99d\uae08" in deposit_clause.text

    rent_item = next(clause for clause in clauses if clause.id == item_id)
    assert "lease_hint_rent" in rent_item.tags
    assert "\uc5f0\uccb4" in rent_item.text

    article_six = next(clause for clause in clauses if clause.id == "A6")
    assert "cross_ref" in article_six.tags


def test_offsets_match_source_text(sample_text: str) -> None:
    clauses = segment_text(sample_text)
    for clause in clauses:
        assert clause.text == sample_text[clause.start : clause.end]
        assert clause.start <= clause.end


def test_cli_outputs_json(sample_text: str, tmp_path: Path) -> None:
    temp_file = tmp_path / "contract.txt"
    temp_file.write_text(sample_text, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "module_3_1.cli", str(temp_file), "--indent", "2"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    assert isinstance(payload, list)
    assert len(payload) >= 6
    assert payload[0]["id"] == "PREFACE"

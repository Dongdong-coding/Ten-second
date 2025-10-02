from __future__ import annotations

import json
from pathlib import Path

from module_3_4.cli import main as cli_main
from module_3_4.engine import execute

FIXTURES = Path(__file__).parent / "fixtures"

def load_fixture(name: str):
    path = FIXTURES / name
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)

def test_engine_matches_penalty_clause():
    clauses = load_fixture("norm_clauses.json")
    ruleset = load_fixture("ruleset_runtime.json")

    hits = execute(clauses, ruleset)

    assert len(hits) == 1
    hit = hits[0]
    assert hit.rule_id == "RULE-001"
    assert hit.clause_id == "C1"
    assert 0.0 < hit.strength <= 1.0
    assert "severity:WARN" in hit.notes
    assert any("numeric:" in note for note in hit.notes)

def test_engine_ignores_out_of_scope_clause():
    clauses = load_fixture("norm_clauses.json")
    ruleset = load_fixture("ruleset_runtime.json")

    hits = execute(clauses, ruleset)

    clause_ids = {hit.clause_id for hit in hits}
    assert "C2" not in clause_ids

def test_cli_end_to_end(tmp_path):
    clauses_path = FIXTURES / "norm_clauses.json"
    ruleset_path = FIXTURES / "ruleset_runtime.json"
    out_path = tmp_path / "hits.json"

    exit_code = cli_main([
        "--clauses",
        str(clauses_path),
        "--ruleset",
        str(ruleset_path),
        "--out",
        str(out_path),
        "--pretty",
    ])

    assert exit_code == 0
    with out_path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    assert isinstance(payload, list)
    assert payload[0]["rule_id"] == "RULE-001"

from __future__ import annotations

import json
from pathlib import Path

import pytest

from module_3_7.cli import main as cli_main
from module_3_7.resolver import ContextResolver


@pytest.fixture(scope="module")
def samples_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "samples"


def test_resolver_applies_context_effects(samples_dir: Path) -> None:
    resolver = ContextResolver.from_files(
        clauses_path=samples_dir / "norm_clauses.json",
        scores_path=samples_dir / "scores.json",
        hits_path=samples_dir / "hits.json",
        policy_path=samples_dir / "policy.json",
        ruleset_path=samples_dir / "ruleset_runtime.json",
    )

    payload = resolver.resolve()
    results = {item["clause_id"]: item for item in payload["results"]}

    assert set(results.keys()) == {"ANNEX-A", "C-101", "C-102", "C-103", "C-202"}

    c102 = results["C-102"]
    assert c102["contextual_risk_flag"] == "OK"
    assert [effect["type"] for effect in c102["effects"]] == ["OVERRIDE", "MITIGATE", "BOUND_BY"]
    assert c102["effects"][0]["target_clause_id"] == "C-101"
    assert c102["effects"][1]["target_clause_id"] == "C-202"

    c103 = results["C-103"]
    assert c103["contextual_risk_flag"] == "AMBIG"
    assert [effect["type"] for effect in c103["effects"]] == ["DEPEND"]

    annex = results["ANNEX-A"]
    assert annex["contextual_risk_flag"] == "AMBIG"

    summary = payload["summary"]
    assert summary["counts_by_effect"] == {
        "BOUND_BY": 1,
        "DEPEND": 2,
        "MITIGATE": 1,
        "OVERRIDE": 1,
    }
    assert summary["changed_flags"] == ["ANNEX-A", "C-102", "C-103"]
    assert summary["unchanged_flags"] == ["C-101", "C-202"]


def test_cli_writes_payload(tmp_path: Path, samples_dir: Path) -> None:
    out_path = tmp_path / "context.json"
    args = [
        "--clauses",
        str(samples_dir / "norm_clauses.json"),
        "--scores",
        str(samples_dir / "scores.json"),
        "--hits",
        str(samples_dir / "hits.json"),
        "--rules",
        str(samples_dir / "ruleset_runtime.json"),
        "--policy",
        str(samples_dir / "policy.json"),
        "--out",
        str(out_path),
    ]
    exit_code = cli_main(args)
    assert exit_code == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text("utf-8"))
    assert "results" in data and "summary" in data
    assert len(data["results"]) == 5


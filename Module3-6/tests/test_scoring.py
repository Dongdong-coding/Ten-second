from __future__ import annotations

import json
from pathlib import Path

import pytest

from module_3_6.aggregator import Aggregator
from module_3_6.cli import main as cli_main
from module_3_6.risk_scorer import score_clauses
from module_3_6.schemas import Policy, hits_from_payload, rules_from_payload

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def _load_fixture(name: str):
    with (SAMPLES / name).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _build_results():
    hits_payload = _load_fixture("hits.json")
    rules_payload = _load_fixture("ruleset_runtime.json")
    policy_payload = _load_fixture("policy.json")

    policy = Policy.from_mapping(policy_payload)
    hits = hits_from_payload(hits_payload)
    rules = rules_from_payload(rules_payload)

    computations = score_clauses(hits, rules, policy)
    aggregator = Aggregator(policy)
    return aggregator.aggregate(computations)


def test_calibration_adjusts_warn_rate():
    results, summary = _build_results()
    warn_threshold = summary["thresholds_applied"]["WARN"]
    assert 0.05 <= warn_threshold <= 0.20
    assert summary["warn_rate"] == pytest.approx(0.90, abs=0.15)


def test_demotes_non_critical_highs():
    results, _ = _build_results()
    demoted = next(item for item in results if item.clause_id == "C-DEMOTE")
    assert demoted.risk_flag == "WARN"
    assert any("demoted" in reason for reason in demoted.reasons)

    critical = next(item for item in results if item.clause_id == "C-CRITICAL")
    assert critical.risk_flag == "HIGH"


def test_ambiguous_cases_excluded_from_warn_rate():
    results, summary = _build_results()

    ambig = next(item for item in results if item.clause_id == "C-AMBIG")
    assert ambig.risk_flag == "AMBIG"

    warn = sum(1 for item in results if item.risk_flag == "WARN")
    high = sum(1 for item in results if item.risk_flag == "HIGH")
    ok = sum(1 for item in results if item.risk_flag == "OK")
    denom = warn + high + ok
    expected_rate = warn / denom if denom else 0.0
    assert summary["warn_rate"] == pytest.approx(round(expected_rate, 4), rel=1e-6, abs=1e-6)

    suppressed = next(item for item in results if item.clause_id == "C-SUPPRESS")
    assert "RULE-NEG" in suppressed.suppressed_rules
    negative_scores = [score for score in suppressed.per_hit_scores if score.adjusted < 0]
    assert negative_scores, "Expected at least one negative per-hit score for suppressed rule"


def test_cli_emits_scores(tmp_path):
    hits_path = SAMPLES / "hits.json"
    rules_path = SAMPLES / "ruleset_runtime.json"
    policy_path = SAMPLES / "policy.json"
    out_path = tmp_path / "scores.json"

    exit_code = cli_main(
        [
            "--hits",
            str(hits_path),
            "--rules",
            str(rules_path),
            "--policy",
            str(policy_path),
            "--out",
            str(out_path),
            "--pretty",
        ]
    )
    assert exit_code == 0

    with out_path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)

    assert "results" in payload and "summary" in payload
    critical = next(item for item in payload["results"] if item["clause_id"] == "C-CRITICAL")
    assert critical["risk_flag"] == "HIGH"
    demoted = next(item for item in payload["results"] if item["clause_id"] == "C-DEMOTE")
    assert demoted["risk_flag"] == "WARN"

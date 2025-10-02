from __future__ import annotations

from pathlib import Path
import sys

import json
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from module_3_8.policy import load_policy
from module_3_8.reporter import EvaluationInputs, build_report
from module_3_8.schemas import (
    load_golden,
    load_hits,
    load_ruleset,
    load_run_stats,
    load_scores,
)


@pytest.fixture(scope="module")
def sample_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "samples"


def test_build_report_produces_expected_metrics(sample_dir: Path) -> None:
    policy = load_policy(sample_dir / "policy.json")
    inputs = EvaluationInputs(
        scores=load_scores(sample_dir / "scores.json"),
        hits=load_hits(sample_dir / "hits.json"),
        golden=load_golden(sample_dir / "golden_labels.json"),
        ruleset=load_ruleset(sample_dir / "ruleset_runtime.json"),
        run_stats=load_run_stats(sample_dir / "run_stats.json"),
    )

    bundle = build_report(inputs, policy)

    alignment = bundle.report_json["golden_alignment"]
    assert pytest.approx(alignment["pass_rate"], rel=1e-3) == 0.75
    assert alignment["failures"] == 1

    rule_metrics = bundle.report_json["rule_metrics"]["per_rule"]
    r3 = next(item for item in rule_metrics if item["rule_id"] == "R3")
    assert r3["fn"] == 1
    assert r3["tp"] == 1

    gate = bundle.gate_decision
    assert gate["allowed"] is False
    assert gate["golden_pass_rate"] == pytest.approx(0.75, rel=1e-3)

    markdown = bundle.report_markdown
    assert "Golden match rate" in markdown
    assert "Gate decision" in markdown


def test_cli_writes_outputs(tmp_path: Path, sample_dir: Path) -> None:
    from module_3_8.cli import main

    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"
    out_gate = tmp_path / "gate.json"

    argv = [
        "--scores",
        str(sample_dir / "scores.json"),
        "--hits",
        str(sample_dir / "hits.json"),
        "--rules",
        str(sample_dir / "ruleset_runtime.json"),
        "--golden",
        str(sample_dir / "golden_labels.json"),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
        "--gate",
        str(out_gate),
        "--policy",
        str(sample_dir / "policy.json"),
        "--run-stats",
        str(sample_dir / "run_stats.json"),
    ]

    exit_code = main(argv)
    assert exit_code == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "golden_alignment" in payload
    assert out_md.read_text(encoding="utf-8").startswith("# Evaluation Summary")
    assert json.loads(out_gate.read_text(encoding="utf-8"))["allowed"] is False

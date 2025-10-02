from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MatchingPolicy:
    strict_match: bool = True
    allow_conservative: bool = False
    treat_empty_expected_rules_as_negative: bool = False


@dataclass(frozen=True)
class GatePolicy:
    min_golden_pass_rate: float = 0.80
    min_rule_precision: float = 0.60
    min_rule_recall: float = 0.60
    enforce_rule_floor_for_critical: bool = True


@dataclass(frozen=True)
class ReportPolicy:
    top_n_problem_rules: int = 10
    show_examples_per_rule: int = 5


@dataclass(frozen=True)
class EvaluationPolicy:
    matching: MatchingPolicy
    gates: GatePolicy
    report: ReportPolicy

    @staticmethod
    def default() -> "EvaluationPolicy":
        return EvaluationPolicy(
            matching=MatchingPolicy(),
            gates=GatePolicy(),
            report=ReportPolicy(),
        )


def load_policy(path: Optional[Path]) -> EvaluationPolicy:
    if path is None:
        return EvaluationPolicy.default()

    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    if not isinstance(raw, dict):
        raise ValueError("policy payload must be a JSON object")

    matching_raw = raw.get("matching", {}) or {}
    gates_raw = raw.get("gates", {}) or {}
    report_raw = raw.get("report", {}) or {}

    matching = MatchingPolicy(
        strict_match=bool(matching_raw.get("strict_match", True)),
        allow_conservative=bool(matching_raw.get("allow_conservative", False)),
        treat_empty_expected_rules_as_negative=bool(
            matching_raw.get("treat_empty_expected_rules_as_negative", False)
        ),
    )

    gates = GatePolicy(
        min_golden_pass_rate=float(gates_raw.get("min_golden_pass_rate", 0.80)),
        min_rule_precision=float(gates_raw.get("min_rule_precision", 0.60)),
        min_rule_recall=float(gates_raw.get("min_rule_recall", 0.60)),
        enforce_rule_floor_for_critical=bool(
            gates_raw.get("enforce_rule_floor_for_critical", True)
        ),
    )

    report = ReportPolicy(
        top_n_problem_rules=int(report_raw.get("top_n_problem_rules", 10)),
        show_examples_per_rule=int(report_raw.get("show_examples_per_rule", 5)),
    )

    return EvaluationPolicy(matching=matching, gates=gates, report=report)

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .policy import EvaluationPolicy
from .schemas import (
    GoldenClause,
    HitRecord,
    RuleDefinition,
    RunStats,
    ScoreRecord,
)


RISK_SEVERITY = {"OK": 0, "WARN": 1, "HIGH": 2}
AMBIG_FLAGS = {"AMBIG", "NULL"}


@dataclass
class EvaluationInputs:
    scores: Sequence[ScoreRecord]
    hits: Sequence[HitRecord]
    golden: Sequence[GoldenClause]
    ruleset: Dict[str, RuleDefinition]
    run_stats: Optional[RunStats] = None


@dataclass
class RuleMetrics:
    rule_id: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    critical: bool
    category: Optional[str]
    subcategory: Optional[str]
    variant: Optional[str]
    fp_examples: List[str]
    fn_examples: List[str]


@dataclass
class ReportBundle:
    report_json: Dict[str, object]
    report_markdown: str
    gate_decision: Dict[str, object]


class EvaluationError(Exception):
    """Raised when inputs are invalid for evaluation."""


def build_report(inputs: EvaluationInputs, policy: EvaluationPolicy) -> ReportBundle:
    _validate_inputs(inputs)

    scores_by_clause = {score.clause_id: score for score in inputs.scores}
    golden_by_clause = {case.clause_id: case for case in inputs.golden}

    alignment = _evaluate_alignment(golden_by_clause, scores_by_clause, policy)

    hits_by_clause = _group_hits_by_clause(inputs.hits)
    rule_metrics = _compute_rule_metrics(
        golden_by_clause,
        hits_by_clause,
        policy,
        inputs.ruleset,
    )

    category_metrics = _aggregate_categories(rule_metrics)
    risk_distribution = _summarize_risk(scores_by_clause.values())

    top_rules = _select_top_problem_rules(rule_metrics, policy.report.top_n_problem_rules)

    report_json = {
        "golden_alignment": alignment,
        "risk_distribution": risk_distribution,
        "rule_metrics": {
            "summary": _summarize_rule_metrics(rule_metrics),
            "per_rule": [metric.__dict__ for metric in rule_metrics],
        },
        "category_metrics": category_metrics,
        "top_problem_rules": [metric.rule_id for metric in top_rules],
    }

    if inputs.run_stats:
        report_json["run_stats"] = {
            "timings": inputs.run_stats.timings,
            "memory_mb": inputs.run_stats.memory_mb,
            "extras": inputs.run_stats.extras,
        }

    gate_decision = _make_gate_decision(rule_metrics, alignment, policy)
    report_json["gate_decision"] = gate_decision

    report_markdown = _render_markdown_summary(
        alignment=alignment,
        top_rules=top_rules,
        category_metrics=category_metrics,
        risk_distribution=risk_distribution,
        gate_decision=gate_decision,
        policy=policy,
    )

    return ReportBundle(
        report_json=report_json,
        report_markdown=report_markdown,
        gate_decision=gate_decision,
    )


def _validate_inputs(inputs: EvaluationInputs) -> None:
    clause_ids = [score.clause_id for score in inputs.scores]
    if len(clause_ids) != len(set(clause_ids)):
        raise EvaluationError("scores payload contains duplicate clause_id values")

    golden_ids = [case.clause_id for case in inputs.golden]
    if len(golden_ids) != len(set(golden_ids)):
        raise EvaluationError("golden labels payload contains duplicate clause_id values")

    missing = set(golden_ids) - set(clause_ids)
    if missing:
        raise EvaluationError(
            f"scores payload missing clause_ids present in golden labels: {sorted(missing)}"
        )


def _evaluate_alignment(
    golden: Dict[str, GoldenClause],
    scores: Dict[str, ScoreRecord],
    policy: EvaluationPolicy,
) -> Dict[str, object]:
    total = len(golden)
    passes = 0
    failures: List[Dict[str, object]] = []
    ambiguous = 0
    flag_counts: Dict[str, int] = {}

    for clause_id, case in golden.items():
        score = scores.get(clause_id)
        actual_flag = score.risk_flag if score else None
        flag_counts[actual_flag or "MISSING"] = flag_counts.get(actual_flag or "MISSING", 0) + 1
        if actual_flag in AMBIG_FLAGS:
            ambiguous += 1

        if _flag_matches(case.expected_flag, actual_flag, policy):
            passes += 1
        else:
            failures.append(
                {
                    "clause_id": clause_id,
                    "expected_flag": case.expected_flag,
                    "actual_flag": actual_flag,
                    "confidence": score.confidence if score else None,
                }
            )

    rate = passes / total if total else 0.0
    return {
        "total": total,
        "passes": passes,
        "failures": len(failures),
        "pass_rate": round(rate, 4),
        "ambiguous_predictions": ambiguous,
        "flag_counts": flag_counts,
        "failure_examples": failures[: policy.report.show_examples_per_rule],
        "policy": {
            "strict_match": policy.matching.strict_match,
            "allow_conservative": policy.matching.allow_conservative,
        },
    }


def _flag_matches(expected: str, actual: Optional[str], policy: EvaluationPolicy) -> bool:
    if actual is None:
        return False
    if actual in AMBIG_FLAGS:
        return False
    if policy.matching.strict_match:
        return actual == expected
    if actual == expected:
        return True
    if policy.matching.allow_conservative:
        expected_rank = RISK_SEVERITY.get(expected, 0)
        actual_rank = RISK_SEVERITY.get(actual, 0)
        return actual_rank >= expected_rank
    return False


def _group_hits_by_clause(hits: Sequence[HitRecord]) -> Dict[str, Set[str]]:
    grouped: Dict[str, Set[str]] = {}
    for hit in hits:
        grouped.setdefault(hit.clause_id, set()).add(hit.rule_id)
    return grouped


def _compute_rule_metrics(
    golden: Dict[str, GoldenClause],
    hits_by_clause: Dict[str, Set[str]],
    policy: EvaluationPolicy,
    ruleset: Dict[str, RuleDefinition],
) -> List[RuleMetrics]:
    rule_counts: Dict[str, Dict[str, object]] = {}

    for clause_id, case in golden.items():
        expected_rules = set(case.expected_rules)
        actual_rules = hits_by_clause.get(clause_id, set())

        for rule_id in expected_rules:
            counts = rule_counts.setdefault(rule_id, {
                "tp": 0,
                "fp": 0,
                "fn": 0,
                "fp_examples": [],
                "fn_examples": [],
            })
            if rule_id in actual_rules:
                counts["tp"] += 1
            else:
                counts["fn"] += 1
                if len(counts["fn_examples"]) < 5:
                    counts["fn_examples"].append(clause_id)

        for rule_id in actual_rules:
            if rule_id in expected_rules:
                continue
            if not expected_rules and not policy.matching.treat_empty_expected_rules_as_negative:
                continue
            counts = rule_counts.setdefault(rule_id, {
                "tp": 0,
                "fp": 0,
                "fn": 0,
                "fp_examples": [],
                "fn_examples": [],
            })
            counts["fp"] += 1
            if len(counts["fp_examples"]) < 5:
                counts["fp_examples"].append(clause_id)

    metrics: List[RuleMetrics] = []
    for rule_id, counts in sorted(rule_counts.items()):
        definition = ruleset.get(rule_id, RuleDefinition(rule_id, None, None, None, False))
        tp = int(counts["tp"])
        fp = int(counts["fp"])
        fn = int(counts["fn"])
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        metrics.append(
            RuleMetrics(
                rule_id=rule_id,
                tp=tp,
                fp=fp,
                fn=fn,
                precision=round(precision, 4),
                recall=round(recall, 4),
                f1=round(f1, 4),
                critical=definition.critical,
                category=definition.category,
                subcategory=definition.subcategory,
                variant=definition.variant,
                fp_examples=list(counts["fp_examples"]),
                fn_examples=list(counts["fn_examples"]),
            )
        )

    return metrics


def _aggregate_categories(metrics: Sequence[RuleMetrics]) -> List[Dict[str, object]]:
    buckets: Dict[Tuple[Optional[str], Optional[str]], Dict[str, float]] = {}
    for metric in metrics:
        key = (metric.category, metric.subcategory)
        bucket = buckets.setdefault(
            key,
            {"tp": 0, "fp": 0, "fn": 0, "rules": []},
        )
        bucket["tp"] += metric.tp
        bucket["fp"] += metric.fp
        bucket["fn"] += metric.fn
        bucket["rules"].append(metric.rule_id)

    category_metrics: List[Dict[str, object]] = []
    for (category, subcategory), counts in sorted(buckets.items(), key=lambda item: (item[0][0] or "", item[0][1] or "")):
        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        category_metrics.append(
            {
                "category": category,
                "subcategory": subcategory,
                "tp": int(tp),
                "fp": int(fp),
                "fn": int(fn),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "rules": sorted(counts["rules"]),
            }
        )
    return category_metrics


def _summarize_risk(scores: Iterable[ScoreRecord]) -> Dict[str, object]:
    flag_counts: Dict[str, int] = {}
    confidences: List[float] = []
    for score in scores:
        flag_counts[score.risk_flag] = flag_counts.get(score.risk_flag, 0) + 1
        confidences.append(score.confidence)

    if confidences:
        confidences_sorted = sorted(confidences)
        mid = len(confidences_sorted) // 2
        if len(confidences_sorted) % 2:
            median = confidences_sorted[mid]
        else:
            median = (confidences_sorted[mid - 1] + confidences_sorted[mid]) / 2
        p90_index = max(int(len(confidences_sorted) * 0.9) - 1, 0)
        p90 = confidences_sorted[p90_index]
        stats = {
            "average": round(mean(confidences_sorted), 4),
            "median": round(median, 4),
            "p90": round(p90, 4),
            "min": round(confidences_sorted[0], 4),
            "max": round(confidences_sorted[-1], 4),
        }
    else:
        stats = {"average": 0.0, "median": 0.0, "p90": 0.0, "min": 0.0, "max": 0.0}

    return {
        "flag_counts": flag_counts,
        "confidence_stats": stats,
    }


def _select_top_problem_rules(
    metrics: Sequence[RuleMetrics],
    limit: int,
) -> List[RuleMetrics]:
    def score(metric: RuleMetrics) -> Tuple[float, float, str]:
        return (
            -(metric.fn + metric.fp),
            metric.f1,
            metric.rule_id,
        )

    sorted_metrics = sorted(metrics, key=score)
    return sorted_metrics[:limit]


def _summarize_rule_metrics(metrics: Sequence[RuleMetrics]) -> Dict[str, object]:
    tp = sum(metric.tp for metric in metrics)
    fp = sum(metric.fp for metric in metrics)
    fn = sum(metric.fn for metric in metrics)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _make_gate_decision(
    metrics: Sequence[RuleMetrics],
    alignment: Dict[str, object],
    policy: EvaluationPolicy,
) -> Dict[str, object]:
    pass_rate = float(alignment.get("pass_rate", 0.0))
    allowed = True
    failing_rules: List[Dict[str, object]] = []
    notes: List[str] = []

    if pass_rate < policy.gates.min_golden_pass_rate:
        allowed = False
        notes.append(
            f"golden pass rate {pass_rate:.2f} below minimum {policy.gates.min_golden_pass_rate:.2f}"
        )

    for metric in metrics:
        precision_ok = metric.precision >= policy.gates.min_rule_precision
        recall_ok = metric.recall >= policy.gates.min_rule_recall
        if precision_ok and recall_ok:
            continue
        reason_parts = []
        if not precision_ok:
            reason_parts.append(
                f"precision {metric.precision:.2f} < {policy.gates.min_rule_precision:.2f}"
            )
        if not recall_ok:
            reason_parts.append(
                f"recall {metric.recall:.2f} < {policy.gates.min_rule_recall:.2f}"
            )
        is_critical = metric.critical and policy.gates.enforce_rule_floor_for_critical
        if is_critical or reason_parts:
            failing_rules.append(
                {
                    "rule_id": metric.rule_id,
                    "precision": metric.precision,
                    "recall": metric.recall,
                    "critical": metric.critical,
                    "reason": "; ".join(reason_parts) or "below configured floor",
                }
            )
            if is_critical:
                allowed = False
                notes.append(
                    f"critical rule {metric.rule_id} failed threshold: {'; '.join(reason_parts)}"
                )

    decision = {
        "allowed": allowed,
        "golden_pass_rate": pass_rate,
        "thresholds": {
            "min_pass": policy.gates.min_golden_pass_rate,
            "min_rule_precision": policy.gates.min_rule_precision,
            "min_rule_recall": policy.gates.min_rule_recall,
            "strict_match": policy.matching.strict_match,
            "allow_conservative": policy.matching.allow_conservative,
        },
        "failing_rules": failing_rules,
        "notes": notes,
    }
    return decision


def _render_markdown_summary(
    alignment: Dict[str, object],
    top_rules: Sequence[RuleMetrics],
    category_metrics: Sequence[Dict[str, object]],
    risk_distribution: Dict[str, object],
    gate_decision: Dict[str, object],
    policy: EvaluationPolicy,
) -> str:
    lines: List[str] = []
    lines.append("# Evaluation Summary")
    lines.append("")
    lines.append(
        f"- Golden match rate: {alignment.get('passes', 0)}/{alignment.get('total', 0)}"
        f" ({alignment.get('pass_rate', 0.0):.2%})"
    )
    lines.append(
        f"- Gate decision: {'allowed' if gate_decision.get('allowed') else 'blocked'}"
    )
    lines.append(
        "- Policy: strict_match="
        f"{policy.matching.strict_match}, allow_conservative={policy.matching.allow_conservative}"
    )
    lines.append("")

    lines.append("## Top Problem Rules")
    if not top_rules:
        lines.append("- All evaluated rules met the configured thresholds.")
    else:
        for metric in top_rules:
            lines.append(
                "- "
                f"{metric.rule_id}: precision {metric.precision:.2f}, recall {metric.recall:.2f}, "
                f"FN {metric.fn}, FP {metric.fp}"
            )
    lines.append("")

    lines.append("## Category View")
    if not category_metrics:
        lines.append("- No category metadata supplied.")
    else:
        for entry in category_metrics:
            category = entry.get("category") or "UNCATEGORIZED"
            subcategory = entry.get("subcategory") or "-"
            lines.append(
                f"- {category}/{subcategory}: precision {entry['precision']:.2f}, "
                f"recall {entry['recall']:.2f} (rules {', '.join(entry['rules'])})"
            )
    lines.append("")

    lines.append("## Risk Distribution")
    flag_counts = risk_distribution.get("flag_counts", {})
    if flag_counts:
        lines.append("- Flags: " + ", ".join(f"{flag}={count}" for flag, count in flag_counts.items()))
    else:
        lines.append("- Flags: none")
    confidence = risk_distribution.get("confidence_stats", {})
    lines.append(
        "- Confidence: mean {average:.2f}, median {median:.2f}, p90 {p90:.2f}".format(**{
            "average": confidence.get("average", 0.0),
            "median": confidence.get("median", 0.0),
            "p90": confidence.get("p90", 0.0),
        })
    )
    lines.append("")

    lines.append("## Gate Rationale")
    notes = gate_decision.get("notes", [])
    if notes:
        for note in notes:
            lines.append(f"- {note}")
    else:
        lines.append("- All thresholds satisfied.")

    return "\n".join(lines)

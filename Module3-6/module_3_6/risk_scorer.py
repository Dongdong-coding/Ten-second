from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .schemas import PerHitScore, Policy, Rule, Hit

_VARIANT_FACTORS: Dict[str, float] = {
    "lex": 1.0,
    "syntax": 1.05,
    "num": 1.08,
    "table": 1.10,
}


@dataclass
class ClauseComputation:
    clause_id: str
    confidence: float
    per_hit_scores: List[PerHitScore]
    adopted_rules: List[str]
    suppressed_rules: List[str]
    reasons: List[str]
    metadata: Dict[str, object]


def score_clauses(
    hits: Iterable[Hit],
    rules: Dict[str, Rule],
    policy: Policy,
) -> List[ClauseComputation]:
    grouped: Dict[str, List[Hit]] = defaultdict(list)
    for hit in hits:
        grouped[hit.clause_id].append(hit)

    computations: List[ClauseComputation] = []
    for clause_id, clause_hits in grouped.items():
        per_hit_scores: List[PerHitScore] = []
        adopted_rules: List[str] = []
        suppressed_rules: List[str] = []
        reasons: List[str] = []
        cumulative = 0.0
        flags: Dict[str, bool] = {}
        priorities: List[int] = []
        severities: List[str] = []

        for hit in clause_hits:
            rule = rules.get(hit.rule_id, Rule(rule_id=hit.rule_id))
            variant_multiplier = _VARIANT_FACTORS.get(hit.match_type, 1.0)
            scope_multiplier = _scope_multiplier(rule)
            raw_score = rule.weight * hit.strength * variant_multiplier * scope_multiplier

            penalties_applied = _collect_penalties(hit, policy.penalties)
            total_penalty = sum(penalties_applied.values())
            adjusted_score = raw_score - total_penalty
            cumulative += adjusted_score

            per_hit_scores.append(
                PerHitScore(
                    rule_id=hit.rule_id,
                    raw=round(raw_score, 6),
                    penalties_applied=penalties_applied,
                    match_type=hit.match_type,
                    strength=hit.strength,
                    weight=rule.weight,
                    adjusted=round(adjusted_score, 6),
                )
            )

            if adjusted_score > 0:
                adopted_rules.append(hit.rule_id)
            else:
                suppressed_rules.append(hit.rule_id)

            reasons.append(
                f"rule={hit.rule_id} ({hit.match_type}) => {adjusted_score:.3f}"
            )

            for flag in rule.flags:
                flags[flag] = True
            for note in hit.notes:
                note_key = note.split(":", 1)[-1]
                if note_key in policy.penalties:
                    flags[note_key] = True

            priorities.append(rule.priority)
            severities.append(rule.severity)

        confidence = max(0.0, min(1.0, cumulative))
        metadata = {
            "flags": flags,
            "max_priority": max(priorities) if priorities else 0,
            "severities": severities,
            "scope_specificity": _best_scope_specificity(
                rules, adopted_rules or suppressed_rules
            ),
        }

        computations.append(
            ClauseComputation(
                clause_id=clause_id,
                confidence=confidence,
                per_hit_scores=per_hit_scores,
                adopted_rules=adopted_rules,
                suppressed_rules=suppressed_rules,
                reasons=reasons,
                metadata=metadata,
            )
        )

    return computations


def _scope_multiplier(rule: Rule) -> float:
    scope = rule.scope or {}
    multiplier = 1.0
    if scope.get("category"):
        multiplier += 0.05
    if scope.get("subcategory"):
        multiplier += 0.05
    return multiplier


def _collect_penalties(hit: Hit, penalties: Dict[str, float]) -> Dict[str, float]:
    applied: Dict[str, float] = {}
    note_tokens = set()
    for note in hit.notes:
        lower = note.lower()
        note_tokens.add(lower)
        note_tokens.add(lower.split(":", 1)[-1])
    for name, penalty in penalties.items():
        key = name.lower()
        if key in note_tokens:
            applied[name] = penalty
        elif hit.flags and key in hit.flags and hit.flags.get(key):
            applied[name] = penalty
    return applied


def _best_scope_specificity(
    rules: Dict[str, Rule],
    rule_ids: Iterable[str],
) -> int:
    best = 0
    for rule_id in rule_ids:
        rule = rules.get(rule_id)
        if not rule:
            continue
        specificity = 0
        scope = rule.scope or {}
        if scope.get("category"):
            specificity += 1
        if scope.get("subcategory"):
            specificity += 1
        best = max(best, specificity)
    return best


__all__ = ["ClauseComputation", "score_clauses"]

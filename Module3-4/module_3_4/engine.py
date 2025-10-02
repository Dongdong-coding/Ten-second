from __future__ import annotations

"""Orchestrator for the Module 3-4 execution engine."""

from collections import defaultdict
from typing import List, Mapping, MutableMapping, Sequence, Tuple, Union

from .fastpath import FastPathMatcher
from .numeric_table import NumericTableEvaluator
from .schemas import Hit, MatchEvidence, NormClause, RulesetRuntime, RuntimeRule
from .syntax import SyntaxMatcher
from . import utils

NormClauseInput = Union[NormClause, Mapping[str, object]]
RulesetInput = Union[RulesetRuntime, Mapping[str, object]]


def execute(clauses: Sequence[NormClauseInput], ruleset: RulesetInput) -> List[Hit]:
    runtime = ruleset if isinstance(ruleset, RulesetRuntime) else RulesetRuntime.from_dict(ruleset)
    normalized_clauses = _coerce_clauses(clauses)
    fastpath = FastPathMatcher(runtime)
    syntax = SyntaxMatcher(runtime)
    numeric = NumericTableEvaluator(runtime)

    rule_map = runtime.rule_by_id()
    rule_priorities = {rule.rule_id: rule.priority for rule in runtime.rules}
    evidence_map: MutableMapping[Tuple[str, str], List[MatchEvidence]] = defaultdict(list)

    for clause in normalized_clauses:
        for rule in runtime.rules:
            if not rule.is_active():
                continue
            if not rule.applies_to(clause):
                continue
            _run_matchers(clause, rule, fastpath, syntax, numeric, evidence_map)

    hits: List[Hit] = []
    for (rule_id, clause_id), evidences in evidence_map.items():
        rule = rule_map.get(rule_id)
        if not rule:
            continue
        hit = _consolidate(clause_id, rule, evidences)
        if hit:
            hits.append(hit)

    hits.sort(
        key=lambda h: (-rule_priorities.get(h.rule_id, 0), -h.strength, h.rule_id, h.clause_id),
    )
    return hits

def _run_matchers(
    clause: NormClause,
    rule: RuntimeRule,
    fastpath: FastPathMatcher,
    syntax: SyntaxMatcher,
    numeric: NumericTableEvaluator,
    evidence_map: MutableMapping[Tuple[str, str], List[MatchEvidence]],
) -> None:
    matchers = [fastpath.match, syntax.match, numeric.match]
    for matcher in matchers:
        try:
            evidences = matcher(clause, rule)
        except Exception as error:  # Defensive: do not block entire engine on one failure
            evidences = []
        for evidence in evidences:
            evidence_map[(evidence.rule_id, evidence.clause_id)].append(evidence)

def _coerce_clauses(clauses: Sequence[NormClauseInput]) -> List[NormClause]:
    normalized: List[NormClause] = []
    for clause in clauses:
        if isinstance(clause, NormClause):
            normalized.append(clause)
        else:
            normalized.append(NormClause.from_dict(clause))
    return normalized

def _find_rule(runtime: RulesetRuntime, rule_id: str) -> RuntimeRule | None:
    for rule in runtime.rules:
        if rule.rule_id == rule_id:
            return rule
    return None

def _rule_priority(runtime: RulesetRuntime, rule_id: str) -> int:
    rule = _find_rule(runtime, rule_id)
    return rule.priority if rule else 0

def _consolidate(clause_id: str, rule: RuntimeRule, evidences: Sequence[MatchEvidence]) -> Hit | None:
    if not evidences:
        return None
    total_strength = 0.0
    all_spans: List[Tuple[int, int]] = []
    notes: List[str] = []
    best_snippet = ""
    best_strength = -1.0
    match_types = set()
    for evidence in evidences:
        total_strength += evidence.strength * rule.weight
        all_spans.extend(evidence.spans)
        notes.extend(evidence.notes)
        match_types.add(evidence.match_type)
        if evidence.strength > best_strength:
            best_strength = evidence.strength
            best_snippet = evidence.evidence_snippet
    if not best_snippet and evidences:
        best_snippet = evidences[0].evidence_snippet
    consolidated_spans = _merge_spans(all_spans)
    strength = utils.clamp(total_strength, 0.0, 1.0)
    match_type = "composite" if len(match_types) > 1 else next(iter(match_types))
    notes.extend([f"severity:{rule.severity}", f"priority:{rule.priority}"])
    unique_notes = []
    seen = set()
    for note in notes:
        if note and note not in seen:
            seen.add(note)
            unique_notes.append(note)
    return Hit(
        rule_id=rule.rule_id,
        clause_id=clause_id,
        match_type=match_type,
        strength=strength,
        spans=tuple(consolidated_spans),
        evidence_snippet=best_snippet,
        notes=tuple(unique_notes),
    )

def _merge_spans(spans: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not spans:
        return []
    sorted_spans = sorted(spans, key=lambda span: span[0])
    merged: List[Tuple[int, int]] = []
    current_start, current_end = sorted_spans[0]
    for start, end in sorted_spans[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = start, end
    merged.append((current_start, current_end))
    return merged

__all__ = ["execute"]


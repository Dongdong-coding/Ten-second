from __future__ import annotations

"""Syntax and proximity based matcher executed after the fast-path scan."""

import re
from typing import Dict, List, Mapping, Sequence, Tuple

from . import utils
from .schemas import MatchEvidence, NormClause, RuntimeRule, RulesetRuntime


def _compile_patterns(values: object) -> List[re.Pattern[str]]:
    compiled: List[re.Pattern[str]] = []
    if not values:
        return compiled
    if isinstance(values, str):
        values = [values]
    if isinstance(values, dict):
        values = values.values()
    for value in values:  # type: ignore[assignment]
        if isinstance(value, str):
            pattern = value.strip()
            if pattern:
                compiled.append(re.compile(pattern, re.IGNORECASE))
        elif isinstance(value, dict):
            pattern = str(value.get("pattern", "")).strip()
            if not pattern:
                continue
            flags = str(value.get("flags", "i"))
            flag_value = re.IGNORECASE if "i" in flags.lower() else 0
            compiled.append(re.compile(pattern, flag_value))
        elif isinstance(value, (list, tuple, set)):
            compiled.extend(_compile_patterns(list(value)))
    return compiled


def _merge_spans(spans: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda item: item[0])
    merged: List[Tuple[int, int]] = []
    cur_start, cur_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


class SyntaxMatcher:
    def __init__(self, ruleset: RulesetRuntime) -> None:
        self._patterns_by_rule: Dict[str, List[re.Pattern[str]]] = {}
        self._window = int(ruleset.proximity.get("window", 40) or 40)
        self._negations = [pattern.lower() for pattern in ruleset.negation_terms]
        self._exceptions = [pattern.lower() for pattern in ruleset.exception_cues]
        self._hydrate(ruleset)

    def _hydrate(self, ruleset: RulesetRuntime) -> None:
        for rule in ruleset.rules:
            matchers = rule.matchers or {}
            if not isinstance(matchers, Mapping):
                matchers = {}
            patterns: List[re.Pattern[str]] = []
            patterns.extend(_compile_patterns(ruleset.syntax_patterns.get(rule.rule_id)))
            patterns.extend(_compile_patterns(matchers.get("syntax")))
            patterns.extend(_compile_patterns(matchers.get("regex")))
            patterns.extend(_compile_patterns(matchers.get("syntax_patterns")))
            if patterns:
                self._patterns_by_rule[rule.rule_id] = patterns

    def match(self, clause: NormClause, rule: RuntimeRule) -> List[MatchEvidence]:
        patterns = self._patterns_by_rule.get(rule.rule_id)
        if not patterns:
            return []
        text = clause.text or clause.normalized_text
        if not text:
            return []
        spans: List[Tuple[int, int]] = []
        notes: List[str] = []
        lowered = text.lower()
        for negation in self._negations:
            if negation and negation in lowered:
                notes.append(f"negation:{negation}")
        for pattern in patterns:
            for match in pattern.finditer(text):
                spans.append(match.span())
        if not spans:
            return []
        spans = _merge_spans(spans)
        snippet = utils.gather_snippet(text, spans, window=self._window)
        evidence = MatchEvidence(
            rule_id=rule.rule_id,
            clause_id=clause.id,
            match_type="syntax",
            strength=utils.clamp(0.4 + 0.1 * len(spans), 0.4, 0.8),
            spans=spans,
            evidence_snippet=snippet,
            notes=notes,
        )
        return [evidence.clamp_strength()]


__all__ = ["SyntaxMatcher"]
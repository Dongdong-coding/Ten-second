from __future__ import annotations

"""Fast-path lexical matcher using precompiled lexicon cues."""

import re
from typing import Dict, Iterable, List, Mapping, Sequence

from . import utils
from .schemas import MatchEvidence, NormClause, RuntimeRule, RulesetRuntime


def _ensure_iterable(value: object) -> Iterable[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        phrases: List[str] = []
        for item in value.values():
            phrases.extend(_ensure_iterable(item))
        return phrases
    if isinstance(value, Sequence):
        phrases: List[str] = []
        for item in value:
            phrases.extend(_ensure_iterable(item))
        return phrases
    return []


class FastPathMatcher:
    """Runs lightweight lexical scans against normalized clause text."""

    def __init__(self, ruleset: RulesetRuntime) -> None:
        self._patterns_by_rule: Dict[str, List[re.Pattern[str]]] = {}
        self._hydrate(ruleset)

    def _hydrate(self, ruleset: RulesetRuntime) -> None:
        for rule in ruleset.rules:
            phrases: List[str] = []
            phrases.extend(_ensure_iterable(ruleset.lexicons.get(rule.rule_id)))
            matchers = rule.matchers or {}
            if not isinstance(matchers, Mapping):
                matchers = {}
            phrases.extend(_ensure_iterable(matchers.get("lexicon")))
            phrases.extend(_ensure_iterable(matchers.get("lexicon_phrases")))
            if not phrases:
                continue
            unique_phrases: List[str] = []
            seen = set()
            for phrase in phrases:
                key = utils.safe_lower(phrase)
                if not key or key in seen:
                    continue
                seen.add(key)
                unique_phrases.append(phrase)
            if not unique_phrases:
                continue
            self._patterns_by_rule[rule.rule_id] = [
                re.compile(re.escape(phrase), re.IGNORECASE) for phrase in unique_phrases
            ]

    def match(self, clause: NormClause, rule: RuntimeRule) -> List[MatchEvidence]:
        patterns = self._patterns_by_rule.get(rule.rule_id)
        if not patterns:
            return []
        haystack = clause.normalized_text or clause.text
        if not haystack:
            return []
        spans: List[tuple[int, int]] = []
        notes: List[str] = []
        for pattern in patterns:
            for match in pattern.finditer(haystack):
                spans.append((match.start(), match.end()))
                notes.append(f"lex:{pattern.pattern}")
        if not spans:
            return []
        strength = utils.clamp(0.2 + 0.1 * len(spans), 0.2, 0.6)
        snippet = utils.gather_snippet(clause.text or haystack, spans)
        evidence = MatchEvidence(
            rule_id=rule.rule_id,
            clause_id=clause.id,
            match_type="lex",
            strength=strength,
            spans=spans,
            evidence_snippet=snippet,
            notes=notes,
        )
        return [evidence.clamp_strength()]


__all__ = ["FastPathMatcher"]
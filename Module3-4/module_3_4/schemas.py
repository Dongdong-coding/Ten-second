from __future__ import annotations

"""Dataclasses and helpers describing Module 3-4 runtime inputs and outputs."""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


def _to_tuple(sequence: Optional[Iterable[Any]]) -> Tuple[Any, ...]:
    if not sequence:
        return tuple()
    if isinstance(sequence, tuple):
        return sequence
    return tuple(sequence)


def _legacy_matchers_to_dict(matchers: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    lexicon: List[str] = []
    regex: List[Dict[str, str]] = []
    negations: List[str] = []
    proximity: Dict[str, int] = {}
    for matcher in matchers:
        m_type = str(matcher.get("type", "")).lower()
        pattern = str(matcher.get("pattern", "")).strip()
        options = matcher.get("options") or {}
        if not pattern:
            continue
        if options.get("negate") or options.get("negation"):
            negations.append(pattern)
            continue
        if m_type in {"keyword", "phrase"}:
            lexicon.append(pattern)
        elif m_type == "regex":
            flags = str(options.get("flags") or "i")
            regex.append({"pattern": pattern, "flags": flags})
        elif m_type == "negation":
            negations.append(pattern)
        elif m_type == "proximity":
            window = options.get("window")
            try:
                proximity["window"] = int(window)
            except (TypeError, ValueError):
                pass
        else:
            lexicon.append(pattern)
    payload: Dict[str, Any] = {}
    if lexicon:
        payload["lexicon"] = list(dict.fromkeys(lexicon))
    if regex:
        payload["regex"] = regex
    if negations:
        payload["negations"] = list(dict.fromkeys(negations))
    if proximity:
        payload["proximity"] = proximity
    return payload


@dataclass(frozen=True)
class NormClause:
    """Normalized clause payload produced by Module 3-2."""

    id: str
    index_path: str
    text: str
    normalized_text: str
    title: Optional[str] = None
    tags: Tuple[str, ...] = field(default_factory=tuple)
    category: Optional[str] = None
    subcategory: Optional[str] = None
    canonical_terms: Tuple[str, ...] = field(default_factory=tuple)
    def_bindings: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NormClause":
        return cls(
            id=str(payload.get("id", "")),
            index_path=str(payload.get("index_path", "")),
            text=str(payload.get("text", "")),
            normalized_text=str(payload.get("normalized_text") or payload.get("text", "")),
            title=payload.get("title"),
            tags=_to_tuple(payload.get("tags")),
            category=payload.get("category"),
            subcategory=payload.get("subcategory"),
            canonical_terms=_to_tuple(payload.get("canonical_terms")),
            def_bindings=_to_tuple(payload.get("def_bindings")),
        )


@dataclass(frozen=True)
class RuntimeRule:
    """Compiled rule emitted by Module 3-3."""

    rule_id: str
    version: Optional[str]
    scope: Mapping[str, Any]
    matchers: Mapping[str, Any]
    severity: Optional[str]
    weight: float
    priority: int
    evidence_hints: Tuple[str, ...]
    requires: Tuple[str, ...]
    flags: Tuple[str, ...]
    activation: Mapping[str, Any]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RuntimeRule":
        flags_payload = payload.get("flags")
        if isinstance(flags_payload, Mapping):
            extracted_flags: List[str] = []
            if flags_payload.get("critical"):
                extracted_flags.append("critical")
            flags = tuple(extracted_flags)
        else:
            flags = _to_tuple(flags_payload)

        matchers_payload = payload.get("matchers", {})
        if isinstance(matchers_payload, list):
            matchers = _legacy_matchers_to_dict(matchers_payload)
        else:
            matchers = matchers_payload or {}

        evidence_payload = payload.get("evidence_hints")
        return cls(
            rule_id=str(payload.get("rule_id", payload.get("id", ""))),
            version=payload.get("version"),
            scope=payload.get("scope", {}),
            matchers=matchers,
            severity=payload.get("severity"),
            weight=float(payload.get("weight", 1.0)),
            priority=int(payload.get("priority", 0)),
            evidence_hints=_to_tuple(evidence_payload),
            requires=_to_tuple(payload.get("requires")),
            flags=flags,
            activation=payload.get("activation", {}),
        )

    def is_active(self) -> bool:
        status = str(self.activation.get("status", "active")).lower()
        return status not in {"disabled", "deprecated"}

    def applies_to(self, clause: NormClause) -> bool:
        scope_category = self.scope.get("category")
        if scope_category and clause.category and scope_category != clause.category:
            return False
        scope_subcategory = self.scope.get("subcategory")
        if scope_subcategory and clause.subcategory and scope_subcategory != clause.subcategory:
            return False
        scope_tags = set(self.scope.get("tags", []) or [])
        if scope_tags:
            if not set(clause.tags or ()).intersection(scope_tags):
                return False
        return True


@dataclass(frozen=True)
class RulesetRuntime:
    """Container for a compiled ruleset and supporting artifacts."""

    rules: Tuple[RuntimeRule, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    indices: Mapping[str, Any] = field(default_factory=dict)
    feature_requirements: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    experiment: Optional[Mapping[str, Any]] = None
    lexicons: Mapping[str, Any] = field(default_factory=dict)
    syntax_patterns: Mapping[str, Any] = field(default_factory=dict)
    proximity: Mapping[str, Any] = field(default_factory=dict)
    negation_terms: Tuple[str, ...] = field(default_factory=tuple)
    exception_cues: Tuple[str, ...] = field(default_factory=tuple)
    mediation_table: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    ) -> "RulesetRuntime":
        if isinstance(payload, Mapping):
            source: Mapping[str, Any] = payload
        elif isinstance(payload, Sequence):
            source = {"rules": list(payload)}
        else:
            raise TypeError(
                "ruleset payload must be a mapping or a sequence of rule objects",
            )

        raw_rules = source.get("rules", {})
        rule_items: List[Mapping[str, Any]]
        if isinstance(raw_rules, Mapping):
            rule_items = []
            for rule_id, rule_payload in raw_rules.items():
                merged = dict(rule_payload or {})
                merged.setdefault("rule_id", rule_id)
                rule_items.append(merged)
        else:
            rule_items = list(raw_rules or [])
        rules = tuple(RuntimeRule.from_dict(item) for item in rule_items)

        feature_requirements_payload = source.get("feature_requirements", {})
        feature_map: Dict[str, Tuple[str, ...]] = {}
        if isinstance(feature_requirements_payload, Mapping):
            for key, value in feature_requirements_payload.items():
                feature_map[str(key)] = _to_tuple(value)
        elif isinstance(feature_requirements_payload, Iterable):
            shared = _to_tuple(feature_requirements_payload)
            if shared:
                for rule in rules:
                    feature_map[rule.rule_id] = shared

        return cls(
            rules=rules,
            metadata=source.get("metadata", {}),
            indices=source.get("indices", {}),
            feature_requirements=feature_map,
            experiment=source.get("experiment"),
            lexicons=source.get("lexicons", {}),
            syntax_patterns=source.get("syntax_patterns", {}),
            proximity=source.get("proximity", {}),
            negation_terms=_to_tuple(source.get("negation_terms")),
            exception_cues=_to_tuple(source.get("exception_cues")),
            mediation_table=source.get("mediation_table", {}),
        )

    def required_features_for(self, rule_id: str) -> Tuple[str, ...]:
        return self.feature_requirements.get(rule_id, tuple())

    def rule_by_id(self) -> Mapping[str, RuntimeRule]:
        return {rule.rule_id: rule for rule in self.rules}


@dataclass
class MatchEvidence:
    """Intermediate evidence emitted by matchers prior to consolidation."""

    rule_id: str
    clause_id: str
    match_type: str
    strength: float
    spans: List[Tuple[int, int]]
    evidence_snippet: str
    notes: List[str] = field(default_factory=list)

    def clamp_strength(self) -> "MatchEvidence":
        self.strength = max(0.0, min(1.0, self.strength))
        return self


@dataclass
class Hit:
    """Final engine output consumed by downstream modules."""

    rule_id: str
    clause_id: str
    match_type: str
    strength: float
    spans: Tuple[Tuple[int, int], ...]
    evidence_snippet: str
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "clause_id": self.clause_id,
            "match_type": self.match_type,
            "strength": round(self.strength, 4),
            "spans": list(self.spans),
            "evidence_snippet": self.evidence_snippet,
            "notes": list(self.notes),
        }


__all__ = [
    "NormClause",
    "RuntimeRule",
    "RulesetRuntime",
    "MatchEvidence",
    "Hit",
]
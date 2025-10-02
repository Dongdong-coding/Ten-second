from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re


KNOWN_EFFECTS = {"OVERRIDE", "MITIGATE", "BOUND_BY", "CONFLICT", "DEPEND"}
DEFAULT_EFFECT_MAP = {
    "NOTWITHSTANDING": "OVERRIDE",
    "SUBJECT_TO": "BOUND_BY",
    "ANNEX_REF": "DEPEND",
    "DEFINITION_LINK": "DEPEND",
    "EXCEPTION_LINK": "MITIGATE",
    "REF_ARTICLE": "DEPEND",
}
DEFAULT_PRIORITIES = ["OVERRIDE", "CONFLICT", "MITIGATE", "BOUND_BY", "DEPEND"]
DEFAULT_THRESHOLDS = {"mitigate_conf_min": 0.80, "mitigate_bonus": 0.05}
DEFAULT_PHRASES = {"notwithstanding": "notwithstanding", "subject_to": "subject to"}


@dataclass
class PolicyRule:
    section: str
    index: int
    when: Dict[str, Any]
    effect: str
    note: Optional[str] = None

    def matches(self, *, edge: str, this_clause: Any, other_clause: Any) -> bool:
        for key, expected in self.when.items():
            if key == "edge":
                if not _match_value(expected, edge):
                    return False
                continue
            if key.startswith("this."):
                attr = key.split(".", 1)[1]
                value = _lookup_attr(this_clause, attr)
                if not _match_value(expected, value):
                    return False
                continue
            if key.startswith("target."):
                attr = key.split(".", 1)[1]
                value = _lookup_attr(other_clause, attr)
                if not _match_value(expected, value):
                    return False
                continue
        return True

    def describe(self) -> str:
        return f"policy:{self.section}[{self.index}]"


@dataclass
class PolicyDecision:
    effect: Optional[str]
    rationale: str
    notes: List[str]


def _lookup_attr(obj: Any, attr: str) -> str:
    if obj is None:
        return ""
    name = {
        "category": "category",
        "subcategory": "subcategory",
        "phrase": "normalized_text",
        "tags": "tags",
        "id": "clause_id",
    }.get(attr, attr)
    value = getattr(obj, name, "")
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key}:{val}" for key, val in value.items())
    return str(value)


def _match_value(expected: Any, value: Any) -> bool:
    haystack = str(value)
    if expected is None:
        return False
    pattern = str(expected)
    if pattern == "*":
        return True
    return bool(re.search(pattern, haystack, flags=re.IGNORECASE))


class ContextPolicy:
    def __init__(
        self,
        *,
        rules: List[PolicyRule],
        thresholds: Dict[str, float],
        priorities: List[str],
        phrases: Dict[str, str],
        default_effects: Dict[str, str],
    ) -> None:
        self._rules = rules
        self.thresholds = {**DEFAULT_THRESHOLDS, **thresholds}
        self.priorities = priorities or DEFAULT_PRIORITIES
        self.phrases = {**DEFAULT_PHRASES, **phrases}
        self.default_effects = {**DEFAULT_EFFECT_MAP, **default_effects}

    @classmethod
    def from_file(cls, path: Path) -> "ContextPolicy":
        with path.open("r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
        return cls.from_dict(raw_data)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ContextPolicy":
        rules: List[PolicyRule] = []
        for section in ("overrides", "subject_to", "annex", "conflicts", "mitigations", "custom"):
            entries = payload.get(section, []) or []
            for idx, entry in enumerate(entries):
                rules.append(
                    PolicyRule(
                        section=section,
                        index=idx,
                        when=dict(entry.get("when", {})),
                        effect=str(entry.get("effect", "")),
                        note=entry.get("note"),
                    )
                )
        thresholds = dict(payload.get("thresholds", {}) or {})
        priorities = list(payload.get("priorities", []) or [])
        phrases = dict(payload.get("phrases", {}) or {})
        defaults = dict(payload.get("default_effects", {}) or {})
        return cls(
            rules=rules,
            thresholds=thresholds,
            priorities=priorities,
            phrases=phrases,
            default_effects=defaults,
        )

    def decide(self, relation_type: str, *, this_clause: Any, other_clause: Any) -> PolicyDecision:
        notes: List[str] = []
        for rule in self._rules:
            if not rule.matches(edge=relation_type, this_clause=this_clause, other_clause=other_clause):
                continue
            effect = rule.effect if rule.effect in KNOWN_EFFECTS else None
            rationale = rule.describe()
            if rule.effect and rule.effect not in KNOWN_EFFECTS:
                notes.append(rule.effect)
            if rule.note:
                notes.append(rule.note)
            if effect:
                return PolicyDecision(effect=effect, rationale=rationale, notes=notes)
        default_effect = self.default_effects.get(relation_type, "DEPEND")
        rationale = f"default:{relation_type.lower()}"
        if default_effect not in KNOWN_EFFECTS:
            notes.append(default_effect)
            return PolicyDecision(effect=None, rationale=rationale, notes=notes)
        return PolicyDecision(effect=default_effect, rationale=rationale, notes=notes)


__all__ = ["ContextPolicy", "PolicyDecision", "PolicyRule", "KNOWN_EFFECTS"]
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


_UTF8_SIG = "utf-8-sig"


@dataclass
class ScoreRecord:
    clause_id: str
    confidence: float
    risk_flag: str
    adopted_rules: Tuple[str, ...] = field(default_factory=tuple)
    reasons: Tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ScoreRecord":
        return cls(
            clause_id=str(payload["clause_id"]),
            confidence=float(payload.get("confidence", 0.0)),
            risk_flag=str(payload.get("risk_flag", "AMBIG")),
            adopted_rules=tuple(str(rule) for rule in payload.get("adopted_rules", []) or []),
            reasons=tuple(str(reason) for reason in payload.get("reasons", []) or []),
        )


@dataclass
class HitRecord:
    rule_id: str
    clause_id: str
    match_type: str
    strength: float

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "HitRecord":
        return cls(
            rule_id=str(payload.get("rule_id", "")),
            clause_id=str(payload.get("clause_id", "")),
            match_type=str(payload.get("match_type", "")),
            strength=float(payload.get("strength", 0.0)),
        )


@dataclass
class GoldenClause:
    clause_id: str
    expected_flag: str
    expected_rules: Tuple[str, ...] = field(default_factory=tuple)
    notes: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GoldenClause":
        expected_rules_payload = payload.get("expected_rules", []) or []
        return cls(
            clause_id=str(payload["clause_id"]),
            expected_flag=str(payload.get("expected_flag", "AMBIG")),
            expected_rules=tuple(str(rule) for rule in expected_rules_payload),
            notes=str(payload["notes"]) if payload.get("notes") is not None else None,
        )




def _resolve_critical_flag(flags_payload: Any) -> bool:
    if not flags_payload:
        return False
    if isinstance(flags_payload, Mapping):
        return bool(flags_payload.get("critical"))
    if isinstance(flags_payload, Sequence) and not isinstance(flags_payload, (str, bytes, bytearray)):
        for flag in flags_payload:
            if str(flag).strip().lower() == "critical":
                return True
        return False
    raise ValueError(
        "ruleset_runtime.rules[*].flags must be an object or list of flag names",
    )


@dataclass
class RuleDefinition:
    rule_id: str
    category: Optional[str]
    subcategory: Optional[str]
    variant: Optional[str]
    critical: bool

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RuleDefinition":
        rule_id = str(payload.get("id") or payload.get("rule_id") or "")
        metadata = payload.get("metadata", {}) or {}
        flags_payload = payload.get("flags")
        critical = _resolve_critical_flag(flags_payload)
        return cls(
            rule_id=rule_id,
            category=str(payload.get("category")) if payload.get("category") is not None else None,
            subcategory=str(payload.get("subcategory")) if payload.get("subcategory") is not None else None,
            variant=str(metadata.get("variant")) if metadata.get("variant") is not None else None,
            critical=critical,
        )


@dataclass
class RunStats:
    timings: Dict[str, float] = field(default_factory=dict)
    memory_mb: Optional[float] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RunStats":
        timings_payload = payload.get("timings", {}) or {}
        memory_mb = payload.get("memory_mb")
        extras = {k: v for k, v in payload.items() if k not in {"timings", "memory_mb"}}
        return cls(
            timings={str(k): float(v) for k, v in timings_payload.items()},
            memory_mb=float(memory_mb) if memory_mb is not None else None,
            extras=extras,
        )


def load_json(path: Path) -> Any:
    with path.open("r", encoding=_UTF8_SIG) as handle:
        return json.load(handle)


def load_scores(path: Path) -> List[ScoreRecord]:
    payload = load_json(path)
    if not isinstance(payload, Sequence):
        raise ValueError(f"scores payload must be a list, received {type(payload)!r}")
    return [ScoreRecord.from_dict(item) for item in payload]


def load_hits(path: Path) -> List[HitRecord]:
    payload = load_json(path)
    if not isinstance(payload, Sequence):
        raise ValueError(f"hits payload must be a list, received {type(payload)!r}")
    return [HitRecord.from_dict(item) for item in payload]


def load_golden(path: Path) -> List[GoldenClause]:
    payload = load_json(path)
    if not isinstance(payload, Sequence):
        raise ValueError(f"golden labels payload must be a list, received {type(payload)!r}")
    return [GoldenClause.from_dict(item) for item in payload]


def load_ruleset(path: Path) -> Dict[str, RuleDefinition]:
    payload = load_json(path)
    rules_payload: Iterable[Any]
    if isinstance(payload, dict) and "rules" in payload:
        rules_payload = payload.get("rules", []) or []
    elif isinstance(payload, Sequence):
        rules_payload = payload
    else:
        raise ValueError("ruleset payload must be a dict with a `rules` key or a list of rules")

    rules: Dict[str, RuleDefinition] = {}
    for item in rules_payload:
        try:
            definition = RuleDefinition.from_dict(item)
        except ValueError as exc:
            rule_label = None
            if isinstance(item, Mapping):
                rule_label = item.get("rule_id") or item.get("id")
            message = str(exc) if rule_label is None else f"{exc} (rule_id={rule_label})"
            raise ValueError(message) from None
        if not definition.rule_id:
            continue
        rules[definition.rule_id] = definition
    return rules


def load_run_stats(path: Optional[Path]) -> Optional[RunStats]:
    if path is None:
        return None
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("run stats payload must be an object")
    return RunStats.from_dict(payload)

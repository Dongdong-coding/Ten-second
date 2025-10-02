from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "HIGH": 0.99,
    "WARN": 0.10,
    "ambig_gap": 0.08,
}

DEFAULT_PENALTIES: Dict[str, float] = {
    "negation": 0.25,
    "exception": 0.15,
    "conflict_local": 0.20,
    "low_evidence": 0.10,
}

DEFAULT_RESOLUTION_ORDER: Sequence[str] = (
    "scope_specificity",
    "priority",
    "most_conservative",
)

DEFAULT_CALIBRATION: Dict[str, Any] = {
    "enable": True,
    "target_warn_rate": 0.90,
    "min_warn": 0.05,
    "max_warn": 0.85,
    "demote_high_to_warn": True,
    "critical_flag": "critical",
}

_SEVERITY_SYNONYMS = {
    "OK": "OK",
    "LOW": "LOW",
    "INFO": "LOW",
    "WARN": "WARN",
    "WARNING": "WARN",
    "MEDIUM": "WARN",
    "HIGH": "HIGH",
    "ALERT": "HIGH",
    "CRITICAL": "CRITICAL",
}


@dataclass
class Hit:
    rule_id: str
    clause_id: str
    match_type: str
    spans: List[Tuple[int, int]]
    strength: float
    notes: List[str] = field(default_factory=list)
    numeric_ctx: Optional[Dict[str, Any]] = None
    table_ctx: Optional[Dict[str, Any]] = None
    flags: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Dict[str, Any]) -> "Hit":
        spans = []
        for span in payload.get("spans", []):
            if isinstance(span, dict):
                start = int(span.get("start", 0))
                end = int(span.get("end", start))
                spans.append((start, end))
            else:
                start, end = span
                spans.append((int(start), int(end)))
        notes = list(payload.get("notes", []))
        flags = dict(payload.get("flags", {}))
        return cls(
            rule_id=str(payload["rule_id"]),
            clause_id=str(payload["clause_id"]),
            match_type=str(payload.get("match_type", "lex")),
            spans=spans,
            strength=float(payload.get("strength", 0.0)),
            notes=notes,
            numeric_ctx=payload.get("numeric_ctx"),
            table_ctx=payload.get("table_ctx"),
            flags=flags,
        )


@dataclass
class Rule:
    rule_id: str
    weight: float = 1.0
    priority: int = 0
    severity: str = "WARN"
    scope: Dict[str, Any] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, payload: Dict[str, Any]) -> "Rule":
        severity_raw = str(payload.get("severity", "WARN")).upper()
        severity = _SEVERITY_SYNONYMS.get(severity_raw)
        if severity is None:
            raise ValueError(f"Unsupported severity '{severity_raw}' in runtime payload")
        flags_payload = payload.get("flags") or {}
        flags: List[str]
        if isinstance(flags_payload, Mapping):
            flags = [name for name, enabled in flags_payload.items() if enabled]
        else:
            flags = [str(flag) for flag in (flags_payload or [])]
        return cls(
            rule_id=str(payload["rule_id"]),
            weight=float(payload.get("weight", 1.0)),
            priority=int(payload.get("priority", 0)),
            severity=severity,
            scope=dict(payload.get("scope", {})),
            flags=flags,
        )


@dataclass
class CalibrationSettings:
    enable: bool = True
    target_warn_rate: float = 0.90
    min_warn: float = 0.05
    max_warn: float = 0.85
    demote_high_to_warn: bool = True
    critical_flag: str = "critical"

    @classmethod
    def from_mapping(cls, payload: Optional[Dict[str, Any]]) -> "CalibrationSettings":
        if not payload:
            payload = {}
        merged = {**DEFAULT_CALIBRATION, **payload}
        return cls(
            enable=bool(merged.get("enable", True)),
            target_warn_rate=float(merged.get("target_warn_rate", 0.90)),
            min_warn=float(merged.get("min_warn", 0.05)),
            max_warn=float(merged.get("max_warn", 0.85)),
            demote_high_to_warn=bool(merged.get("demote_high_to_warn", True)),
            critical_flag=str(merged.get("critical_flag", "critical")),
        )


@dataclass
class Policy:
    thresholds: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    penalties: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PENALTIES))
    resolution_order: Sequence[str] = field(default_factory=lambda: list(DEFAULT_RESOLUTION_ORDER))
    calibration: CalibrationSettings = field(default_factory=CalibrationSettings)

    @classmethod
    def from_mapping(cls, payload: Optional[Dict[str, Any]]) -> "Policy":
        if not payload:
            payload = {}
        thresholds = dict(DEFAULT_THRESHOLDS)
        thresholds.update(payload.get("thresholds", {}))
        penalties = dict(DEFAULT_PENALTIES)
        penalties.update(payload.get("penalties", {}))
        resolution = list(DEFAULT_RESOLUTION_ORDER)
        if "resolution_order" in payload:
            resolution = list(payload.get("resolution_order", []))
        calibration = CalibrationSettings.from_mapping(payload.get("calibration"))
        return cls(
            thresholds=thresholds,
            penalties=penalties,
            resolution_order=resolution,
            calibration=calibration,
        )


@dataclass
class PerHitScore:
    rule_id: str
    raw: float
    penalties_applied: Dict[str, float]
    match_type: str
    strength: float
    weight: float
    adjusted: float

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        return payload


@dataclass
class ClauseScore:
    clause_id: str
    confidence: float
    risk_flag: str
    reasons: List[str]
    adopted_rules: List[str]
    suppressed_rules: List[str]
    per_hit_scores: List[PerHitScore]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["per_hit_scores"] = [score.to_dict() for score in self.per_hit_scores]
        return payload


def hits_from_payload(payload: Any) -> List[Hit]:
    if isinstance(payload, Mapping) and "hits" in payload:
        payload = payload.get("hits", [])
    if not isinstance(payload, Iterable):
        raise ValueError("hits payload must be iterable")
    return [Hit.from_mapping(item) for item in payload]


def rules_from_payload(payload: Any) -> Dict[str, Rule]:
    if isinstance(payload, Mapping):
        raw_rules = payload.get("rules")
        if isinstance(raw_rules, Mapping):
            items = []
            for rule_id, definition in raw_rules.items():
                merged = dict(definition or {})
                merged.setdefault("rule_id", rule_id)
                items.append(merged)
        else:
            items = list(raw_rules or [])
    else:
        items = list(payload or [])
    return {rule.rule_id: rule for rule in (Rule.from_mapping(item) for item in items)}


__all__ = [
    "Hit",
    "Rule",
    "Policy",
    "CalibrationSettings",
    "PerHitScore",
    "ClauseScore",
    "hits_from_payload",
    "rules_from_payload",
    "DEFAULT_THRESHOLDS",
    "DEFAULT_PENALTIES",
]
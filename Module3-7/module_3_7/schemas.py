from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json

_UTF8_SIG = "utf-8-sig"


@dataclass
class Clause:
    clause_id: str
    index_path: str
    text: str
    normalized_text: str
    title: str
    tags: List[str]
    category: str
    subcategory: str
    canonical_terms: List[str]
    def_bindings: Dict[str, str]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Clause":
        return cls(
            clause_id=str(payload.get("id") or payload.get("clause_id") or ""),
            index_path=str(payload.get("index_path", "")),
            text=str(payload.get("text", "")),
            normalized_text=str(payload.get("normalized_text", payload.get("text", ""))),
            title=str(payload.get("title", "")),
            tags=list(payload.get("tags", []) or []),
            category=str(payload.get("category", "UNKNOWN")),
            subcategory=str(payload.get("subcategory", "")),
            canonical_terms=list(payload.get("canonical_terms", []) or []),
            def_bindings=dict(payload.get("def_bindings", {}) or {}),
        )


@dataclass
class Score:
    clause_id: str
    confidence: float
    risk_flag: str
    adopted_rules: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Score":
        return cls(
            clause_id=str(payload["clause_id"]),
            confidence=float(payload.get("confidence", 0.0)),
            risk_flag=str(payload.get("risk_flag", "AMBIG")),
            adopted_rules=list(payload.get("adopted_rules", []) or []),
            reasons=list(payload.get("reasons", []) or []),
        )


@dataclass
class Hit:
    rule_id: str
    clause_id: str
    match_type: str
    spans: List[Dict[str, Any]]
    strength: float

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Hit":
        return cls(
            rule_id=str(payload.get("rule_id", "")),
            clause_id=str(payload.get("clause_id", "")),
            match_type=str(payload.get("match_type", "")),
            spans=list(payload.get("spans", []) or []),
            strength=float(payload.get("strength", 0.0)),
        )


@dataclass
class Relation:
    source_id: str
    target_id: str
    relation_type: str
    cue: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "type": self.relation_type,
            "target_clause_id": self.target_id,
        }
        if self.cue:
            data["cue"] = self.cue
        return data


@dataclass
class Evidence:
    source_snippet: Optional[str] = None
    target_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if self.source_snippet:
            payload["source_snippet"] = self.source_snippet
        if self.target_snippet:
            payload["target_snippet"] = self.target_snippet
        return payload


@dataclass
class EffectRecord:
    effect_type: str
    target_clause_id: str
    rationale: str
    evidence: Optional[Evidence] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "type": self.effect_type,
            "target_clause_id": self.target_clause_id,
            "rationale": self.rationale,
        }
        if self.evidence:
            evidence_dict = self.evidence.to_dict()
            if evidence_dict:
                data["evidence"] = evidence_dict
        return data


@dataclass
class ContextResolution:
    clause_id: str
    base_risk_flag: str
    base_confidence: float
    relations: List[Relation] = field(default_factory=list)
    effects: List[EffectRecord] = field(default_factory=list)
    contextual_risk_flag: Optional[str] = None
    policy_notes: List[str] = field(default_factory=list)
    graph_degree_out: int = 0
    graph_degree_in: int = 0

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "clause_id": self.clause_id,
            "base_risk_flag": self.base_risk_flag,
            "base_confidence": self.base_confidence,
            "relations": [relation.to_dict() for relation in self.relations],
            "effects": [effect.to_dict() for effect in self.effects],
            "policy_notes": list(self.policy_notes),
            "graph_degree": {"out": self.graph_degree_out, "in": self.graph_degree_in},
        }
        if self.contextual_risk_flag:
            payload["contextual_risk_flag"] = self.contextual_risk_flag
        return payload


def _load_json(path: Path) -> Any:
    with path.open("r", encoding=_UTF8_SIG) as handle:
        return json.load(handle)


def load_clauses(path: Path) -> Dict[str, Clause]:
    data = _load_json(path)
    if isinstance(data, dict):
        data = data.get("clauses") or data.get("norm_clauses") or list(data.values())
    if not isinstance(data, list):
        raise ValueError(f"clauses payload must be a list, received {type(data)!r}")
    clauses = [Clause.from_dict(item) for item in data]
    return {clause.clause_id: clause for clause in clauses}


def load_scores(path: Path) -> Dict[str, Score]:
    data = _load_json(path)
    if not isinstance(data, list):
        raise ValueError("scores must be a list of per-clause objects")
    scores = [Score.from_dict(item) for item in data]
    return {score.clause_id: score for score in scores}


def load_hits(path: Path) -> List[Hit]:
    data = _load_json(path)
    if isinstance(data, dict) and "hits" in data:
        data = data.get("hits", [])
    if not isinstance(data, Iterable):
        raise ValueError("hits payload must be iterable")
    return [Hit.from_dict(item) for item in data]


__all__ = [
    "Clause",
    "Score",
    "Hit",
    "Relation",
    "Evidence",
    "EffectRecord",
    "ContextResolution",
    "load_clauses",
    "load_scores",
    "load_hits",
]
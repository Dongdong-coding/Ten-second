from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

JsonDict = Dict[str, Any]


@dataclass(slots=True)
class DefinitionBinding:
    alias: str
    base: str
    source_clause_id: str

    def to_dict(self) -> JsonDict:
        return {
            'alias': self.alias,
            'base': self.base,
            'source_clause_id': self.source_clause_id,
        }


@dataclass(slots=True)
class Clause:
    id: str
    text: str
    title: str = ''
    tags: List[str] = field(default_factory=list)
    start: int = 0
    end: int = 0
    index_path: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: JsonDict) -> 'Clause':
        tags = data.get('tags') or []
        index_path_value = data.get('index_path', '')
        if isinstance(index_path_value, list):
            index_path = '.'.join(str(part) for part in index_path_value)
        else:
            index_path = str(index_path_value)
        metadata = data.get('metadata', {}) or {}
        return cls(
            id=str(data.get('id', '')),
            text=str(data.get('text', '')),
            title=str(data.get('title', '')),
            tags=[str(tag) for tag in tags],
            start=int(data.get('start', 0) or 0),
            end=int(data.get('end', 0) or 0),
            index_path=index_path,
            metadata=dict(metadata),
        )

    def to_dict(self) -> JsonDict:
        payload: JsonDict = {
            'id': self.id,
            'text': self.text,
            'title': self.title,
            'tags': list(self.tags),
            'start': self.start,
            'end': self.end,
        }
        if self.index_path:
            payload['index_path'] = self.index_path
        if self.metadata:
            payload['metadata'] = dict(self.metadata)
        return payload


@dataclass(slots=True)
class NormClause:
    id: str
    normalized_text: str
    category: str
    subcategory: Optional[str]
    canonical_terms: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    def_bindings: List[DefinitionBinding] = field(default_factory=list)
    evidence_keywords: List[str] = field(default_factory=list)
    candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        payload: JsonDict = {
            'id': self.id,
            'normalized_text': self.normalized_text,
            'category': self.category,
            'subcategory': self.subcategory,
            'canonical_terms': list(self.canonical_terms),
            'tags': list(self.tags),
        }
        return payload


__all__ = ['Clause', 'DefinitionBinding', 'NormClause']

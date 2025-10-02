from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class NormClause:
    """Normalized clause payload emitted from Module 3-2."""

    id: str
    index_path: Optional[str]
    text: str
    normalized_text: Optional[str] = None
    title: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    category: Optional[str] = None
    subcategory: Optional[str] = None
    canonical_terms: List[str] = field(default_factory=list)
    sent_boundaries: Optional[List[Tuple[int, int]]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NormClause":
        sent_bounds = data.get("sent_boundaries") or data.get("sentence_spans")
        if sent_bounds is not None:
            parsed_bounds: List[Tuple[int, int]] = []
            for pair in sent_bounds:
                if isinstance(pair, dict):
                    start = int(pair.get("start", 0))
                    end = int(pair.get("end", start))
                else:
                    start, end = pair
                parsed_bounds.append((start, end))
        else:
            parsed_bounds = None
        return cls(
            id=str(data["id"]),
            index_path=data.get("index_path"),
            text=str(data.get("text", "")),
            normalized_text=data.get("normalized_text"),
            title=data.get("title"),
            tags=list(data.get("tags", []) or []),
            category=data.get("category"),
            subcategory=data.get("subcategory"),
            canonical_terms=list(data.get("canonical_terms", []) or []),
            sent_boundaries=parsed_bounds,
        )


@dataclass
class TableContext:
    cell_text: str
    row: Optional[int] = None
    col: Optional[int] = None
    header_top: Optional[str] = None
    header_left: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: Optional[Dict[str, Any]]) -> Optional["TableContext"]:
        if not payload:
            return None
        return cls(
            cell_text=str(payload.get("cell_text", "")),
            row=payload.get("row"),
            col=payload.get("col"),
            header_top=payload.get("header_top"),
            header_left=payload.get("header_left"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_text": self.cell_text,
            "row": self.row,
            "col": self.col,
            "header_top": self.header_top,
            "header_left": self.header_left,
        }


@dataclass
class NumericContext:
    value: Optional[float]
    unit: Optional[str] = None
    comparator: Optional[str] = None
    rhs_display: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: Optional[Dict[str, Any]]) -> Optional["NumericContext"]:
        if not payload:
            return None
        return cls(
            value=payload.get("value"),
            unit=payload.get("unit"),
            comparator=payload.get("comparator"),
            rhs_display=payload.get("rhs_display"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "comparator": self.comparator,
            "rhs_display": self.rhs_display,
        }


@dataclass
class Hit:
    rule_id: str
    clause_id: str
    match_type: str
    spans: List[Tuple[int, int]]
    strength: Optional[float]
    notes: List[str] = field(default_factory=list)
    table_ctx: Optional[TableContext] = None
    numeric_ctx: Optional[NumericContext] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hit":
        raw_spans = data.get("spans") or []
        spans: List[Tuple[int, int]] = []
        for span in raw_spans:
            if isinstance(span, dict):
                start = int(span.get("start", 0))
                end = int(span.get("end", start))
            else:
                start, end = span
            spans.append((start, end))
        return cls(
            rule_id=str(data.get("rule_id")),
            clause_id=str(data.get("clause_id")),
            match_type=str(data.get("match_type", "")),
            spans=spans,
            strength=data.get("strength"),
            notes=list(data.get("notes", []) or []),
            table_ctx=TableContext.from_payload(data.get("table_ctx")),
            numeric_ctx=NumericContext.from_payload(data.get("numeric_ctx")),
        )


@dataclass
class Evidence:
    rule_id: str
    clause_id: str
    match_type: str
    snippet: str
    snippet_char_start_abs: int
    snippet_char_end_abs: int
    highlights_rel: List[Tuple[int, int]]
    sentence_span: Tuple[int, int]
    context_window_sentences: int
    overflow: bool
    strength: Optional[float]
    notes: List[str] = field(default_factory=list)
    table_ctx: Optional[TableContext] = None
    numeric_ctx: Optional[NumericContext] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "rule_id": self.rule_id,
            "clause_id": self.clause_id,
            "match_type": self.match_type,
            "snippet": self.snippet,
            "snippet_char_start_abs": self.snippet_char_start_abs,
            "snippet_char_end_abs": self.snippet_char_end_abs,
            "highlights_rel": [[s, e] for s, e in self.highlights_rel],
            "sentence_span": [self.sentence_span[0], self.sentence_span[1]],
            "context_window_sentences": self.context_window_sentences,
            "overflow": self.overflow,
            "strength": self.strength,
            "notes": self.notes,
        }
        if self.table_ctx:
            payload["table_ctx"] = self.table_ctx.to_dict()
        if self.numeric_ctx:
            payload["numeric_ctx"] = self.numeric_ctx.to_dict()
        return payload


EvidenceList = Iterable[Evidence]

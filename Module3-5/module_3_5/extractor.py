from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from .schemas import Evidence, Hit, NormClause


_UTF8_SIG = "utf-8-sig"


@dataclass(frozen=True)
class Sentence:
    start: int
    end: int

    def intersects(self, span: Tuple[int, int]) -> bool:
        span_start, span_end = span
        return not (span_end <= self.start or span_start >= self.end)


DEFAULT_MIN_LENGTH = 120
DEFAULT_MAX_LENGTH = 300
CONTEXT_SENTENCE_PADDING = 1
SENSITIVE_PATTERNS = [
    re.compile(r"\b(?:\d{2,}-){2,}\d{2,}\b"),
    re.compile(r"\b\d{4,}\b"),
    re.compile(r"\b\d{2,3}-\d{3,4}-\d{4}\b"),
    re.compile(r"\b\d{2,3}-\d{2}-\d{6}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
]


class ClauseNotFoundError(KeyError):
    """Raised when a hit references an unknown clause identifier."""


def load_clauses(path: Path) -> Dict[str, NormClause]:
    data = _read_json(path)
    if isinstance(data, dict):
        if "clauses" in data:
            payload = data["clauses"]
        elif "norm_clauses" in data:
            payload = data["norm_clauses"]
        else:
            payload = list(data.values())
    else:
        payload = data
    clauses = [NormClause.from_dict(item) for item in payload]
    return {clause.id: clause for clause in clauses}


def load_hits(path: Path) -> List[Hit]:
    data = _read_json(path)
    if isinstance(data, dict):
        if "hits" in data:
            payload = data.get("hits", [])
        else:
            payload = list(data.values())
    else:
        payload = data

    if payload in (None, ""):
        return []
    if not isinstance(payload, Iterable):
        raise ValueError("hits payload must be iterable")

    hits: List[Hit] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each hit must be an object")
        hits.append(Hit.from_dict(item))
    return hits


def extract_evidence(
    clauses: Dict[str, NormClause],
    hits: Sequence[Hit],
    *,
    target_min: int = DEFAULT_MIN_LENGTH,
    target_max: int = DEFAULT_MAX_LENGTH,
    redact_sensitive: bool = False,
) -> List[Evidence]:
    if target_min > target_max:
        target_min, target_max = target_max, target_min
    results: List[Evidence] = []
    for hit in hits:
        clause = clauses.get(hit.clause_id)
        if clause is None:
            raise ClauseNotFoundError(f"Unknown clause_id '{hit.clause_id}' in hit {hit.rule_id}")
        sentences = _resolve_sentences(clause)
        merged_spans = _merge_spans(hit.spans, len(clause.text))
        snippet_info = _build_snippet_window(
            clause_text=clause.text,
            sentences=sentences,
            highlight_spans=merged_spans,
            target_min=target_min,
            target_max=target_max,
        )
        snippet = snippet_info.snippet
        highlights_rel = _relativize_highlights(snippet_info.start, merged_spans, len(snippet))
        overflow = snippet_info.overflow
        context_padding = snippet_info.context_padding
        notes = list(hit.notes)
        if redact_sensitive:
            snippet, redacted = _redact_snippet(snippet)
            if redacted and "redacted_sensitive" not in notes:
                notes.append("redacted_sensitive")
        evidence = Evidence(
            rule_id=hit.rule_id,
            clause_id=hit.clause_id,
            match_type=hit.match_type,
            snippet=snippet,
            snippet_char_start_abs=snippet_info.start,
            snippet_char_end_abs=snippet_info.end,
            highlights_rel=highlights_rel,
            sentence_span=(snippet_info.sent_start_idx, snippet_info.sent_end_idx),
            context_window_sentences=context_padding,
            overflow=overflow,
            strength=hit.strength,
            notes=notes,
            table_ctx=hit.table_ctx,
            numeric_ctx=hit.numeric_ctx,
        )
        results.append(evidence)
    return results


@dataclass
class SnippetWindow:
    start: int
    end: int
    sent_start_idx: int
    sent_end_idx: int
    snippet: str
    overflow: bool
    context_padding: int


def _build_snippet_window(
    *,
    clause_text: str,
    sentences: Sequence[Sentence],
    highlight_spans: Sequence[Tuple[int, int]],
    target_min: int,
    target_max: int,
) -> SnippetWindow:
    text_length = len(clause_text)
    if not sentences:
        sentences = [Sentence(0, text_length)]
    highlight_sentences = _sentences_covering_highlights(sentences, highlight_spans)
    if not highlight_sentences:
        core_start_idx = 0
        core_end_idx = 0
    else:
        core_start_idx = min(highlight_sentences)
        core_end_idx = max(highlight_sentences)
    start_idx = max(0, core_start_idx - CONTEXT_SENTENCE_PADDING)
    end_idx = min(len(sentences) - 1, core_end_idx + CONTEXT_SENTENCE_PADDING)

    snippet_start = sentences[start_idx].start
    snippet_end = sentences[end_idx].end
    snippet = clause_text[snippet_start:snippet_end]

    while len(snippet) < target_min and (start_idx > 0 or end_idx < len(sentences) - 1):
        expanded = False
        if start_idx > 0:
            start_idx -= 1
            expanded = True
        if len(snippet) < target_min and end_idx < len(sentences) - 1:
            end_idx += 1
            expanded = True
        snippet_start = sentences[start_idx].start
        snippet_end = sentences[end_idx].end
        snippet = clause_text[snippet_start:snippet_end]
        if not expanded:
            break

    overflow = False
    while len(snippet) > target_max and (start_idx < core_start_idx or end_idx > core_end_idx):
        trimmed = False
        if end_idx > core_end_idx and len(snippet) > target_max:
            candidate = end_idx - 1
            if candidate >= core_end_idx:
                end_idx = candidate
                trimmed = True
        if len(snippet) > target_max and start_idx < core_start_idx:
            candidate = start_idx + 1
            if candidate <= core_start_idx:
                start_idx = candidate
                trimmed = True
        snippet_start = sentences[start_idx].start
        snippet_end = sentences[end_idx].end
        snippet = clause_text[snippet_start:snippet_end]
        if not trimmed:
            break
        overflow = True

    snippet_start = max(0, min(snippet_start, text_length))
    snippet_end = max(snippet_start, min(snippet_end, text_length))
    snippet = clause_text[snippet_start:snippet_end]

    context_padding = max(core_start_idx - start_idx, end_idx - core_end_idx, 0)

    return SnippetWindow(
        start=snippet_start,
        end=snippet_end,
        sent_start_idx=start_idx,
        sent_end_idx=end_idx,
        snippet=snippet,
        overflow=overflow or len(snippet) > target_max,
        context_padding=context_padding,
    )


def _sentences_covering_highlights(
    sentences: Sequence[Sentence],
    highlight_spans: Sequence[Tuple[int, int]],
) -> List[int]:
    covered: List[int] = []
    for idx, sentence in enumerate(sentences):
        for span in highlight_spans:
            if sentence.intersects(span):
                covered.append(idx)
                break
    return covered


def _merge_spans(spans: Sequence[Tuple[int, int]], length: int) -> List[Tuple[int, int]]:
    cleaned = []
    for start, end in spans:
        start = max(0, min(start, length))
        end = max(start, min(end, length))
        if start == end:
            continue
        cleaned.append((start, end))
    if not cleaned:
        return []
    cleaned.sort(key=lambda pair: pair[0])
    merged: List[Tuple[int, int]] = []
    cur_start, cur_end = cleaned[0]
    for start, end in cleaned[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


def _resolve_sentences(clause: NormClause) -> List[Sentence]:
    if clause.sent_boundaries:
        sentences: List[Sentence] = []
        for start, end in clause.sent_boundaries:
            start = max(0, min(start, len(clause.text)))
            end = max(start, min(end, len(clause.text)))
            if start == end:
                continue
            sentences.append(Sentence(start, end))
        if sentences:
            return sentences
    return _heuristic_sentence_boundaries(clause.text)


def _heuristic_sentence_boundaries(text: str) -> List[Sentence]:
    boundaries: List[Sentence] = []
    start = 0
    idx = 0
    length = len(text)
    while idx < length:
        char = text[idx]
        if char in ".!?":
            lookahead = idx + 1
            while lookahead < length and text[lookahead] in '\"\\\')]}':
                lookahead += 1
            end = lookahead
            boundaries.append(Sentence(start, end))
            idx = end
            while idx < length and text[idx].isspace() and text[idx] != '\n':
                idx += 1
            start = idx
        elif char == '\n':
            newline_block_end = idx
            while newline_block_end < length and text[newline_block_end] in '\r\n':
                newline_block_end += 1
            if newline_block_end - idx >= 2:
                end = idx
                if end > start:
                    boundaries.append(Sentence(start, end))
                start = newline_block_end
            idx = newline_block_end
        else:
            idx += 1
    if start < length:
        boundaries.append(Sentence(start, length))

    cleaned: List[Sentence] = []
    for sentence in boundaries:
        seg = text[sentence.start:sentence.end]
        if not seg.strip():
            continue
        leading = 0
        while sentence.start + leading < sentence.end and text[sentence.start + leading].isspace():
            leading += 1
        trailing = 0
        while sentence.end - trailing - 1 >= sentence.start and text[sentence.end - trailing - 1].isspace():
            trailing += 1
        cleaned.append(
            Sentence(
                sentence.start + leading,
                max(sentence.start + leading, sentence.end - trailing),
            )
        )
    if not cleaned:
        cleaned.append(Sentence(0, length))
    return cleaned


def _relativize_highlights(
    snippet_start: int,
    spans: Sequence[Tuple[int, int]],
    snippet_length: int,
) -> List[Tuple[int, int]]:
    snippet_end = snippet_start + snippet_length
    highlights: List[Tuple[int, int]] = []
    for start, end in spans:
        clipped_start = max(start, snippet_start)
        clipped_end = min(end, snippet_end)
        if clipped_start >= clipped_end:
            continue
        highlights.append((clipped_start - snippet_start, clipped_end - snippet_start))
    return highlights


def _redact_snippet(snippet: str) -> Tuple[str, bool]:
    if not snippet:
        return snippet, False
    chars = list(snippet)
    mask = [False] * len(chars)
    for pattern in SENSITIVE_PATTERNS:
        for match in pattern.finditer(snippet):
            for idx in range(match.start(), match.end()):
                mask[idx] = True
    if not any(mask):
        return snippet, False
    idx = 0
    while idx < len(chars):
        if mask[idx]:
            block_start = idx
            while idx < len(chars) and mask[idx]:
                chars[idx] = "*"
                idx += 1
            block_len = idx - block_start
            if block_len < 4:
                for offset in range(block_len, 4):
                    insert_pos = min(block_start + offset, len(chars) - 1)
                    chars[insert_pos] = "*"
        else:
            idx += 1
    return "".join(chars), True


def _read_json(path: Path):
    with path.open("r", encoding=_UTF8_SIG) as stream:
        return json.load(stream)


__all__ = [
    "ClauseNotFoundError",
    "DEFAULT_MAX_LENGTH",
    "DEFAULT_MIN_LENGTH",
    "extract_evidence",
    "load_clauses",
    "load_hits",
]

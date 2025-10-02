from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .schemas import Clause


_CIRCLED_TO_INT: Dict[str, int] = {chr(code): idx for idx, code in enumerate(range(0x2460, 0x2474), start=1)}
_HANGUL_SEQUENCE = "\uac00\ub098\ub2e4\ub77c\ub9c8\uc0ac\uc544\uc790\ucc28\uce74\ud0c0\ud30c\ud558"

_ARTICLE_PREFIX_RE = re.compile(
    r"^제\s*(?P<number>\d+)\s*조\s*(?:[\(\[\{（［｟「『](?P<title>[^\)\]\}）］｠」』]+)[\)\]\}）］｠」』])?",
)

_PARAGRAPH_PREFIX_RE = re.compile(
    r"^(?P<marker>\(\d+\)|\d+\)|\d+\.\s?|\d+-|[\u2460-\u2473]|제\s*\d+\s*항)",
)

_ITEM_PREFIX_RE = re.compile(r"^(?P<marker>[가-하])[\.\)]")

_MARKER_SEARCH_RE = re.compile(
    r"(\(\d+\)|\d+\)|\d+\.\s?|\d+-|[\u2460-\u2473]|제\s*\d+\s*항|[가-하][\.\)])",
)

_LAW_REF_RE = re.compile(r"제\s*\d+\s*조")
_LAW_NAME_RE = re.compile(r"(민법|주택임대차보호법|상가건물\s*임대차보호법)")
_ANNEX_KEYWORDS = ["부속서", "별첨", "부록", "시방서", "비품목록", "시설물", "목록"]
_PARTY_ALIAS = {"갑": "GAP", "을": "EUL", "병": "BYEONG", "정": "JEONG"}

_HINT_KEYWORDS: Dict[str, Iterable[str]] = {
    "lease_hint_deposit": ["\ubcf4\uc99d\uae08", "\uc784\ub300\ubcf4\uc99d\uae08", "\uc804\uc138\ubcf4\uc99d\uae08", "\ubcf4\uc99d\uae08 \ubc18\ud658"],
    "lease_hint_rent": ["\ucc28\uc784", "\uc6d4\uc138", "\uc784\ub300\ub8cc", "\uc5f0\uccb4", "\uc5f0\uccb4\ub8cc"],
    "lease_hint_period": ["\uc784\ub300\uae30\uac04", "\uac1c\uc2dc\uc77c", "\ub9cc\ub8cc\uc77c", "\uae30\uac04", "\uc885\ub8cc\uc77c"],
    "lease_hint_renewal": ["\uac31\uc2e0", "\uc7ac\uacc4\uc57d", "\uac31\uc2e0\uc694\uad6c\uad8c", "\uc790\ub3d9\uac31\uc2e0"],
    "lease_hint_repair": ["\uc218\uc120", "\uc218\ub9ac", "\ubcf4\uc218", "\ud558\uc790", "\uc720\uc9c0\ubcf4\uc218"],
    "lease_hint_restore": ["\uc6d0\uc0c1\ubcf5\uad6c", "\ubcf5\uad6c", "\uc6d0\uc0c1\ud68c\ubcf5"],
    "lease_hint_sublease": ["\uc804\ub300", "\uc7ac\uc784\ub300", "\uc591\ub3c4", "\uc804\ub300\ucc28"],
    "lease_hint_mgmtfee": ["\uad00\ub9ac\ube44", "\uacf5\uc6a9\uc804\uae30", "\uccad\uc18c", "\uacbd\ube44", "\uc2b9\uac15\uae30\uc720\uc9c0"],
    "lease_hint_utilities": ["\uc804\uae30", "\uc218\ub3c4", "\uac00\uc2a4", "\ub3c4\uc2dc\uac00\uc2a4", "\ub09c\ubc29", "\ud1b5\uc2e0\uc694\uae08"],
    "lease_hint_termination": ["\ud574\uc81c", "\ud574\uc9c0", "\uc190\ud574\ubc30\uc0c1", "\uc704\uc57d\uae08", "\ud1b5\uc9c0", "\ucd5c\uace0"],
    "lease_hint_payment": ["\uc9c0\uae09", "\uc1a1\uae08", "\uacc4\uc88c", "\uc785\uae08", "\uc608\uae08\uc8fc"],
    "lease_hint_premises": ["\uc8fc\uc18c", "\uce35", "\ud638", "\uc9c0\ubc88", "\uac74\ubb3c", "\uba74\uc801", "\uc81c\uacf1", "\ud3c9"],
    "lease_hint_inventory": ["\ube44\ud488", "\uc7a5\ube44", "\ubaa9\ub85d", "\uc2dc\uc124"],
    "lease_hint_special": ["\ud2b9\uc57d", "\ud2b9\ubcc4", "\ucd94\uac00\uc870\uac74"],
}


@dataclass(slots=True)
class _OpenClause:
    level: int
    id: str
    start: int
    index_path: List[str]
    tags: Set[str] = field(default_factory=set)
    title: Optional[str] = None


class ClauseSegmenter:
    """Deterministic state-machine segmenter for Korean lease contracts."""

    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._text: str = ""
        self._clauses: List[Clause] = []
        self._open: Dict[int, _OpenClause] = {}
        self._article_no: Optional[str] = None
        self._paragraph_no: Optional[str] = None
        self._paragraph_seq: Dict[str, int] = {}
        self._item_seq: Dict[Tuple[str, str], int] = {}

    def segment(self, text: str) -> List[Clause]:
        """Split *text* into Clause objects."""

        self._reset()
        if text is None:
            return []

        canonical = text.replace("\r\n", "\n").replace("\r", "\n")
        self._text = canonical
        if not canonical:
            return []

        offset = 0
        for chunk in canonical.splitlines(keepends=True):
            line = chunk[:-1] if chunk.endswith("\n") else chunk
            line_start = offset
            stripped = line.strip()
            leading_removed = line.lstrip()
            leading_offset = line_start + (len(line) - len(leading_removed))

            if stripped:
                article_match = _ARTICLE_PREFIX_RE.match(leading_removed)
                if article_match:
                    tail = leading_removed[article_match.end():]
                    base_offset = leading_offset + article_match.end()
                    next_offset = self._start_article(leading_offset, article_match, tail, base_offset)
                    consumed = next_offset - base_offset
                    remaining_tail = tail[consumed:]
                    self._process_inline_markers(remaining_tail, next_offset)
                else:
                    if self._article_no is None and -1 not in self._open:
                        self._start_preface(leading_offset)
                    self._process_inline_markers(leading_removed, leading_offset)

            offset += len(chunk)

        for level in sorted(self._open.keys(), reverse=True):
            self._flush_level(level, len(self._text))

        return self._clauses

    def _start_preface(self, start: int) -> None:
        self._open[-1] = _OpenClause(
            level=-1,
            id="PREFACE",
            start=start,
            index_path=["PREFACE"],
            tags={"preface"},
        )

    def _start_article(
        self,
        start: int,
        match: re.Match[str],
        tail: str,
        tail_offset: int,
    ) -> int:
        number = match.group("number")
        number = str(int(number)) if number else "0"
        title = match.group("title")
        consumed = 0
        if not title:
            title, consumed = self._extract_inline_title(tail)
        else:
            consumed = len(tail) - len(tail.lstrip())
        remaining_offset = tail_offset + consumed

        self._flush_level(-1, start)
        self._flush_from_level(0, start)

        clause_id = f"A{number}"
        open_clause = _OpenClause(
            level=0,
            id=clause_id,
            start=start,
            index_path=[number],
            tags={"article"},
            title=title.strip() if title else None,
        )
        if title:
            open_clause.tags.add("has_title")
        self._open[0] = open_clause
        self._article_no = number
        self._paragraph_no = None
        self._paragraph_seq[number] = 0

        return remaining_offset

    def _process_inline_markers(self, text: str, absolute_start: int) -> None:
        stripped = text.lstrip()
        consumed = len(text) - len(stripped)
        start = absolute_start + consumed
        if not stripped:
            return

        paragraph_match = _PARAGRAPH_PREFIX_RE.match(stripped)
        if paragraph_match:
            marker = paragraph_match.group("marker")
            para_start = start + paragraph_match.start()
            self._start_paragraph(para_start, marker)
            tail = stripped[paragraph_match.end():]
            tail_offset = para_start + paragraph_match.end()
            self._process_inline_markers(tail, tail_offset)
            return

        item_match = _ITEM_PREFIX_RE.match(stripped)
        if item_match:
            marker = item_match.group("marker")
            item_start = start + item_match.start()
            self._start_item(item_start, marker)
            tail = stripped[item_match.end():]
            tail_offset = item_start + item_match.end()
            self._process_inline_markers(tail, tail_offset)

    def _start_paragraph(self, start: int, marker: str) -> None:
        if self._article_no is None:
            self._article_no = "0"
            self._open[0] = _OpenClause(
                level=0,
                id="A0",
                start=start,
                index_path=["0"],
                tags={"article", "synthetic"},
            )

        self._flush_from_level(1, start)

        normalized = self._normalise_paragraph_marker(marker)
        clause_id = f"A{self._article_no}-{normalized}"
        index_path = [self._article_no, normalized]
        open_clause = _OpenClause(
            level=1,
            id=clause_id,
            start=start,
            index_path=index_path,
            tags={"paragraph", f"marker:{marker}"},
        )
        self._open[1] = open_clause
        self._paragraph_no = normalized
        self._item_seq[(self._article_no, normalized)] = 0

    def _start_item(self, start: int, marker: str) -> None:
        if self._paragraph_no is None:
            self._start_paragraph(start, "1")

        self._flush_from_level(2, start)

        normalized = self._normalise_item_marker(marker)
        clause_id = f"A{self._article_no}-{self._paragraph_no}-{normalized}"
        index_path = [self._article_no, self._paragraph_no, normalized]
        open_clause = _OpenClause(
            level=2,
            id=clause_id,
            start=start,
            index_path=index_path,
            tags={"item", f"marker:{marker}"},
        )
        self._open[2] = open_clause

    def _flush_from_level(self, level: int, end: int) -> None:
        for lvl in sorted(list(self._open.keys()), reverse=True):
            if lvl >= level:
                self._flush_level(lvl, end)

    def _flush_level(self, level: int, end: int) -> None:
        clause_meta = self._open.pop(level, None)
        if clause_meta is None:
            return

        block = self._text[clause_meta.start:end]
        stripped_block = block.strip()
        if not stripped_block:
            if level == 0:
                self._article_no = None
                self._paragraph_no = None
            elif level == 1:
                self._paragraph_no = None
            return

        inner_offset = block.find(stripped_block)
        start = clause_meta.start + inner_offset
        clause_text = stripped_block
        clause_end = start + len(clause_text)

        tags = set(clause_meta.tags)
        tags.update(self._infer_tags(clause_text, clause_meta))

        clause = Clause(
            id=clause_meta.id,
            level=clause_meta.level,
            index_path=list(clause_meta.index_path),
            start=start,
            end=clause_end,
            text=clause_text,
            tags=sorted(tags),
            title=clause_meta.title,
        )
        self._clauses.append(clause)

        if level == 0:
            self._article_no = None
            self._paragraph_no = None
        elif level == 1:
            self._paragraph_no = None

    def _extract_inline_title(self, tail: str) -> Tuple[Optional[str], int]:
        if not tail:
            return None, 0
        leading_ws = len(tail) - len(tail.lstrip())
        trimmed = tail.lstrip()
        if not trimmed:
            return None, leading_ws
        if _PARAGRAPH_PREFIX_RE.match(trimmed) or _ITEM_PREFIX_RE.match(trimmed):
            return None, leading_ws
        marker_match = _MARKER_SEARCH_RE.search(trimmed)
        if marker_match:
            candidate = trimmed[: marker_match.start()].strip()
            consumed = leading_ws + marker_match.start()
        else:
            candidate = trimmed.strip()
            consumed = len(tail)
        if candidate and len(candidate) <= 30:
            return candidate, consumed
        return None, leading_ws

    def _normalise_paragraph_marker(self, marker: str) -> str:
        marker = marker.strip()
        parsed: Optional[int] = None
        circled = _CIRCLED_TO_INT.get(marker)
        if circled is not None:
            parsed = circled
        elif marker.startswith("제") and marker.endswith("항"):
            digits = re.findall(r"\d+", marker)
            if digits:
                parsed = int(digits[0])
        else:
            m = re.match(r"\(?\s*(\d+)\s*[\)\.-]?", marker)
            if m:
                parsed = int(m.group(1))
        article_key = self._article_no or "0"
        article_seq = self._paragraph_seq.get(article_key, 0)
        if parsed is None:
            parsed = article_seq + 1
        self._paragraph_seq[article_key] = max(article_seq, parsed)
        return str(parsed)

    def _normalise_item_marker(self, marker: str) -> str:
        marker = marker.strip()
        key = (self._article_no or "0", self._paragraph_no or "1")
        seq_value = self._item_seq.get(key, 0)
        char = marker[0]
        if char in _HANGUL_SEQUENCE:
            index = _HANGUL_SEQUENCE.index(char) + 1
            self._item_seq[key] = max(seq_value, index)
            return char
        index = seq_value + 1
        self._item_seq[key] = index
        fallback_index = (index - 1) % len(_HANGUL_SEQUENCE)
        return _HANGUL_SEQUENCE[fallback_index]

    def _infer_tags(self, text: str, clause_meta: _OpenClause) -> Set[str]:
        tags: Set[str] = set()
        for tag, keywords in _HINT_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                tags.add(tag)
        if any(keyword in text for keyword in _ANNEX_KEYWORDS):
            tags.add("annex_ref")
            tags.add("lease_hint_inventory")
        if _LAW_REF_RE.search(text) or _LAW_NAME_RE.search(text):
            tags.add("cross_ref")
        for alias, english in _PARTY_ALIAS.items():
            if alias in text and ((alias + "(") in text or (alias + " ") in text):
                tags.add(f"party_alias:{english}")
        if clause_meta.title and clause_meta.title in text:
            tags.add("title_in_text")
        return tags


def segment_text(text: str) -> List[Clause]:
    """Helper for functional style usage."""

    return ClauseSegmenter().segment(text)


__all__ = ["ClauseSegmenter", "segment_text"]

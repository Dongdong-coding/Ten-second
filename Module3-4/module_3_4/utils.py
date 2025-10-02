from __future__ import annotations

"""Utility helpers for the Module 3-4 execution engine."""

import re
from typing import Iterator, List, Sequence, Tuple

_NUMERIC_TOKEN = re.compile(r"(?<![\w.])(\d+[\d,\.]*)(?![\w.])")
_PERCENT_TOKEN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_CURRENCY_SUFFIX = re.compile(r"(\uB9CC\uC6D0|\uC5B5\uC6D0|KRW|\uC6D0)")

def safe_lower(text: str) -> str:
    return text.lower() if text else ""

def sentence_chunks(text: str) -> List[str]:
    if not text:
        return []
    splits = re.split(r"(?<=[.!?])\s+", text)
    return [chunk.strip() for chunk in splits if chunk.strip()]

def gather_snippet(text: str, spans: Sequence[Tuple[int, int]], window: int = 80) -> str:
    if not spans:
        return text[:window].strip()
    start = max(0, spans[0][0] - window // 2)
    end = min(len(text), spans[-1][1] + window // 2)
    snippet = text[start:end].strip()
    return snippet

def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))

def extract_numeric_tokens(text: str) -> List[float]:
    values: List[float] = []
    for match in _NUMERIC_TOKEN.finditer(text or ""):
        token = match.group(1)
        cleaned = token.replace(",", "")
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    return values

def extract_percentage_tokens(text: str) -> List[float]:
    values: List[float] = []
    for match in _PERCENT_TOKEN.finditer(text or ""):
        try:
            values.append(float(match.group(1)) / 100.0)
        except ValueError:
            continue
    return values

def infer_currency_multiplier(text: str) -> float:
    """Maps Korean suffixes (\uB9CC\uC6D0 = 10k) to numeric multipliers."""
    if not text:
        return 1.0
    suffix_match = _CURRENCY_SUFFIX.search(text)
    if not suffix_match:
        return 1.0
    suffix = suffix_match.group(1)
    if suffix == "\uB9CC\uC6D0":
        return 10_000.0
    if suffix == "\uC5B5\uC6D0":
        return 100_000_000.0
    return 1.0

def expand_numeric_value(raw: float, suffix_multiplier: float) -> float:
    return raw * suffix_multiplier

def rolling_window(tokens: Sequence[str], size: int) -> Iterator[Sequence[str]]:
    if size <= 0:
        return iter(())
    for index in range(len(tokens) - size + 1):
        yield tokens[index : index + size]

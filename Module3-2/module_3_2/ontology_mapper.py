from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .schemas import Clause, DefinitionBinding, NormClause

PARTICLE_SUFFIXES = [
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "와",
    "과",
    "의",
    "도",
    "으로",
    "로",
    "에게",
    "에서",
    "부터",
    "까지",
    "께",
    "한테",
]

_ALIAS_PATTERN_FORWARD = re.compile(
    r"(?P<base>[가-힣A-Za-z0-9\s]+?)\(\s*(?:이하\s*)?[\"'“”‘’《『]?(?P<alias>[가-힣A-Za-z0-9]+)[\"'“”‘’》』]?\s*(?:이라|라)\s*(?:한다|칭한다)\s*\)"
)
_ALIAS_PATTERN_REVERSE = re.compile(
    r"(?P<alias>[가-힣A-Za-z0-9]+)\(\s*(?:이하\s*)?[\"'“”‘’《『]?(?P<base>[가-힣A-Za-z0-9\s]+?)[\"'“”‘’》』]?\s*(?:이라|라)\s*(?:한다|칭한다)\s*\)"
)


@dataclass
class DefinitionTable:
    bindings: Dict[str, DefinitionBinding]

    def add(self, alias: str, base: str, clause_id: str) -> bool:
        alias = alias.strip()
        base = base.strip()
        if not alias or not base:
            return False
        binding = DefinitionBinding(alias=alias, base=base, source_clause_id=clause_id)
        existing = self.bindings.get(alias)
        if existing is None or len(base) > len(existing.base):
            self.bindings[alias] = binding
            return True
        return False

    def items(self) -> Iterable[DefinitionBinding]:
        return self.bindings.values()


def load_synonyms(path: Path) -> Dict[str, Dict[str, Iterable[str]]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    terms = data.get("terms", {})
    normalized: Dict[str, Dict[str, Iterable[str]]] = {}
    for code, payload in terms.items():
        canonical = str(payload.get("canonical", "")).strip()
        aliases = [canonical] + [str(alias).strip() for alias in payload.get("aliases", []) if str(alias).strip()]
        normalized[code] = {"canonical": canonical, "aliases": aliases}
    return normalized


def load_ontology(path: Path) -> Dict[str, List[Dict[str, object]]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def bind_definitions(clauses: Sequence[Clause]) -> Tuple[DefinitionTable, List[DefinitionBinding]]:
    table = DefinitionTable(bindings={})
    collected: List[DefinitionBinding] = []
    for clause in clauses:
        pairs = _extract_definition_pairs(clause.text)
        for base, alias in pairs:
            if table.add(alias, base, clause.id):
                collected.append(table.bindings[alias])
    return table, collected


def _extract_definition_pairs(text: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for match in _ALIAS_PATTERN_FORWARD.finditer(text):
        base = match.group("base").strip()
        alias = match.group("alias").strip()
        if not base or not alias:
            continue
        if len(alias) >= len(base):
            continue
        pairs.append((base, alias))
    for match in _ALIAS_PATTERN_REVERSE.finditer(text):
        base = match.group("base").strip()
        alias = match.group("alias").strip()
        if not base or not alias:
            continue
        if len(alias) >= len(base):
            continue
        pairs.append((base, alias))
    return pairs


def normalize_terms(
    text: str,
    definition_table: DefinitionTable,
    synonyms: Dict[str, Dict[str, Iterable[str]]],
) -> Tuple[str, List[str]]:
    normalized = text
    for binding in definition_table.items():
        normalized, _ = _replace_with_particles(normalized, binding.alias, binding.base)
    canonical_hits: Dict[str, int] = {}
    for code, entry in synonyms.items():
        canonical = entry.get("canonical", "")
        for alias in entry.get("aliases", []):
            normalized, count = _replace_with_particles(normalized, alias, canonical)
            if count:
                canonical_hits[code] = canonical_hits.get(code, 0) + count
    normalized = _collapse_whitespace(normalized)
    canonical_terms: set[str] = set(canonical_hits.keys())
    for code, entry in synonyms.items():
        canonical = entry.get("canonical", "")
        if canonical and canonical in normalized:
            canonical_terms.add(code)
    return normalized, sorted(canonical_terms)


def _replace_with_particles(text: str, alias: str, replacement: str) -> Tuple[str, int]:
    if not alias or alias == replacement:
        return text, 0
    suffix_pattern = "|".join(sorted(PARTICLE_SUFFIXES, key=len, reverse=True))
    pattern = re.compile(
        rf"{re.escape(alias)}(?P<particle>(?:{suffix_pattern})?)",
        flags=re.UNICODE,
    )
    occurrences = 0

    def _repl(match: re.Match[str]) -> str:
        nonlocal occurrences
        occurrences += 1
        particle = match.group("particle") or ""
        return f"{replacement}{particle}"

    return pattern.sub(_repl, text), occurrences


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_TAG_CATEGORY_MAP: Dict[str, Tuple[str, str]] = {
    "lease_hint_deposit": ("MONEY", "DEPOSIT"),
    "lease_hint_rent": ("MONEY", "RENT"),
    "lease_hint_late_fee": ("MONEY", "LATE_FEE"),
    "lease_hint_term": ("TERM", "PERIOD"),
    "lease_hint_renewal": ("TERM", "RENEWAL"),
    "lease_hint_termination": ("TERM", "TERMINATION"),
    "lease_hint_restore": ("USE_MAINT", "RESTORE"),
    "lease_hint_repair": ("USE_MAINT", "REPAIR"),
    "lease_hint_mgmt_fee": ("USE_MAINT", "MGMT_FEE"),
    "lease_hint_utilities": ("USE_MAINT", "UTILITIES"),
    "lease_hint_sublease": ("RIGHTS", "SUBLEASE_ASSIGN"),
    "lease_hint_premises": ("PREMISES", "PREMISES_DESC"),
    "lease_hint_inventory": ("PREMISES", "INVENTORY"),
    "lease_hint_law": ("LAW", "LAW"),
}


def map_category(
    clause: Clause,
    normalized_text: str,
    ontology: Dict[str, object],
) -> Tuple[str, Optional[str], List[str], List[Dict[str, object]]]:
    text = normalized_text
    title = clause.title or ""
    tags = clause.tags or []
    candidates: List[Tuple[str, str, float, List[str]]] = []
    ontology_categories = ontology.get("categories", [])

    for category in ontology_categories:
        cat_code = str(category.get("code", ""))
        cat_keywords = [str(kw) for kw in category.get("keywords", [])]
        subcategories = category.get("subcategories", [])
        for sub in subcategories:
            sub_code = str(sub.get("code", ""))
            sub_keywords = [str(kw) for kw in sub.get("keywords", [])]
            score = 0.0
            evidence: List[str] = []
            for keyword in sub_keywords:
                if keyword and keyword in title:
                    score += 3.0
                    if keyword not in evidence:
                        evidence.append(keyword)
                if keyword and keyword in text:
                    score += 2.0
                    if keyword not in evidence:
                        evidence.append(keyword)
            for keyword in cat_keywords:
                if keyword and keyword in title:
                    score += 1.0
                    if keyword not in evidence:
                        evidence.append(keyword)
                if keyword and keyword in text:
                    score += 1.0
                    if keyword not in evidence:
                        evidence.append(keyword)
            for tag in tags:
                mapped = _TAG_CATEGORY_MAP.get(tag)
                if mapped == (cat_code, sub_code):
                    score += 4.0
                    if tag not in evidence:
                        evidence.append(tag)
            if score > 0:
                candidates.append((cat_code, sub_code, score, evidence))

    candidates.sort(key=lambda item: item[2], reverse=True)
    formatted_candidates = [
        {
            "category": cat,
            "subcategory": sub,
            "score": round(score, 2),
            "evidence": evidence,
        }
        for cat, sub, score, evidence in candidates[:3]
    ]
    if not candidates:
        return "uncategorized", None, [], formatted_candidates

    best_cat, best_sub, _best_score, best_evidence = candidates[0]
    return best_cat, best_sub, best_evidence, formatted_candidates


def process(
    clauses: Sequence[Clause | Dict[str, object]],
    ontology: Dict[str, object],
    synonyms: Dict[str, Dict[str, Iterable[str]]],
) -> List[NormClause]:
    clause_objects: List[Clause] = [
        clause if isinstance(clause, Clause) else Clause.from_dict(clause)
        for clause in clauses
    ]
    definition_table, definition_bindings = bind_definitions(clause_objects)
    results: List[NormClause] = []
    for clause in clause_objects:
        normalized_text, canonical_terms = normalize_terms(
            clause.text,
            definition_table,
            synonyms,
        )
        category, subcategory, evidence_keywords, candidates = map_category(
            clause,
            normalized_text,
            ontology,
        )
        norm_clause = NormClause(
            id=clause.id,
            normalized_text=normalized_text,
            category=category,
            subcategory=subcategory,
            canonical_terms=list(dict.fromkeys(canonical_terms)),
            tags=list(dict.fromkeys(clause.tags)),
            def_bindings=list(definition_bindings),
            evidence_keywords=evidence_keywords,
            candidates=candidates,
        )
        results.append(norm_clause)
    return results


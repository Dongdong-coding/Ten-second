import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from module_3_2.ontology_mapper import load_ontology, load_synonyms, process
from module_3_2.schemas import Clause


FIXTURE_ROOT = ROOT


def _load_clauses() -> list[Clause]:
    sample_path = FIXTURE_ROOT / "samples" / "clauses_from_3_1.json"
    with sample_path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    return [Clause.from_dict(item) for item in data]


def test_process_creates_norm_clauses():
    clauses = _load_clauses()
    ontology = load_ontology(FIXTURE_ROOT / "data" / "ontology_lease.json")
    synonyms = load_synonyms(FIXTURE_ROOT / "data" / "synonyms_ko.json")

    results = process(clauses, ontology, synonyms)

    assert len(results) == 3

    deposit_clause = results[0]
    assert deposit_clause.category == "MONEY"
    assert deposit_clause.subcategory == "DEPOSIT"
    assert "DEPOSIT" in deposit_clause.canonical_terms
    assert any(binding.alias == "갑" and binding.base == "임대인" for binding in deposit_clause.def_bindings)

    rent_clause = results[1]
    assert rent_clause.category == "MONEY"
    assert rent_clause.subcategory == "RENT"
    assert "RENT" in rent_clause.canonical_terms
    assert "갑" not in rent_clause.normalized_text
    assert "임대인" in rent_clause.normalized_text

    renewal_clause = results[2]
    assert renewal_clause.category == "TERM"
    assert renewal_clause.subcategory == "RENEWAL"
    assert "RENEWAL" in renewal_clause.canonical_terms
    assert renewal_clause.evidence_keywords


@pytest.mark.parametrize(
    "text, expected",
    [
        ("임차인(이하 '을'이라 한다)", ("임차인", "을")),
        ("갑(이하 임대인이라 칭한다)", ("임대인", "갑")),
    ],
)
def test_definition_patterns(text: str, expected: tuple[str, str]):
    clause = Clause(id="test", index_path="0", text=text)
    ontology = load_ontology(FIXTURE_ROOT / "data" / "ontology_lease.json")
    synonyms = load_synonyms(FIXTURE_ROOT / "data" / "synonyms_ko.json")

    results = process([clause], ontology, synonyms)
    bindings = results[0].def_bindings
    assert any(binding.base == expected[0] and binding.alias == expected[1] for binding in bindings)

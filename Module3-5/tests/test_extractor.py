from pathlib import Path

from module_3_5.extractor import extract_evidence, load_clauses, load_hits


SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def _load_fixture():
    clauses = load_clauses(SAMPLES_DIR / "clauses.json")
    hits = load_hits(SAMPLES_DIR / "hits.json")
    return clauses, hits


def test_extracts_highlighted_snippet_respects_targets():
    clauses, hits = _load_fixture()
    evidences = extract_evidence(clauses, hits, target_min=80, target_max=180)

    assert len(evidences) == 2
    first = evidences[0].to_dict()
    assert first["snippet"].startswith("The tenant must remit rent")
    assert first["snippet_char_start_abs"] == 0
    assert first["snippet_char_end_abs"] == len(clauses["C-001"].text)
    assert first["highlights_rel"] == [[39, 69]]
    assert first["context_window_sentences"] == 1
    assert not first["overflow"]


def test_preserves_numeric_context_for_num_hits():
    clauses, hits = _load_fixture()
    evidences = extract_evidence(clauses, hits, target_min=40, target_max=120)

    numeric = next(ev for ev in evidences if ev.match_type == "num").to_dict()
    assert numeric["numeric_ctx"] == {
        "value": 0.1,
        "unit": "ratio",
        "comparator": "<=",
        "rhs_display": "10 percent",
    }
    assert numeric["highlights_rel"] == [[20, 23]]


def test_redaction_masks_sensitive_tokens():
    clauses, hits = _load_fixture()
    evidences = extract_evidence(clauses, hits, target_min=40, target_max=180, redact_sensitive=True)

    first = evidences[0].to_dict()
    assert "110-222-3333333" not in first["snippet"]
    assert "***" in first["snippet"] or "****" in first["snippet"]
    assert first["highlights_rel"] == [[39, 69]]
    assert "redacted_sensitive" in first["notes"]

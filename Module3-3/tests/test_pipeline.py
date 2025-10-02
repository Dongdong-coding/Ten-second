import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from module_3_3.exceptions import ValidationError
from module_3_3.pipeline import build_runtime_payload


SAMPLE = ROOT / "samples" / "demo_rules.json"


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8-sig"))


def test_build_runtime_payload(tmp_path):
    output = build_runtime_payload(SAMPLE, "1.0.0")
    assert output["metadata"]["ruleset_id"] == "lease-baseline"
    assert output["metadata"]["engine_version"] == "1.0.0"
    assert output["indexes"]["by_category"]["MONEY.DEPOSIT"] == ["MONEY_DEPOSIT_MINIMUM"]
    assert set(output["feature_requirements"]) == {"numeric_amount", "date_range"}
    assert output["metadata"]["checksum_sha256"]


def test_duplicate_rule_id_rejected(tmp_path):
    payload = load_sample()
    payload["rules"][1]["rule_id"] = payload["rules"][0]["rule_id"]
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        build_runtime_payload(rules_path, "1.0.0")


def test_engine_semver_mismatch(tmp_path):
    with pytest.raises(ValidationError):
        build_runtime_payload(SAMPLE, "2.0.0")


def test_experiment_allocation_must_sum_to_100(tmp_path):
    payload = load_sample()
    payload["experiment"]["variants"]["canary"] = 10
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        build_runtime_payload(rules_path, "1.0.0")


def test_flag_override_adjusts_variants(tmp_path):
    flags = {"experiment": {"variants": {"baseline": 40.0, "canary": 60.0}}}
    flags_path = tmp_path / "flags.json"
    flags_path.write_text(json.dumps(flags), encoding="utf-8")
    output = build_runtime_payload(SAMPLE, "1.0.0", flags_path)
    assert output["experiment"]["variants"]["canary"] == 60.0
    assert output["metadata"]["experiment_variants"] == ["baseline", "canary"]

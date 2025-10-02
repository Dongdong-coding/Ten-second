"""Compilation utilities for transforming specs into runtime payloads."""
from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Iterable, Mapping

from .models import (
    ActivationWindow,
    ExperimentAllocation,
    MatcherSpec,
    RuleSpec,
    RulesetSpec,
    RuntimeRule,
    RuntimeRuleset,
)
from .utils import sha256_digest, utc_now


def _activation_to_payload(activation: ActivationWindow) -> Dict[str, object]:
    payload: Dict[str, object] = {"status": activation.status}
    if activation.start_at:
        payload["start_at"] = activation.start_at.isoformat()
    if activation.end_at:
        payload["end_at"] = activation.end_at.isoformat()
    return payload


def _matcher_to_payload(matcher: MatcherSpec) -> Dict[str, object]:
    payload: Dict[str, object] = {"type": matcher.type, "pattern": matcher.pattern}
    if matcher.options:
        payload["options"] = dict(matcher.options)
    return payload


def _compile_rule(rule: RuleSpec) -> RuntimeRule:
    matcher_payloads = tuple(_matcher_to_payload(matcher) for matcher in rule.matchers)
    activation_payload = _activation_to_payload(rule.activation)
    return RuntimeRule(
        rule_id=rule.rule_id,
        version=rule.version,
        scope=dict(rule.scope),
        matcher_payloads=matcher_payloads,
        severity=rule.severity,
        weight=rule.weight,
        priority=rule.priority,
        evidence_hints=tuple(rule.evidence_hints),
        requires=tuple(rule.requires),
        flags=tuple(rule.flags),
        activation=activation_payload,
    )


def _compile_experiment(experiment: ExperimentAllocation | None) -> Dict[str, object] | None:
    if not experiment:
        return None
    payload: Dict[str, object] = {
        "variants": {name: round(weight, 6) for name, weight in experiment.variants.items()},
    }
    if experiment.sticky_scope:
        payload["sticky_scope"] = experiment.sticky_scope
    return payload


def _build_indexes(rules: Iterable[RuntimeRule]) -> Dict[str, Dict[str, list[str]]]:
    by_category: Dict[str, list[str]] = {}
    by_flag: Dict[str, list[str]] = {}
    by_severity: Dict[str, list[str]] = {}

    for rule in rules:
        category = rule.scope.get("category")
        if isinstance(category, str) and category:
            by_category.setdefault(category, []).append(rule.rule_id)
        for flag in rule.flags:
            by_flag.setdefault(flag, []).append(rule.rule_id)
        by_severity.setdefault(rule.severity, []).append(rule.rule_id)

    for mapping in (by_category, by_flag, by_severity):
        for key, values in mapping.items():
            mapping[key] = sorted(values)

    return {"by_category": by_category, "by_flag": by_flag, "by_severity": by_severity}


def compile_ruleset(spec: RulesetSpec, engine_version: str) -> RuntimeRuleset:
    compiled_rules = tuple(_compile_rule(rule) for rule in spec.rules)
    indexes = _build_indexes(compiled_rules)
    feature_requirements = {
        rule.rule_id: tuple(rule.requires)
        for rule in compiled_rules
        if rule.requires
    }
    experiment_payload = _compile_experiment(spec.experiment)

    metadata = {
        "ruleset_id": spec.metadata.ruleset_id,
        "ruleset_version": spec.metadata.version,
        "compiled_at": utc_now().isoformat(),
        "engine_version": engine_version,
        "engine_range": {
            "min": spec.metadata.engine_range.minimum,
            "max": spec.metadata.engine_range.maximum,
        },
        "description": spec.metadata.description,
    }
    if experiment_payload:
        metadata["experiment_variants"] = sorted(experiment_payload["variants"].keys())
    metadata.setdefault("mediation_table", {})

    runtime = RuntimeRuleset(
        metadata=metadata,
        indexes=indexes,
        rules=compiled_rules,
        feature_requirements=feature_requirements,
        experiment=experiment_payload,
    )
    checksum_source = _canonicalize(runtime)
    metadata["checksum_sha256"] = sha256_digest(checksum_source)
    return runtime


def _canonicalize(runtime: RuntimeRuleset) -> bytes:
    """Return a deterministic byte representation for checksum purposes."""

    import json

    payload = {
        "metadata": runtime.metadata,
        "indexes": runtime.indexes,
        "rules": [
            {
                "rule_id": rule.rule_id,
                "version": rule.version,
                "scope": rule.scope,
                "matchers": list(rule.matcher_payloads),
                "severity": rule.severity,
                "weight": rule.weight,
                "priority": rule.priority,
                "evidence_hints": list(rule.evidence_hints),
                "requires": list(rule.requires),
                "flags": list(rule.flags),
                "activation": rule.activation,
            }
            for rule in runtime.rules
        ],
        "feature_requirements": {
            rule_id: list(requirements)
            for rule_id, requirements in runtime.feature_requirements.items()
        },
        "experiment": runtime.experiment,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

"""High-level orchestration for compiling rulesets."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from .compiler import compile_ruleset
from .exceptions import LoaderError, ValidationError
from .loader import load_ruleset
from .models import RulesetSpec, RuntimeRule
from .validators import validate_ruleset

_UTF8 = "utf-8"
_UTF8_SIG = "utf-8-sig"
_ALLOWED_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
_SEVERITY_SYNONYMS = {
    "OK": "LOW",
    "INFO": "LOW",
    "WARN": "MEDIUM",
    "WARNING": "MEDIUM",
    "ALERT": "HIGH",
}


def _apply_flag_overrides(spec: RulesetSpec, flag_payload: Mapping[str, Any]) -> RulesetSpec:
    experiment_override = flag_payload.get("experiment")
    if not experiment_override or not spec.experiment:
        return spec
    variants_override = experiment_override.get("variants")
    merged_variants = dict(spec.experiment.variants)
    if variants_override:
        try:
            override_casted = {str(name): float(weight) for name, weight in variants_override.items()}
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid experiment override variants: {exc}") from exc
        merged_variants.update(override_casted)
    sticky_scope = experiment_override.get("sticky_scope", spec.experiment.sticky_scope)
    experiment = replace(spec.experiment, variants=merged_variants, sticky_scope=sticky_scope)
    return replace(spec, experiment=experiment)


def _normalise_severity(value: str) -> str:
    upper = str(value or "").upper()
    canonical = _SEVERITY_SYNONYMS.get(upper, upper)
    if canonical not in _ALLOWED_SEVERITIES:
        raise ValidationError(
            f"Unsupported severity '{value}'. Allowed severities: {sorted(_ALLOWED_SEVERITIES)}"
        )
    return canonical


def _clamp_weight(weight: float) -> float:
    try:
        numeric = float(weight)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Weight must be a number between 0 and 1, received {weight!r}") from exc
    return max(0.0, min(1.0, numeric))


def _normalise_scope(scope: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    category = scope.get("category")
    if isinstance(category, str) and category:
        payload["category"] = category
    subcategory = scope.get("subcategory")
    if isinstance(subcategory, str) and subcategory:
        payload["subcategory"] = subcategory
    tags: list[str] = []
    for key in ("tags", "canonical_terms", "labels"):
        values = scope.get(key)
        if isinstance(values, (list, tuple, set)):
            tags.extend(str(item) for item in values if item)
        elif isinstance(values, str) and values:
            tags.append(values)
    if tags:
        payload["tags"] = list(dict.fromkeys(tags))
    return payload


def _serialise_matchers(rule: RuntimeRule) -> dict[str, Any]:
    lexicon: list[str] = []
    regex: list[dict[str, str]] = []
    negations: list[str] = []
    proximity: dict[str, int] = {}

    for matcher in rule.matcher_payloads:
        m_type = str(matcher.get("type", "")).lower()
        pattern = str(matcher.get("pattern", "")).strip()
        options = matcher.get("options") or {}
        if not pattern:
            continue
        if options.get("negate") or options.get("negation"):
            negations.append(pattern)
            continue
        if m_type in {"keyword", "phrase"}:
            lexicon.append(pattern)
        elif m_type == "regex":
            flags = str(options.get("flags") or "i")
            regex.append({"pattern": pattern, "flags": flags})
        elif m_type == "negation":
            negations.append(pattern)
        elif m_type == "proximity":
            window = options.get("window")
            try:
                proximity["window"] = int(window)
            except (TypeError, ValueError):
                pass
        else:
            lexicon.append(pattern)
        if "window" in options and "window" not in proximity:
            try:
                proximity["window"] = int(options["window"])
            except (TypeError, ValueError):
                pass

    payload: dict[str, Any] = {}
    if lexicon:
        payload["lexicon"] = list(dict.fromkeys(lexicon))
    if regex:
        payload["regex"] = regex
    if negations:
        payload["negations"] = list(dict.fromkeys(negations))
    if proximity:
        payload["proximity"] = proximity
    return payload


def _serialise_flags(flags: Any) -> dict[str, Any] | None:
    if not flags:
        return None
    critical = any(str(flag).lower() == "critical" for flag in flags)
    return {"critical": True} if critical else None


def _serialise_activation(activation: Mapping[str, Any]) -> dict[str, Any]:
    if not activation:
        return {}
    payload: dict[str, Any] = {}
    status = activation.get("status")
    if status:
        payload["status"] = status
    variant = activation.get("variant") or activation.get("group")
    if variant:
        payload["variant"] = variant
    pct = activation.get("pct") or activation.get("percentage")
    try:
        if pct is not None:
            payload["pct"] = int(pct)
    except (TypeError, ValueError):
        pass
    return payload


def _build_indices(rules: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, list[str]] = {}
    by_flag: dict[str, list[str]] = {}
    by_severity: dict[str, list[str]] = {}

    for rule_id, payload in rules.items():
        scope = payload.get("scope", {})
        category = scope.get("category")
        if category:
            by_category.setdefault(category, []).append(rule_id)
        flags_payload = payload.get("flags") or {}
        if flags_payload.get("critical"):
            by_flag.setdefault("critical", []).append(rule_id)
        severity = payload.get("severity")
        if severity:
            by_severity.setdefault(severity, []).append(rule_id)

    for mapping in (by_category, by_flag, by_severity):
        for key, values in mapping.items():
            mapping[key] = sorted(dict.fromkeys(values))

    return {
        "by_category": by_category,
        "by_flag": by_flag,
        "by_severity": by_severity,
    }


def _serialize(runtime) -> dict[str, Any]:
    rules_payload: dict[str, dict[str, Any]] = {}
    for rule in runtime.rules:
        severity = _normalise_severity(rule.severity)
        scope_payload = _normalise_scope(rule.scope)
        matchers_payload = _serialise_matchers(rule)
        weight = _clamp_weight(rule.weight)
        flags_payload = _serialise_flags(rule.flags)
        requires = [str(req) for req in rule.requires if req]
        activation_payload = _serialise_activation(rule.activation)

        rule_payload: dict[str, Any] = {
            "rule_id": rule.rule_id,
            "version": rule.version,
            "severity": severity,
            "weight": weight,
            "priority": int(rule.priority),
            "scope": scope_payload,
            "matchers": matchers_payload,
        }
        if requires:
            rule_payload["requires"] = list(dict.fromkeys(requires))
        if flags_payload:
            rule_payload["flags"] = flags_payload
        if activation_payload:
            rule_payload["activation"] = activation_payload

        rules_payload[rule.rule_id] = rule_payload

    indices = _build_indices(rules_payload)

    metadata = dict(runtime.metadata)
    engine_semver = metadata.get("engine_version")

    return {
        "engine_semver": engine_semver,
        "metadata": metadata,
        "indices": indices,
        "rules": rules_payload,
        "feature_requirements": {
            key: list(values)
            for key, values in runtime.feature_requirements.items()
        },
        "experiment": dict(runtime.experiment) if runtime.experiment else None,
        "mediation_table": metadata.get("mediation_table", {}),
    }


def _validate_engine_range(spec: RulesetSpec, engine_version: str) -> None:
    if not spec.metadata.engine_range.contains(engine_version):
        minimum = spec.metadata.engine_range.minimum
        maximum = spec.metadata.engine_range.maximum or "*"
        raise ValidationError(
            f"Engine version {engine_version} outside allowed range {minimum}..{maximum}"
        )


def build_runtime_payload(
    rules_path: str | Path,
    engine_version: str,
    flags_path: str | Path | None = None,
) -> dict[str, Any]:
    """Produce a JSON-serialisable runtime payload."""

    spec = load_ruleset(rules_path)
    _validate_engine_range(spec, engine_version)

    if flags_path:
        try:
            payload = json.loads(Path(flags_path).read_text(encoding=_UTF8_SIG))
        except json.JSONDecodeError as exc:
            raise LoaderError(f"Invalid flag file JSON: {exc}") from exc
        spec = _apply_flag_overrides(spec, payload)

    validate_ruleset(spec, engine_version)
    runtime = compile_ruleset(spec, engine_version)
    return _serialize(runtime)
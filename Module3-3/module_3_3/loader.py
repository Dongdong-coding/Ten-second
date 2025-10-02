"""Load ruleset definitions from disk."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from .exceptions import LoaderError
from .models import (
    ACTIVATION_STATUSES,
    ExperimentAllocation,
    MatcherSpec,
    ActivationWindow,
    RuleSpec,
    RulesetMetadata,
    RulesetSpec,
    SemverRange,
)


ISO_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
]


def _parse_datetime(raw: str | None) -> datetime | None:
    if raw in (None, ""):
        return None
    for fmt in ISO_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise LoaderError(f"Unsupported datetime format: {raw}")


def _parse_activation(payload: Mapping[str, Any] | None) -> ActivationWindow:
    if not payload:
        return ActivationWindow()
    status = payload.get("status", "active")
    if status not in ACTIVATION_STATUSES:
        raise LoaderError(f"Unknown activation status '{status}'")
    start_at = _parse_datetime(payload.get("start_at"))
    end_at = _parse_datetime(payload.get("end_at"))
    return ActivationWindow(status=status, start_at=start_at, end_at=end_at)


def _parse_matchers(entries: Iterable[Mapping[str, Any]]) -> tuple[MatcherSpec, ...]:
    matchers: list[MatcherSpec] = []
    for entry in entries:
        matcher_type = entry.get("type")
        pattern = entry.get("pattern")
        options = entry.get("options", {})
        if not matcher_type or not pattern:
            raise LoaderError("Matcher requires both 'type' and 'pattern'")
        if not isinstance(options, Mapping):
            raise LoaderError("Matcher 'options' must be a mapping")
        matchers.append(MatcherSpec(type=str(matcher_type), pattern=str(pattern), options=dict(options)))
    if not matchers:
        raise LoaderError("Rule must define at least one matcher")
    return tuple(matchers)


def _parse_rule(payload: Mapping[str, Any]) -> RuleSpec:
    try:
        rule_id = str(payload["rule_id"])
        version = str(payload["version"])
        scope = dict(payload.get("scope", {}))
        matchers = _parse_matchers(payload.get("matchers", []))
        severity = str(payload.get("severity", "WARN"))
        weight = float(payload.get("weight", 1.0))
        priority = int(payload.get("priority", 100))
        evidence_hints = tuple(str(item) for item in payload.get("evidence_hints", []))
        requires = tuple(str(item) for item in payload.get("requires", []))
        flags = tuple(str(item) for item in payload.get("flags", []))
        activation = _parse_activation(payload.get("activation"))
    except KeyError as exc:
        raise LoaderError(f"Missing required rule key: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise LoaderError(f"Invalid rule field: {exc}") from exc
    return RuleSpec(
        rule_id=rule_id,
        version=version,
        scope=scope,
        matchers=matchers,
        severity=severity,
        weight=weight,
        priority=priority,
        evidence_hints=evidence_hints,
        requires=requires,
        flags=flags,
        activation=activation,
    )


def _parse_experiment(payload: Mapping[str, Any] | None) -> ExperimentAllocation | None:
    if not payload:
        return None
    variants = payload.get("variants")
    if not isinstance(variants, Mapping) or not variants:
        raise LoaderError("Experiment requires non-empty 'variants' mapping")
    try:
        casted = {str(name): float(value) for name, value in variants.items()}
    except (TypeError, ValueError) as exc:
        raise LoaderError("Experiment variant weights must be numeric") from exc
    sticky_scope = payload.get("sticky_scope")
    if sticky_scope is not None:
        sticky_scope = str(sticky_scope)
    return ExperimentAllocation(variants=casted, sticky_scope=sticky_scope)


def load_ruleset(path: str | Path) -> RulesetSpec:
    """Load a ruleset specification from *path*."""

    source = Path(path)
    if not source.exists():
        raise LoaderError(f"Ruleset file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise LoaderError(f"Invalid JSON in {source}: {exc}") from exc

    try:
        raw_meta = payload["ruleset"]
        raw_rules = payload["rules"]
    except KeyError as exc:
        raise LoaderError(f"Missing top-level key: {exc.args[0]}") from exc

    if not isinstance(raw_rules, list) or not raw_rules:
        raise LoaderError("'rules' must be a non-empty list")

    try:
        engine_range_payload = raw_meta["engine_semver"]
        semver_range = SemverRange(
            minimum=str(engine_range_payload["min"]),
            maximum=str(engine_range_payload.get("max")) if engine_range_payload.get("max") else None,
        )
        metadata = RulesetMetadata(
            ruleset_id=str(raw_meta["id"]),
            version=str(raw_meta["version"]),
            description=raw_meta.get("description"),
            engine_range=semver_range,
            engine_semver=str(raw_meta.get("engine")) if raw_meta.get("engine") else None,
        )
    except KeyError as exc:
        raise LoaderError(f"Missing metadata key: {exc.args[0]}") from exc

    rules = tuple(_parse_rule(entry) for entry in raw_rules)
    experiment = _parse_experiment(payload.get("experiment"))

    return RulesetSpec(metadata=metadata, rules=rules, experiment=experiment)

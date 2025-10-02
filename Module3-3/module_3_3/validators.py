"""Validation routines for the ruleset compiler."""
from __future__ import annotations

import re
from typing import Iterable

from .exceptions import ValidationError
from .models import (
    ACTIVATION_STATUSES,
    ALLOWED_MATCHER_TYPES,
    ExperimentAllocation,
    MatcherSpec,
    RuleSpec,
    RulesetSpec,
)
from .utils import ensure_allowed_scope

PATTERN_LENGTH_LIMIT = 512

_SEVERITY_CANONICAL = {
    "LOW": "LOW",
    "OK": "LOW",
    "INFO": "LOW",
    "WARN": "WARN",
    "WARNING": "WARN",
    "MEDIUM": "WARN",
    "HIGH": "HIGH",
    "ALERT": "HIGH",
    "CRITICAL": "CRITICAL",
}

def _validate_matchers(rule_id: str, matchers: Iterable[MatcherSpec]) -> None:
    seen = set()
    for matcher in matchers:
        if matcher.type not in ALLOWED_MATCHER_TYPES:
            raise ValidationError(f"{rule_id}: unsupported matcher type '{matcher.type}'")
        if len(matcher.pattern) > PATTERN_LENGTH_LIMIT:
            raise ValidationError(f"{rule_id}: matcher pattern exceeds {PATTERN_LENGTH_LIMIT} chars")
        key = (matcher.type, matcher.pattern)
        if key in seen:
            raise ValidationError(f"{rule_id}: duplicate matcher '{matcher.pattern}'")
        seen.add(key)
        if matcher.type == "regex":
            try:
                re.compile(matcher.pattern)
            except re.error as exc:
                raise ValidationError(f"{rule_id}: invalid regex '{matcher.pattern}': {exc}") from exc

def _validate_activation(rule: RuleSpec) -> None:
    status = rule.activation.status
    if status not in ACTIVATION_STATUSES:
        raise ValidationError(f"{rule.rule_id}: activation status '{status}' is not supported")
    start = rule.activation.start_at
    end = rule.activation.end_at
    if start and end and start >= end:
        raise ValidationError(f"{rule.rule_id}: activation end_at must be after start_at")

def _validate_experiment(experiment: ExperimentAllocation | None) -> None:
    if not experiment:
        return
    total = experiment.total_percentage()
    if abs(total - 100.0) > 1e-6:
        raise ValidationError(f"Experiment allocations must sum to 100, got {total}")
    for name, weight in experiment.variants.items():
        if weight <= 0:
            raise ValidationError(f"Experiment variant '{name}' weight must be positive")

def validate_ruleset(spec: RulesetSpec, engine_version: str) -> None:
    """Validate the supplied *spec* and raise :class:`ValidationError` on failure."""

    metadata = spec.metadata
    if not metadata.ruleset_id:
        raise ValidationError("Ruleset id is required")
    if not metadata.version:
        raise ValidationError("Ruleset version is required")
    try:
        engine_supported = metadata.engine_range.contains(engine_version)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not engine_supported:
        minimum = metadata.engine_range.minimum
        maximum = metadata.engine_range.maximum or "*"
        raise ValidationError(
            f"Engine version {engine_version} incompatible with ruleset range {minimum}..{maximum}"
        )

    seen_rule_ids: set[str] = set()
    categories_by_severity: dict[str, set[str]] = {}
    for rule in spec.rules:
        if rule.rule_id in seen_rule_ids:
            raise ValidationError(f"Duplicate rule_id '{rule.rule_id}'")
        seen_rule_ids.add(rule.rule_id)
        ensure_allowed_scope(rule.scope)

        canonical_severity = _SEVERITY_CANONICAL.get(rule.severity.upper())
        if canonical_severity is None:
            raise ValidationError(f"{rule.rule_id}: unknown severity '{rule.severity}'")

        if not (0.0 <= rule.weight <= 1.0):
            raise ValidationError(f"{rule.rule_id}: weight must be between 0 and 1")
        if rule.priority < 0:
            raise ValidationError(f"{rule.rule_id}: priority must be non-negative")

        _validate_matchers(rule.rule_id, rule.matchers)
        _validate_activation(rule)
        _ensure_scope_priority(rule, categories_by_severity, canonical_severity)
        _validate_requires(rule)

    _validate_experiment(spec.experiment)

def _ensure_scope_priority(rule: RuleSpec, matrix: dict[str, set[str]], severity: str) -> None:
    category = str(rule.scope.get("category", ""))
    if not category:
        return
    severity_slot = matrix.setdefault(category, set())
    fingerprint = f"{severity}:{rule.priority}"
    if fingerprint in severity_slot:
        raise ValidationError(
            f"{rule.rule_id}: category '{category}' already has severity/priority '{severity}/{rule.priority}'",
        )
    severity_slot.add(fingerprint)

def _validate_requires(rule: RuleSpec) -> None:
    for requirement in rule.requires:
        if not requirement or not requirement.strip():
            raise ValidationError(f"{rule.rule_id}: requires entries must be non-empty")
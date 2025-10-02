"""Data models for the Module3-3 ruleset compiler."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


ALLOWED_MATCHER_TYPES = {"keyword", "regex", "phrase"}
ALLOWED_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "WARN", "OK", "INFO", "ALERT"}
ACTIVATION_STATUSES = {"draft", "active", "paused", "retired"}


@dataclass(frozen=True)
class SemverRange:
    """Inclusive semantic version range."""

    minimum: str
    maximum: Optional[str] = None

    def contains(self, version: str) -> bool:
        """Return True if *version* falls inside the declared range."""

        def _normalize(tag: str) -> List[int]:
            parts = tag.split(".")
            if len(parts) != 3:
                raise ValueError(f"Semver '{tag}' must have major.minor.patch")
            try:
                return [int(p) for p in parts]
            except ValueError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Semver '{tag}' must contain integers") from exc

        target = _normalize(version)
        low = _normalize(self.minimum)
        if target < low:
            return False
        if self.maximum is None:
            return True
        high = _normalize(self.maximum)
        return target <= high


@dataclass(frozen=True)
class ExperimentAllocation:
    """Experiment variant allocation percentages."""

    variants: Mapping[str, float]
    sticky_scope: Optional[str] = None

    def total_percentage(self) -> float:
        return sum(self.variants.values())


@dataclass(frozen=True)
class ActivationWindow:
    status: str = "active"
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


@dataclass(frozen=True)
class MatcherSpec:
    """Matcher definition describing how the runtime should evaluate a rule."""

    type: str
    pattern: str
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleSpec:
    """High level rule specification as provided by policy authors."""

    rule_id: str
    version: str
    scope: Mapping[str, Any]
    matchers: Sequence[MatcherSpec]
    severity: str
    weight: float = 1.0
    priority: int = 100
    evidence_hints: Sequence[str] = field(default_factory=tuple)
    requires: Sequence[str] = field(default_factory=tuple)
    flags: Sequence[str] = field(default_factory=tuple)
    activation: ActivationWindow = field(default_factory=ActivationWindow)


@dataclass(frozen=True)
class RulesetMetadata:
    ruleset_id: str
    version: str
    description: Optional[str]
    engine_range: SemverRange
    checksum: Optional[str] = None
    engine_semver: Optional[str] = None


@dataclass(frozen=True)
class RulesetSpec:
    metadata: RulesetMetadata
    rules: Sequence[RuleSpec]
    experiment: Optional[ExperimentAllocation]


@dataclass(frozen=True)
class RuntimeRule:
    rule_id: str
    version: str
    scope: Mapping[str, Any]
    matcher_payloads: Sequence[Mapping[str, Any]]
    severity: str
    weight: float
    priority: int
    evidence_hints: Sequence[str]
    requires: Sequence[str]
    flags: Sequence[str]
    activation: Mapping[str, Any]


@dataclass(frozen=True)
class RuntimeRuleset:
    metadata: Mapping[str, Any]
    indexes: Mapping[str, Any]
    rules: Sequence[RuntimeRule]
    feature_requirements: Mapping[str, Sequence[str]]
    experiment: Optional[Mapping[str, Any]] = None

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Set

from .schemas import CalibrationSettings


@dataclass(frozen=True)
class CalibrationClause:
    clause_id: str
    confidence: float
    metadata: Dict[str, object] = field(default_factory=dict)


class ThresholdCalibrator:
    def __init__(self, settings: CalibrationSettings) -> None:
        self.settings = settings

    def calibrate(
        self,
        clauses: Sequence[CalibrationClause],
        thresholds: Dict[str, float],
    ) -> tuple[float, Set[str]]:
        warn_threshold = self._choose_warn_threshold(clauses, thresholds)
        demotions: Set[str] = set()
        if self.settings.demote_high_to_warn:
            demotions = self._find_demotions(clauses, thresholds.get("HIGH", 0.99))
        return warn_threshold, demotions

    def _choose_warn_threshold(
        self,
        clauses: Sequence[CalibrationClause],
        thresholds: Dict[str, float],
    ) -> float:
        base_warn = thresholds.get("WARN", 0.10)
        min_warn = self.settings.min_warn
        max_warn = self.settings.max_warn
        if not clauses or not self.settings.enable or min_warn >= max_warn:
            return _clamp(base_warn, min_warn, max_warn)

        high_threshold = thresholds.get("HIGH", 0.99)
        ambig_gap = thresholds.get("ambig_gap", 0.08)
        base_warn = _clamp(base_warn, min_warn, max_warn)

        candidates: List[float] = [base_warn, min_warn, max_warn]
        for clause in clauses:
            confidence = clause.confidence
            if confidence >= high_threshold:
                continue
            candidates.append(_clamp(confidence, min_warn, max_warn))
            candidates.append(_clamp(confidence + 1e-6, min_warn, max_warn))

        seen = set()
        unique_candidates: List[float] = []
        for candidate in candidates:
            key = round(candidate, 6)
            if key in seen:
                continue
            seen.add(key)
            unique_candidates.append(candidate)

        target = self.settings.target_warn_rate
        best_threshold = base_warn
        best_score = (float("inf"), float("inf"), float("inf"))

        for candidate in unique_candidates:
            warn_rate = _warn_rate(clauses, candidate, high_threshold, ambig_gap)
            distance = abs(warn_rate - target)
            jitter = abs(candidate - base_warn)
            score = (distance, jitter, candidate)
            if score < best_score:
                best_score = score
                best_threshold = candidate

        return _clamp(best_threshold, min_warn, max_warn)

    def _find_demotions(
        self,
        clauses: Sequence[CalibrationClause],
        high_threshold: float,
    ) -> Set[str]:
        flag_name = self.settings.critical_flag
        demotions: Set[str] = set()
        for clause in clauses:
            confidence = clause.confidence
            if confidence < high_threshold:
                continue
            flags = clause.metadata.get("flags", {}) if clause.metadata else {}
            is_critical = bool(flags.get(flag_name))
            if not is_critical:
                demotions.add(clause.clause_id)
        return demotions


def _warn_rate(
    clauses: Sequence[CalibrationClause],
    warn_threshold: float,
    high_threshold: float,
    ambig_gap: float,
) -> float:
    warn = high = ok = 0
    warn_cutoff = warn_threshold + max(ambig_gap, 0.0)
    for clause in clauses:
        confidence = clause.confidence
        if confidence >= high_threshold:
            high += 1
        elif confidence >= warn_cutoff:
            warn += 1
        else:
            ok += 1
    denom = warn + high + ok
    if denom == 0:
        return 0.0
    return warn / denom


def _clamp(value: float, lower: float, upper: float) -> float:
    if lower > upper:
        return value
    return max(lower, min(value, upper))


__all__ = ["CalibrationClause", "ThresholdCalibrator"]

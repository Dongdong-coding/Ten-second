from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

from .calibrator import CalibrationClause, ThresholdCalibrator
from .risk_scorer import ClauseComputation
from .schemas import ClauseScore, Policy


class Aggregator:
    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self._calibrator = ThresholdCalibrator(policy.calibration)

    def aggregate(self, computations: Sequence[ClauseComputation]) -> Tuple[List[ClauseScore], Dict[str, object]]:
        computations = sorted(computations, key=lambda item: item.clause_id)
        thresholds = dict(self.policy.thresholds)
        calibration_input = [
            CalibrationClause(
                clause_id=comp.clause_id,
                confidence=comp.confidence,
                metadata=comp.metadata,
            )
            for comp in computations
        ]
        warn_threshold, demotions = self._calibrator.calibrate(calibration_input, thresholds)
        thresholds["WARN"] = warn_threshold

        high_threshold = thresholds.get("HIGH", 0.99)
        ambig_gap = thresholds.get("ambig_gap", 0.08)

        results: List[ClauseScore] = []
        counters = {"HIGH": 0, "WARN": 0, "OK": 0, "AMBIG": 0}

        for comp in computations:
            risk_flag, reasons = self._classify(
                comp,
                high_threshold,
                warn_threshold,
                ambig_gap,
                demotions,
            )
            counters[risk_flag] += 1
            results.append(
                ClauseScore(
                    clause_id=comp.clause_id,
                    confidence=round(comp.confidence, 6),
                    risk_flag=risk_flag,
                    reasons=reasons,
                    adopted_rules=comp.adopted_rules,
                    suppressed_rules=comp.suppressed_rules,
                    per_hit_scores=comp.per_hit_scores,
                    metadata=comp.metadata,
                )
            )

        high = counters["HIGH"]
        warn = counters["WARN"]
        ok = counters["OK"]
        ambig = counters["AMBIG"]
        denom = warn + high + ok
        warn_rate = warn / denom if denom else 0.0
        high_rate = high / denom if denom else 0.0
        ok_rate = ok / denom if denom else 0.0
        ambig_rate = ambig / (warn + high + ok + ambig) if (warn + high + ok + ambig) else 0.0

        summary = {
            "warn_rate": round(warn_rate, 4),
            "high_rate": round(high_rate, 4),
            "ok_rate": round(ok_rate, 4),
            "ambig_rate": round(ambig_rate, 4),
            "thresholds_applied": {
                "HIGH": round(high_threshold, 6),
                "WARN": round(warn_threshold, 6),
            },
        }

        return results, summary

    def _classify(
        self,
        comp: ClauseComputation,
        high_threshold: float,
        warn_threshold: float,
        ambig_gap: float,
        demotions: Sequence[str],
    ) -> Tuple[str, List[str]]:
        reasons = list(comp.reasons)
        confidence = comp.confidence
        demoted = comp.clause_id in demotions

        if confidence >= high_threshold and not demoted:
            reasons.append(f"confidence >= HIGH ({high_threshold:.2f})")
            return "HIGH", reasons

        if confidence >= high_threshold and demoted:
            reasons.append("demoted_high_without_critical")
            reasons.append(f"confidence >= HIGH ({high_threshold:.2f})")
            reasons.append("demoted_to_WARN via calibration")
            return "WARN", reasons

        warn_cutoff = warn_threshold + max(ambig_gap, 0.0)
        if confidence >= warn_cutoff:
            reasons.append(
                f"confidence >= WARN ({warn_threshold:.2f}) with gap {ambig_gap:.2f}"
            )
            return "WARN", reasons

        if confidence >= warn_threshold:
            reasons.append(
                f"within ambig window [{warn_threshold:.2f}, {warn_cutoff:.2f})"
            )
            return "AMBIG", reasons

        reasons.append(f"confidence < WARN ({warn_threshold:.2f})")
        return "OK", reasons


__all__ = ["Aggregator"]

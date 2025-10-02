from __future__ import annotations

"""Numeric and table driven evaluation for Module 3-4."""

from dataclasses import dataclass
import operator
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import utils
from .schemas import MatchEvidence, NormClause, RuntimeRule, RulesetRuntime

_OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}

_DATE_RANGE_TOKEN = re.compile("(\\d+(?:\\.\\d+)?)\\s*(?:\\uAC1C\\uC6D4|\\uB2EC|month|months)", re.IGNORECASE)


@dataclass
class NumericContext:
    values: Dict[str, Any]
    notes: List[str]


class NumericTableEvaluator:
    def __init__(self, ruleset: RulesetRuntime) -> None:
        self._ruleset = ruleset

    def match(self, clause: NormClause, rule: RuntimeRule) -> List[MatchEvidence]:
        requirements = set(rule.requires or ()) | set(self._ruleset.required_features_for(rule.rule_id))
        context = self._build_context(clause)
        if not self._satisfies_requirements(requirements, context):
            return []
        matchers = rule.matchers or {}
        if not isinstance(matchers, Mapping):
            matchers = {}
        numeric_spec = matchers.get("numeric") or matchers.get("table")
        if not numeric_spec:
            return []
        ok, eval_notes = self._evaluate_spec(numeric_spec, context.values)
        if not ok:
            return []
        notes = [f"numeric:{note}" for note in context.notes + eval_notes if note]
        if "numeric:match" not in notes:
            notes.insert(0, "numeric:match")
        strength = utils.clamp(0.55 + 0.05 * len(eval_notes), 0.45, 0.9)
        text = clause.text or clause.normalized_text
        spans: List[Tuple[int, int]] = []
        spans.extend(context.values.get("amount_spans", []))
        spans.extend(context.values.get("percentage_spans", []))
        spans = spans[:3]
        snippet = utils.gather_snippet(text or "", spans)
        evidence = MatchEvidence(
            rule_id=rule.rule_id,
            clause_id=clause.id,
            match_type="numeric",
            strength=strength,
            spans=spans,
            evidence_snippet=snippet,
            notes=notes,
        )
        return [evidence.clamp_strength()]

    def _build_context(self, clause: NormClause) -> NumericContext:
        notes: List[str] = []
        text = clause.text or clause.normalized_text or ""
        amount_multiplier = utils.infer_currency_multiplier(text)
        amounts: List[float] = []
        amount_spans: List[Tuple[int, int]] = []
        for match in re.finditer(r"\\d+[\\d,\\.]*", text):
            raw = match.group(0).replace(",", "")
            try:
                value = float(raw)
            except ValueError:
                continue
            amounts.append(utils.expand_numeric_value(value, amount_multiplier))
            amount_spans.append((match.start(), match.end()))
        percentages = utils.extract_percentage_tokens(text)
        percentage_spans: List[Tuple[int, int]] = []
        for match in re.finditer(r"\\d+(?:\\.\\d+)?%", text):
            percentage_spans.append(match.span())
        duration_tokens = [float(token) for token in _DATE_RANGE_TOKEN.findall(text)]
        if duration_tokens:
            notes.append("duration_token")
        values = {
            "amounts": amounts,
            "amount_spans": amount_spans,
            "percentages": percentages,
            "percentage_spans": percentage_spans,
            "durations": duration_tokens,
        }
        return NumericContext(values=values, notes=notes)

    def _satisfies_requirements(
        self,
        requirements: Iterable[str],
        context: NumericContext,
    ) -> bool:
        requirements = list(requirements)
        if not requirements:
            return True
        available = set()
        if context.values.get("amounts"):
            available.add("numeric_amount")
        if context.values.get("percentages"):
            available.add("percentage")
        if context.values.get("durations"):
            available.add("date_range")
        return all(req in available for req in requirements)

    def _evaluate_spec(self, spec: Any, values: Dict[str, Any]) -> Tuple[bool, List[str]]:
        if isinstance(spec, Mapping):
            comparator = str(spec.get("op") or spec.get("comparator") or "").strip()
            lhs = spec.get("lhs") or spec.get("feature")
            rhs = spec.get("rhs", spec.get("value"))
            if lhs == "numeric_amount" and values.get("amounts"):
                return self._evaluate_numeric(values["amounts"], comparator, rhs, "amount")
            if lhs == "percentage" and values.get("percentages"):
                return self._evaluate_numeric(values["percentages"], comparator, rhs, "percentage")
            if lhs == "date_range" and values.get("durations"):
                return self._evaluate_numeric(values["durations"], comparator, rhs, "duration")
            return False, []
        if isinstance(spec, Sequence):
            overall_notes: List[str] = []
            for item in spec:
                ok, item_notes = self._evaluate_spec(item, values)
                if not ok:
                    return False, []
                overall_notes.extend(item_notes)
            return True, overall_notes
        return bool(spec), []

    def _evaluate_numeric(
        self,
        candidates: Sequence[float],
        comparator: str,
        rhs: Any,
        label: str,
    ) -> Tuple[bool, List[str]]:
        if not candidates:
            return False, []
        op = _OPERATORS.get(comparator)
        if not op:
            return False, []
        try:
            rhs_value = float(rhs)
        except (TypeError, ValueError):
            return False, []
        for candidate in candidates:
            if op(candidate, rhs_value):
                return True, [f"{label}_pass"]
        return False, []

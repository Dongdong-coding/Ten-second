from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple
import json
import re

from . import schemas
from .policy import ContextPolicy, PolicyDecision

_UTF8_SIG = "utf-8-sig"

ANNEX_KEYWORDS = ("annex", "appendix", "schedule", "exhibit")
EXCEPTION_KEYWORDS = ("exception", "except", "carve-out")
RISK_ORDER = ["HIGH", "WARN", "OK"]
EFFECT_AUDIENCE = {
    "NOTWITHSTANDING": "target",
    "EXCEPTION_LINK": "target",
    "SUBJECT_TO": "source",
    "ANNEX_REF": "source",
    "DEFINITION_LINK": "source",
    "REF_ARTICLE": "source",
}


class ContextResolver:
    def __init__(
        self,
        *,
        clauses: Dict[str, schemas.Clause],
        scores: Dict[str, schemas.Score],
        hits: Sequence[schemas.Hit],
        policy: ContextPolicy,
        ruleset: Optional[dict] = None,
    ) -> None:
        self.clauses = clauses
        self.scores = scores
        self.hits = list(hits)
        self.policy = policy
        self.ruleset = ruleset or {}

        self._relations: List[schemas.Relation] = self._build_relations()
        self._relations_by_source: Dict[str, List[schemas.Relation]] = defaultdict(list)
        self._relations_by_target: Dict[str, List[schemas.Relation]] = defaultdict(list)
        for relation in self._relations:
            self._relations_by_source[relation.source_id].append(relation)
            self._relations_by_target[relation.target_id].append(relation)

    @classmethod
    def from_files(
        cls,
        *,
        clauses_path: Path,
        scores_path: Path,
        hits_path: Optional[Path],
        policy_path: Path,
        ruleset_path: Optional[Path] = None,
    ) -> "ContextResolver":
        try:
            clauses = schemas.load_clauses(clauses_path)
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Invalid clauses payload at {clauses_path}: {exc}") from exc
        try:
            scores = schemas.load_scores(scores_path)
        except (ValueError, KeyError) as exc:
            message = str(exc)
            if isinstance(exc, ValueError) and message == "scores must be a list of per-clause objects":
                raise ValueError(message) from None
            raise ValueError(f"Invalid scores payload at {scores_path}: {exc}") from exc
        hits: Sequence[schemas.Hit] = []
        if hits_path and hits_path.exists():
            try:
                hits = schemas.load_hits(hits_path)
            except (ValueError, KeyError) as exc:
                raise ValueError(f"Invalid hits payload at {hits_path}: {exc}") from exc
        policy = ContextPolicy.from_file(policy_path)
        ruleset = {}
        if ruleset_path and ruleset_path.exists():
            with ruleset_path.open("r", encoding=_UTF8_SIG) as handle:
                ruleset = json.load(handle)
        return cls(clauses=clauses, scores=scores, hits=hits, policy=policy, ruleset=ruleset)

    def resolve(self) -> Dict[str, object]:
        results: List[schemas.ContextResolution] = []
        effect_counts: Dict[str, int] = defaultdict(int)
        changed: List[str] = []
        unchanged: List[str] = []

        for clause_id in sorted(self.clauses.keys()):
            clause = self.clauses[clause_id]
            score = self.scores.get(
                clause_id,
                schemas.Score(clause_id=clause_id, confidence=0.0, risk_flag="AMBIG"),
            )
            outgoing = sorted(
                self._relations_by_source.get(clause_id, []),
                key=lambda rel: (rel.relation_type, rel.target_id),
            )
            applicable_relations = self._collect_applicable_relations(clause_id)
            effects: List[schemas.EffectRecord] = []
            policy_notes: List[str] = []

            for relation, other_clause in applicable_relations:
                decision = self.policy.decide(
                    relation_type=relation.relation_type,
                    this_clause=clause,
                    other_clause=other_clause,
                )
                if decision.notes:
                    policy_notes.extend(decision.notes)
                if not decision.effect:
                    continue
                counterpart_id = _counterpart_id(relation, clause_id)
                rationale = self._build_rationale(relation, decision)
                evidence = self._build_evidence(primary=clause, counterpart=other_clause)
                effects.append(
                    schemas.EffectRecord(
                        effect_type=decision.effect,
                        target_clause_id=counterpart_id,
                        rationale=rationale,
                        evidence=evidence,
                    )
                )
                effect_counts[decision.effect] += 1

            effects = self._sort_effects(effects)
            contextual_flag = self._derive_contextual_flag(score, effects)

            resolution = schemas.ContextResolution(
                clause_id=clause_id,
                base_risk_flag=score.risk_flag,
                base_confidence=score.confidence,
                relations=outgoing,
                effects=effects,
                contextual_risk_flag=contextual_flag,
                policy_notes=sorted(set(policy_notes)),
                graph_degree_out=len(outgoing),
                graph_degree_in=len(self._relations_by_target.get(clause_id, [])),
            )
            if contextual_flag and contextual_flag != score.risk_flag:
                changed.append(clause_id)
            else:
                unchanged.append(clause_id)
            results.append(resolution)

        summary = {
            "counts_by_effect": {key: effect_counts[key] for key in sorted(effect_counts.keys())},
            "changed_flags": sorted(changed),
            "unchanged_flags": sorted(unchanged),
        }
        return {
            "results": [item.to_dict() for item in results],
            "summary": summary,
        }

    # ... remainder unchanged ...om __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple
import json
import re

from . import schemas
from .policy import ContextPolicy, PolicyDecision

ANNEX_KEYWORDS = ("annex", "appendix", "schedule", "exhibit")
EXCEPTION_KEYWORDS = ("exception", "except", "carve-out")
RISK_ORDER = ["HIGH", "WARN", "OK"]
EFFECT_AUDIENCE = {
    "NOTWITHSTANDING": "target",
    "EXCEPTION_LINK": "target",
    "SUBJECT_TO": "source",
    "ANNEX_REF": "source",
    "DEFINITION_LINK": "source",
    "REF_ARTICLE": "source",
}


class ContextResolver:
    def __init__(
        self,
        *,
        clauses: Dict[str, schemas.Clause],
        scores: Dict[str, schemas.Score],
        hits: Sequence[schemas.Hit],
        policy: ContextPolicy,
        ruleset: Optional[dict] = None,
    ) -> None:
        self.clauses = clauses
        self.scores = scores
        self.hits = list(hits)
        self.policy = policy
        self.ruleset = ruleset or {}

        self._relations: List[schemas.Relation] = self._build_relations()
        self._relations_by_source: Dict[str, List[schemas.Relation]] = defaultdict(list)
        self._relations_by_target: Dict[str, List[schemas.Relation]] = defaultdict(list)
        for relation in self._relations:
            self._relations_by_source[relation.source_id].append(relation)
            self._relations_by_target[relation.target_id].append(relation)

    @classmethod
    def from_files(
        cls,
        *,
        clauses_path: Path,
        scores_path: Path,
        hits_path: Optional[Path],
        policy_path: Path,
        ruleset_path: Optional[Path] = None,
    ) -> "ContextResolver":
        clauses = schemas.load_clauses(clauses_path)
        scores = schemas.load_scores(scores_path)
        hits: Sequence[schemas.Hit] = []
        if hits_path and hits_path.exists():
            hits = schemas.load_hits(hits_path)
        policy = ContextPolicy.from_file(policy_path)
        ruleset = {}
        if ruleset_path and ruleset_path.exists():
            with ruleset_path.open("r", encoding="utf-8") as handle:
                ruleset = json.load(handle)
        return cls(clauses=clauses, scores=scores, hits=hits, policy=policy, ruleset=ruleset)

    def resolve(self) -> Dict[str, object]:
        results: List[schemas.ContextResolution] = []
        effect_counts: Dict[str, int] = defaultdict(int)
        changed: List[str] = []
        unchanged: List[str] = []

        for clause_id in sorted(self.clauses.keys()):
            clause = self.clauses[clause_id]
            score = self.scores.get(
                clause_id,
                schemas.Score(clause_id=clause_id, confidence=0.0, risk_flag="AMBIG"),
            )
            outgoing = sorted(
                self._relations_by_source.get(clause_id, []),
                key=lambda rel: (rel.relation_type, rel.target_id),
            )
            applicable_relations = self._collect_applicable_relations(clause_id)
            effects: List[schemas.EffectRecord] = []
            policy_notes: List[str] = []

            for relation, other_clause in applicable_relations:
                decision = self.policy.decide(
                    relation_type=relation.relation_type,
                    this_clause=clause,
                    other_clause=other_clause,
                )
                if decision.notes:
                    policy_notes.extend(decision.notes)
                if not decision.effect:
                    continue
                counterpart_id = _counterpart_id(relation, clause_id)
                rationale = self._build_rationale(relation, decision)
                evidence = self._build_evidence(primary=clause, counterpart=other_clause)
                effects.append(
                    schemas.EffectRecord(
                        effect_type=decision.effect,
                        target_clause_id=counterpart_id,
                        rationale=rationale,
                        evidence=evidence,
                    )
                )
                effect_counts[decision.effect] += 1

            effects = self._sort_effects(effects)
            contextual_flag = self._derive_contextual_flag(score, effects)

            resolution = schemas.ContextResolution(
                clause_id=clause_id,
                base_risk_flag=score.risk_flag,
                base_confidence=score.confidence,
                relations=outgoing,
                effects=effects,
                contextual_risk_flag=contextual_flag,
                policy_notes=sorted(set(policy_notes)),
                graph_degree_out=len(outgoing),
                graph_degree_in=len(self._relations_by_target.get(clause_id, [])),
            )
            if contextual_flag and contextual_flag != score.risk_flag:
                changed.append(clause_id)
            else:
                unchanged.append(clause_id)
            results.append(resolution)

        summary = {
            "counts_by_effect": {key: effect_counts[key] for key in sorted(effect_counts.keys())},
            "changed_flags": sorted(changed),
            "unchanged_flags": sorted(unchanged),
        }
        return {
            "results": [item.to_dict() for item in results],
            "summary": summary,
        }

    def _collect_applicable_relations(self, clause_id: str) -> List[Tuple[schemas.Relation, schemas.Clause]]:
        items: List[Tuple[schemas.Relation, schemas.Clause]] = []
        for relation in self._relations_by_source.get(clause_id, []):
            audience = EFFECT_AUDIENCE.get(relation.relation_type, "source")
            if audience != "source":
                continue
            counterpart = self.clauses.get(relation.target_id)
            if counterpart:
                items.append((relation, counterpart))
        for relation in self._relations_by_target.get(clause_id, []):
            audience = EFFECT_AUDIENCE.get(relation.relation_type, "source")
            if audience != "target":
                continue
            counterpart = self.clauses.get(relation.source_id)
            if counterpart:
                items.append((relation, counterpart))
        return items

    def _derive_contextual_flag(
        self,
        score: schemas.Score,
        effects: Sequence[schemas.EffectRecord],
    ) -> Optional[str]:
        if not effects:
            return None
        current_flag = score.risk_flag
        confidence = score.confidence
        for effect in effects:
            current_flag = self._apply_effect(current_flag, confidence, effect.effect_type)
        if current_flag == score.risk_flag:
            return None
        return current_flag

    def _apply_effect(self, flag: str, confidence: float, effect: str) -> str:
        effect_upper = effect.upper()
        if effect_upper == "OVERRIDE":
            return _step_down_risk(flag)
        if effect_upper == "MITIGATE":
            threshold = float(self.policy.thresholds.get("mitigate_conf_min", 0.80))
            bonus = float(self.policy.thresholds.get("mitigate_bonus", 0.0))
            if confidence + bonus >= threshold:
                return _step_down_risk(flag)
            return flag
        if effect_upper == "CONFLICT":
            return "AMBIG"
        if effect_upper == "DEPEND":
            return "AMBIG"
        return flag

    def _sort_effects(self, effects: Sequence[schemas.EffectRecord]) -> List[schemas.EffectRecord]:
        priority_index = {name: idx for idx, name in enumerate(self.policy.priorities)}
        return sorted(
            effects,
            key=lambda eff: (
                priority_index.get(eff.effect_type, len(priority_index)),
                eff.target_clause_id,
            ),
        )

    def _build_rationale(self, relation: schemas.Relation, decision: PolicyDecision) -> str:
        return f"{relation.relation_type} via {decision.rationale}"

    def _build_evidence(
        self,
        *,
        primary: schemas.Clause,
        counterpart: schemas.Clause,
    ) -> schemas.Evidence:
        return schemas.Evidence(
            source_snippet=_trim_sentence(primary.text),
            target_snippet=_trim_sentence(counterpart.text),
        )

    def _build_relations(self) -> List[schemas.Relation]:
        relations: Dict[Tuple[str, str, str], schemas.Relation] = {}
        for clause in self.clauses.values():
            targets = self._collect_targets(clause)
            for target_id, relation_type, cue in targets:
                if target_id not in self.clauses:
                    continue
                key = (clause.clause_id, target_id, relation_type)
                if key in relations:
                    continue
                relations[key] = schemas.Relation(
                    source_id=clause.clause_id,
                    target_id=target_id,
                    relation_type=relation_type,
                    cue=cue,
                )
        return sorted(relations.values(), key=lambda rel: (rel.source_id, rel.relation_type, rel.target_id))

    def _collect_targets(self, clause: schemas.Clause) -> List[Tuple[str, str, Optional[str]]]:
        targets: Set[str] = set()
        annotations: List[Tuple[str, str, Optional[str]]] = []
        targets.update(self._targets_from_tags(clause))
        targets.update(self._targets_from_bindings(clause))
        targets.update(self._targets_from_text(clause))
        for target in targets:
            relation_type, cue = self._infer_relation_type(clause, target)
            annotations.append((target, relation_type, cue))
        return annotations

    def _targets_from_tags(self, clause: schemas.Clause) -> Set[str]:
        targets: Set[str] = set()
        for tag in clause.tags:
            if ":" not in tag:
                continue
            prefix, value = tag.split(":", 1)
            if prefix in {"ref", "annex", "exception"}:
                targets.add(value)
        return targets

    def _targets_from_bindings(self, clause: schemas.Clause) -> Set[str]:
        return set(clause.def_bindings.values())

    def _targets_from_text(self, clause: schemas.Clause) -> Set[str]:
        text = clause.normalized_text
        targets: Set[str] = set(re.findall(r"\[([A-Za-z0-9_-]+)\]", text))
        for number in re.findall(r"clause\s*(\d{1,4})", text, flags=re.IGNORECASE):
            candidate = f"C-{number}"
            if candidate in self.clauses:
                targets.add(candidate)
        return targets

    def _infer_relation_type(self, clause: schemas.Clause, target: str) -> Tuple[str, Optional[str]]:
        norm_text = clause.normalized_text
        for tag in clause.tags:
            if tag == f"annex:{target}":
                return "ANNEX_REF", "annex"
            if tag == f"exception:{target}":
                return "EXCEPTION_LINK", "exception"
        if target in clause.def_bindings.values():
            return "DEFINITION_LINK", "definition"
        phrase = self.policy.phrases.get("notwithstanding")
        if phrase and phrase.lower() in norm_text.lower():
            return "NOTWITHSTANDING", phrase
        subj_phrase = self.policy.phrases.get("subject_to")
        if subj_phrase and subj_phrase.lower() in norm_text.lower():
            return "SUBJECT_TO", subj_phrase
        lowered = norm_text.lower()
        for keyword in ANNEX_KEYWORDS:
            if keyword in lowered:
                return "ANNEX_REF", keyword
        for keyword in EXCEPTION_KEYWORDS:
            if keyword in lowered:
                return "EXCEPTION_LINK", keyword
        return "REF_ARTICLE", None


def _counterpart_id(relation: schemas.Relation, clause_id: str) -> str:
    return relation.target_id if relation.source_id == clause_id else relation.source_id


def _trim_sentence(text: str, *, limit: int = 120) -> str:
    snippet = " ".join(text.strip().split())
    if len(snippet) <= limit:
        return snippet
    return snippet[: limit - 3] + "..."


def _step_down_risk(flag: str) -> str:
    if flag not in RISK_ORDER:
        return flag
    index = RISK_ORDER.index(flag)
    if index >= len(RISK_ORDER) - 1:
        return flag
    return RISK_ORDER[index + 1]


__all__ = ["ContextResolver"]
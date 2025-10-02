from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .policy import EvaluationPolicy, load_policy
from .reporter import EvaluationInputs, build_report, EvaluationError
from .schemas import (
    load_golden,
    load_hits,
    load_ruleset,
    load_run_stats,
    load_scores,
)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Module 3.8 evaluation reporter")
    parser.add_argument("--scores", required=True, help="Path to scores.json")
    parser.add_argument("--hits", required=True, help="Path to hits.json")
    parser.add_argument("--rules", required=True, help="Path to ruleset_runtime.json")
    parser.add_argument("--golden", required=True, help="Path to golden_labels.json")
    parser.add_argument("--out-json", required=True, help="Output path for report JSON")
    parser.add_argument("--out-md", required=True, help="Output path for Markdown summary")
    parser.add_argument("--gate", required=True, help="Output path for gate decision JSON")
    parser.add_argument("--policy", help="Optional policy configuration JSON")
    parser.add_argument("--run-stats", help="Optional run statistics JSON")
    return parser.parse_args(argv)


def _resolve_policy(path_str: Optional[str]) -> EvaluationPolicy:
    path = Path(path_str) if path_str else None
    return load_policy(path)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    scores_path = Path(args.scores)
    hits_path = Path(args.hits)
    rules_path = Path(args.rules)
    golden_path = Path(args.golden)
    out_json_path = Path(args.out_json)
    out_md_path = Path(args.out_md)
    gate_path = Path(args.gate)
    policy_path = Path(args.policy) if args.policy else None
    run_stats_path = Path(args.run_stats) if args.run_stats else None

    policy = load_policy(policy_path)

    try:
        scores = load_scores(scores_path)
        hits = load_hits(hits_path)
        golden = load_golden(golden_path)
        ruleset = load_ruleset(rules_path)
        run_stats = load_run_stats(run_stats_path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    inputs = EvaluationInputs(
        scores=scores,
        hits=hits,
        golden=golden,
        ruleset=ruleset,
        run_stats=run_stats,
    )

    try:
        bundle = build_report(inputs, policy)
    except EvaluationError as exc:
        raise SystemExit(f"evaluation failed: {exc}")

    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.parent.mkdir(parents=True, exist_ok=True)

    out_json_path.write_text(json.dumps(bundle.report_json, indent=2, ensure_ascii=False), encoding="utf-8")
    out_md_path.write_text(bundle.report_markdown, encoding="utf-8")

    gate_payload = bundle.gate_decision
    gate_path.write_text(json.dumps(gate_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

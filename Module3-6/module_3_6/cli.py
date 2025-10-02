from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .aggregator import Aggregator
from .risk_scorer import score_clauses
from .schemas import Policy, hits_from_payload, rules_from_payload

_UTF8 = "utf-8"
_UTF8_SIG = "utf-8-sig"


def _prepare_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding=_UTF8)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding=_UTF8)


def _load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding=_UTF8_SIG) as stream:
        return json.load(stream)


def _write_json(payload: Any, path: Path, indent: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=_UTF8) as stream:
        if indent is not None:
            json.dump(payload, stream, ensure_ascii=False, indent=indent)
        else:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate risk scores from rule hits")
    parser.add_argument("--hits", required=True, help="Path to hits.json from Module3-4")
    parser.add_argument("--rules", required=True, help="Path to ruleset_runtime.json from Module3-3")
    parser.add_argument("--out", required=True, help="Destination path for aggregated scores list")
    parser.add_argument("--summary-out", help="Optional path to write aggregation summary JSON")
    parser.add_argument("--policy", help="Optional policy JSON controlling thresholds and penalties")
    parser.add_argument("--indent", type=int, help="Indentation level for JSON output (overrides --pretty).")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output with a default indentation of 2.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _prepare_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        hits_payload = _load_json(args.hits)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to read hits payload: {exc}") from None
    try:
        rules_payload = _load_json(args.rules)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to read ruleset payload: {exc}") from None
    policy_payload = None
    if args.policy:
        try:
            policy_payload = _load_json(args.policy)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Failed to read policy payload: {exc}") from None

    policy = Policy.from_mapping(policy_payload)
    try:
        hits = hits_from_payload(hits_payload)
    except ValueError as exc:
        raise SystemExit(f"Invalid hits payload: {exc}") from None
    try:
        rules = rules_from_payload(rules_payload)
    except ValueError as exc:
        raise SystemExit(f"Invalid ruleset payload: {exc}") from None

    computations = score_clauses(hits, rules, policy)
    aggregator = Aggregator(policy)
    results, summary = aggregator.aggregate(computations)

    indent = args.indent if args.indent is not None else (2 if args.pretty else None)
    scores_payload = [result.to_dict() for result in results]
    document = {"results": scores_payload, "summary": summary}
    _write_json(document, Path(args.out), indent)

    if args.summary_out:
        summary_payload = {"summary": summary}
        _write_json(summary_payload, Path(args.summary_out), indent)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
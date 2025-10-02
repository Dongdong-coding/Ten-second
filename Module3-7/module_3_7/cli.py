from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .resolver import ContextResolver

_UTF8 = "utf-8"


def _prepare_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding=_UTF8)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding=_UTF8)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve cross-clause context for Module 3-7 outputs.")
    parser.add_argument("--clauses", type=Path, required=True, help="Path to norm_clauses.json from Module 3-2")
    parser.add_argument("--scores", type=Path, required=True, help="Path to scores.json from Module 3-6")
    parser.add_argument("--hits", type=Path, required=False, help="Path to hits.json from Module 3-4")
    parser.add_argument("--rules", type=Path, required=False, help="Path to ruleset_runtime.json from Module 3-3")
    parser.add_argument("--policy", type=Path, required=True, help="Path to context policy JSON")
    parser.add_argument("--out", type=Path, required=True, help="Destination file for context_resolutions.json")
    parser.add_argument("--indent", type=int, default=None, help="Indentation for output JSON (overrides --pretty)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON with a default indentation of 2")
    return parser


def main(argv: list[str] | None = None) -> int:
    _prepare_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        resolver = ContextResolver.from_files(
            clauses_path=args.clauses,
            scores_path=args.scores,
            hits_path=args.hits,
            policy_path=args.policy,
            ruleset_path=args.rules,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    payload = resolver.resolve()

    indent = args.indent if args.indent is not None else (2 if args.pretty else None)
    if indent is None:
        indent = 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding=_UTF8) as handle:
        if indent is not None:
            json.dump(payload, handle, ensure_ascii=False, indent=indent)
        else:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
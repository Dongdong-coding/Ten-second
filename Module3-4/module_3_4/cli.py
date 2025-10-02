from __future__ import annotations

"""Command line entry point for the Module 3-4 engine."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Mapping, Sequence

from .engine import execute

_UTF8 = "utf-8"
_UTF8_SIG = "utf-8-sig"


def _prepare_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding=_UTF8)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding=_UTF8)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding=_UTF8_SIG) as stream:
        return json.load(stream)


def _dump_json(path: Path, payload: Any, indent: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=_UTF8) as stream:
        if indent is not None:
            json.dump(payload, stream, ensure_ascii=False, indent=indent, sort_keys=True)
        else:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))


def _rules_list_to_mapping(items: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]] | None:
    keyed: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            return None
        rule_id = str(item.get("rule_id") or item.get("id") or "").strip()
        if not rule_id:
            return None
        keyed[rule_id] = dict(item)
    return keyed if keyed else None


def _normalize_ruleset_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        normalized = dict(payload)
        rules_payload = normalized.get("rules")
        if isinstance(rules_payload, list):
            keyed = _rules_list_to_mapping(rules_payload)
            if keyed is not None:
                normalized["rules"] = keyed
        return normalized
    if isinstance(payload, list):
        keyed = _rules_list_to_mapping(payload)
        if keyed is not None:
            return {"rules": keyed}
    return payload

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Module 3-4 rule execution engine.")
    parser.add_argument("--clauses", required=True, help="Path to normalized clauses JSON produced by Module 3-2.")
    parser.add_argument("--ruleset", required=True, help="Path to compiled ruleset runtime JSON produced by Module 3-3.")
    parser.add_argument("--out", required=True, help="Path to write hits JSON output.")
    parser.add_argument("--indent", type=int, help="Indentation level for output JSON (overrides --pretty if set).")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the output JSON with a default indentation.")
    return parser


def main(argv: List[str] | None = None) -> int:
    _prepare_stdio()
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    clauses_payload = _load_json(Path(args.clauses))
    ruleset_payload = _normalize_ruleset_payload(_load_json(Path(args.ruleset)))

    indent = args.indent if args.indent is not None else (2 if args.pretty else None)

    try:
        hits = execute(clauses_payload, ruleset_payload)
    except AttributeError as exc:
        message = str(exc)
        if "list" in message and "get" in message:
            raise SystemExit(
                "ruleset matchers must be objects; encountered legacy list-based matchers. "
                "Please re-run Module 3-3 or normalize your ruleset runtime JSON.",
            ) from None
        raise
    except TypeError as exc:
        raise SystemExit(f"Invalid ruleset runtime payload: {exc}") from None
    except ValueError as exc:
        raise SystemExit(f"Execution failed: {exc}") from None

    _dump_json(Path(args.out), [hit.to_dict() for hit in hits], indent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
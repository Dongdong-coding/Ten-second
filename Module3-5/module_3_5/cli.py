from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .extractor import (
    DEFAULT_MAX_LENGTH,
    DEFAULT_MIN_LENGTH,
    extract_evidence,
    load_clauses,
    load_hits,
)

_UTF8 = "utf-8"
_UTF8_SIG = "utf-8-sig"


def _prepare_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding=_UTF8)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding=_UTF8)


def _dump_json(path: Path, payload: list[dict[str, object]], indent: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=_UTF8) as stream:
        if indent is not None:
            json.dump(payload, stream, ensure_ascii=False, indent=indent)
        else:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))


def main(argv: list[str] | None = None) -> None:
    _prepare_stdio()
    parser = argparse.ArgumentParser(
        description="Generate evidence snippets from normalized clauses and rule hits.",
    )
    parser.add_argument("--clauses", required=True, help="Path to NormClause JSON payload.")
    parser.add_argument("--hits", required=True, help="Path to hits JSON payload.")
    parser.add_argument("--out", required=True, help="File path to write evidence JSON.")
    parser.add_argument(
        "--target-min",
        type=int,
        default=DEFAULT_MIN_LENGTH,
        help="Minimum snippet length in characters (default: %(default)s).",
    )
    parser.add_argument(
        "--target-max",
        type=int,
        default=DEFAULT_MAX_LENGTH,
        help="Maximum snippet length in characters (default: %(default)s).",
    )
    parser.add_argument(
        "--redact-sensitive",
        default="false",
        help="Redact sensitive tokens (true/false).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=None,
        help="JSON indentation level (overrides --pretty).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print output JSON with a default indentation of 2.",
    )
    args = parser.parse_args(argv)

    try:
        clauses = load_clauses(Path(args.clauses))
    except (ValueError, KeyError) as exc:
        raise SystemExit(f"Invalid clauses payload: {exc}") from None
    try:
        hits = load_hits(Path(args.hits))
    except (ValueError, KeyError) as exc:
        raise SystemExit(f"Invalid hits payload: {exc}") from None

    redact_sensitive = _to_bool(args.redact_sensitive)
    evidences = extract_evidence(
        clauses,
        hits,
        target_min=args.target_min,
        target_max=args.target_max,
        redact_sensitive=redact_sensitive,
    )

    indent = args.indent if args.indent is not None else (2 if args.pretty else None)
    if indent is None:
        indent = 2
    payload = [item.to_dict() for item in evidences]
    _dump_json(Path(args.out), payload, indent)


def _to_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    raise ValueError(f"Cannot interpret boolean value from '{value}'")


if __name__ == "__main__":  # pragma: no cover
    main()
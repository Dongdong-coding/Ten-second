"""CLI entrypoint for compiling rulesets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .exceptions import LoaderError, RulesetCompilerError, ValidationError
from .pipeline import build_runtime_payload

_UTF8 = "utf-8"
_UTF8_SIG = "utf-8-sig"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile policy rules into runtime artefacts")
    parser.add_argument("--rules", required=True, help="Path to the input ruleset JSON file")
    parser.add_argument("--engine", required=True, help="Engine semantic version executing the ruleset")
    parser.add_argument("--flags", help="Optional path to experiment flag overrides JSON")
    parser.add_argument("--out", required=True, help="Destination path for the runtime JSON payload")
    parser.add_argument("--pretty", action="store_true", help="Emit human-friendly JSON with indentation")
    return parser.parse_args(argv)


def _prepare_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding=_UTF8)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding=_UTF8)


def _load_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding=_UTF8_SIG))
    except json.JSONDecodeError as exc:
        raise LoaderError(f"Invalid JSON in {path}: {exc}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    _prepare_stdio()
    args = parse_args(argv)

    rules_path = Path(args.rules)
    if not rules_path.exists():
        raise FileNotFoundError(f"Ruleset file not found: {rules_path}")

    flags_payload_path: str | None = None
    if args.flags:
        flags_path = Path(args.flags)
        if not flags_path.exists():
            raise FileNotFoundError(f"Flag override file not found: {flags_path}")
        # Validate early so we can emit a friendly error before compilation
        _load_json(flags_path)
        flags_payload_path = str(flags_path)

    try:
        payload = build_runtime_payload(rules_path, args.engine, flags_payload_path)
    except (LoaderError, ValidationError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    except RulesetCompilerError as exc:
        sys.stderr.write(f"unexpected error: {exc}\n")
        return 3

    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    json_kwargs: dict[str, object] = {"ensure_ascii": False}
    if args.pretty:
        json_kwargs.update(indent=2, sort_keys=True)
    else:
        json_kwargs.update(separators=(",", ":"))
    destination.write_text(json.dumps(payload, **json_kwargs), encoding=_UTF8)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional

from .clause_segmenter import ClauseSegmenter
from .schemas import Clause

_UTF8 = "utf-8"
_UTF8_SIG = "utf-8-sig"
_BOM = "\ufeff"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Segment Korean lease contracts into structured clauses.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Optional contract file path. Reads STDIN when omitted.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Destination path for clause JSON output.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=None,
        help="Pretty-print JSON with the given indentation.",
    )
    return parser


def _load_text_from_path(path: str) -> str:
    return Path(path).read_text(encoding=_UTF8_SIG)


def _prepare_stdio() -> None:
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding=_UTF8)


def _strip_bom(text: str) -> str:
    if text.startswith(_BOM):
        return text.lstrip(_BOM)
    return text


def _serialise_clause(clause: Clause) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": clause.id,
        "start": clause.start,
        "end": clause.end,
        "text": clause.text,
        "tags": list(clause.tags),
    }
    if clause.title:
        payload["title"] = clause.title
    return payload


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _prepare_stdio()

    if args.path:
        raw_text = _load_text_from_path(args.path)
    else:
        raw_text = sys.stdin.read()

    raw_text = _strip_bom(raw_text)

    segmenter = ClauseSegmenter()
    clauses = segmenter.segment(raw_text)
    payload = [_serialise_clause(clause) for clause in clauses]

    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding=_UTF8) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=args.indent)
        if args.indent is not None:
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
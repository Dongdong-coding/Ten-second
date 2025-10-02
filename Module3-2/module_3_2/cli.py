from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .ontology_mapper import load_ontology, load_synonyms, process
from .schemas import Clause

_UTF8 = 'utf-8'
_UTF8_SIG = 'utf-8-sig'


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Normalize lease clauses and map ontology categories.',
    )
    parser.add_argument(
        '--in',
        dest='input_path',
        required=True,
        help='Path to clauses JSON produced by Module 3-1.',
    )
    parser.add_argument(
        '--out',
        dest='output_path',
        required=True,
        help='Destination path for normalized clause JSON.',
    )
    parser.add_argument(
        '--ontology',
        dest='ontology_path',
        default=None,
        help='Optional custom ontology JSON path. Defaults to packaged ontology.',
    )
    parser.add_argument(
        '--synonyms',
        dest='synonyms_path',
        default=None,
        help='Optional custom synonyms JSON path. Defaults to packaged synonyms.',
    )
    parser.add_argument(
        '--indent',
        type=int,
        default=2,
        help='Indentation level for JSON output (default: %(default)s).',
    )
    return parser.parse_args(argv)


def _prepare_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding=_UTF8)


def _load_clauses(path: Path) -> list[Clause]:
    with path.open('r', encoding=_UTF8_SIG) as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError('Input JSON must be a list of clause dictionaries.')
    return [Clause.from_dict(item) for item in payload]


def _resolve_data_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    package_root = Path(__file__).resolve().parent.parent
    default_data_dir = package_root / 'data'
    ontology_path = Path(args.ontology_path) if args.ontology_path else default_data_dir / 'ontology_lease.json'
    synonyms_path = Path(args.synonyms_path) if args.synonyms_path else default_data_dir / 'synonyms_ko.json'
    output_path = Path(args.output_path)
    return ontology_path, synonyms_path, output_path


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    _prepare_stdio()

    input_path = Path(args.input_path)
    if not input_path.exists():
        raise FileNotFoundError(f'Input file not found: {input_path}')

    clauses = _load_clauses(input_path)
    ontology_path, synonyms_path, output_path = _resolve_data_paths(args)

    ontology = load_ontology(ontology_path)
    synonyms = load_synonyms(synonyms_path)

    norm_clauses = process(clauses, ontology, synonyms)
    payload = [clause.to_dict() for clause in norm_clauses]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding=_UTF8) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=args.indent)
        if args.indent is not None:
            handle.write("\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())

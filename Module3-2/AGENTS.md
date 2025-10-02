# Repository Guidelines

## Project Structure & Module Organization
- Core package lives in `module_3_2/`; `ontology_mapper.py` hosts the mapping pipeline, `schemas.py` defines `Clause`/`NormClause` dataclasses, and `cli.py` wires the CLI entrypoint.
- Domain resources sit under `data/` (`ontology_lease.json`, `synonyms_ko.json`). Update them atomically and keep identifiers stable for downstream consumers.
- Tests reside in `tests/test_mapper.py`; expand within `tests/` using descriptive filenames that mirror the feature under review.
- Sample inputs in `samples/clauses_from_3_1.json` illustrate expected clause payloads; mirror this layout when crafting new fixtures or regression cases.

## Build, Test, and Development Commands
- `python -m module_3_2.cli --in samples/clauses_from_3_1.json --out build/norm_clauses.json` runs the end-to-end normalization flow; adjust paths to integrate with external pipelines.
- `pytest` executes the mapper suite; scope to a topic with `pytest tests/test_mapper.py -k deposit` during focused iterations.
- `python -m compileall module_3_2` performs a lightweight syntax sanity check before opening a pull request.

## Coding Style & Naming Conventions
- Target Python 3.11 and the standard library only; deterministic behavior is required for reproducible clause mapping.
- Apply PEP 8 with 4-space indentation; prefer explicit snake_case names (`map_category`, `bind_definitions`, `normalize_terms`).
- Encapsulate reusable text-normalization helpers in dedicated functions and avoid ad hoc globals inside mapping routines.
- Maintain Korean terminology exactly as captured in `synonyms_ko.json`; add aliases in lowercase and keep canonical tokens in UPPER_SNAKE_CASE.

## Testing Guidelines
- Model new tests after the scenarios embodied in `samples/` and assert on both successful categorizations and expected fallbacks (`uncategorized`, `candidates`).
- Changes affecting ontology mapping must extend `tests/test_mapper.py` with at least one positive and one edge-case assertion.
- Keep tests deterministic: seed any future randomness and assert on ordered fields such as `index_path` and `evidence_keywords`.

## Commit & Pull Request Guidelines
- Adopt Conventional Commit headers (`feat:`, `fix:`, `refactor:`, `test:`) followed by an imperative summary, e.g., `feat: add deposit clause mapper`.
- Reference issue IDs in the body when applicable and document ontology or synonym updates explicitly, including data version bumps.
- Pull requests need a concise overview, test evidence (`pytest` invocation + result), and before/after CLI output snippets when behavior shifts.

## Security & Configuration Tips
- Validate ontology JSON with `python -m json.tool data/ontology_lease.json` before pushing changes to prevent malformed releases.
- When updating synonyms, guard against duplicate aliases by adding a targeted test or quick set-membership check within `cli.py`.

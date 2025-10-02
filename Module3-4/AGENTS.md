# Repository Guidelines

## Project Structure & Module Organization
- Source code resides in `module_3_4/`; keep the orchestration entry in `engine.py`, evaluation utilities in `runtime/`, and shared schemas in `models.py`.
- Compiled rules imported from Module3-3 should sit in `build/ruleset_runtime.json`; treat `configs/` for environment toggles and `samples/` for fixture payloads.
- Put integration notebooks or prototypes in `notebooks/` and keep large artifacts out of version control via `.gitignore`.
- Tests live in `tests/` (mirroring package names) and synthetic data for them belongs in `tests/fixtures/`.

## Build, Test, and Development Commands
- `python -m venv .venv` then `.venv\\Scripts\\activate` to isolate dependencies; install editable with `python -m pip install -e .`.
- Run the decision engine via `python -m module_3_4.cli --rules build/ruleset_runtime.json --clauses samples/normalized_clauses.json --out build/decisions.json`.
- `pytest -q` executes the suite; narrow focus with `pytest tests/test_engine.py -k deposit` during iteration.
- `python -m ruff check module_3_4 tests` and `python -m black module_3_4 tests` keep formatting consistent.

## Coding Style & Naming Conventions
- Target Python 3.11, 4-space indentation, and type-hinted functions; snake_case for functions and variables, PascalCase for dataclasses, UPPER_SNAKE_CASE for constants.
- Favor pure functions for scoring rules and keep side-effects confined to CLI wrappers.
- Document nontrivial heuristics with concise comments and place shared constants in `module_3_4/constants.py`.

## Testing Guidelines
- Every rule execution path requires unit coverage plus a scenario test that feeds compiled rules and normalized clauses.
- Name tests `test_<component>_<behavior>` and store fixtures in `tests/fixtures/*.json`.
- Maintain at least 90% coverage via `pytest --cov=module_3_4 --cov-report=term-missing`; capture the command and summary in PRs.

## Commit & Pull Request Guidelines
- Use Conventional Commit headers (e.g., `feat: add penalty rule evaluator`) with summaries under 72 characters.
- Reference task IDs or spec doc links in the body and flag schema or contract changes explicitly.
- Pull requests need a purpose summary, testing evidence, attached sample outputs, and any config toggles reviewers must set locally.

## Security & Configuration Tips
- Keep secrets in `.env` and commit only `.env.example`.
- Validate rule payloads with `python -m json.tool` and never check real customer data into `samples/` or `tests/fixtures/`.
- Hash runtime bundles with `sha256sum build/ruleset_runtime.json` and record the digest in release notes.

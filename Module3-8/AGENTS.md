# Repository Guidelines

## Project Structure & Module Organization
- Keep production code in `module_3_8/`; route entry logic through `cli.py`, shared schemas in `schemas.py`, and agent implementations under `module_3_8/agents/`.
- Store policies, prompts, and tunables in `configs/`; persist sample payloads in `samples/`; send run artifacts to gitignored `artifacts/`.
- Mirror the package inside `tests/`, keeping reusable fixtures in `tests/fixtures/` and deterministic JSON snapshots in `tests/snapshots/`.
- Record architectural decisions and data contracts in `docs/` for future contributors.

## Build, Test, and Development Commands
- Create a virtual environment with `python -m venv .venv` and activate via `.venv\Scripts\activate`.
- Install dependencies in editable mode: `python -m pip install -e .[dev]`.
- Run the CLI locally with `python -m module_3_8.cli --config configs/dev.yaml --clauses samples/norm_clauses.json --hits samples/hits.json --scores samples/scores.json --rules samples/ruleset_runtime.json --out artifacts/context_resolutions.json`.
- Run tests with `pytest -q` or focus with `pytest tests/agents/test_context_router.py -k override`.
- Keep style checks green using `python -m ruff check module_3_8 tests` and `python -m black module_3_8 tests`.

## Coding Style & Naming Conventions
- Target Python 3.11, four-space indentation, explicit type hints, and dataclasses for structured payloads.
- Use snake_case for functions/modules, PascalCase for classes, and UPPER_SNAKE_CASE for constants and environment keys.
- Centralize prompts, regexes, and policy tables in config files and load them through helper utilities rather than embedding raw literals.

## Testing Guidelines
- Cover each decision branch with unit tests and add at least one CLI integration suite built on the canonical samples.
- Name tests `test_<component>_<behavior>`, share fixtures from `tests/fixtures/`, and snapshot deterministic outputs in `tests/snapshots/`.
- Maintain >=90% coverage via `pytest --cov=module_3_8 --cov-report=term-missing`; include the coverage summary in review requests.

## Commit & Pull Request Guidelines
- Follow Conventional Commit headers (`feat:`, `fix:`, `refactor:`) with <=72 character subjects and reference tracking IDs when possible.
- PRs should explain behavioral changes, attach CLI transcripts or diffed JSON artifacts, and list the validation commands you ran.
- Request review after lint and tests pass; co-review policy or schema updates and log any follow-ups in the PR checklist.

## Security & Configuration Tips
- Store secrets in `.env` (commit only `.env.example`), validate JSON with `python -m json.tool`, and lint configs with `python -m yamllint configs`.
- Strip customer data from committed samples and redact sensitive identifiers from logs or generated artifacts before sharing.

# Repository Guidelines

## Project Structure & Module Organization
- Keep production code in `module_3_6/`; house the CLI in `cli.py`, pipeline wiring in `pipeline.py`, and shared schemas in `schemas.py`.
- Implement agents under `module_3_6/agents/` (one module per agent) and reuse helpers from `module_3_6/utils.py`.
- Configuration presets live in `configs/`, sample payloads in `samples/`, and transient outputs in `artifacts/` (gitignored).
- Mirror the package layout inside `tests/` and park reusable fixtures in `tests/fixtures/`.

## Build, Test, and Development Commands
- `python -m venv .venv` then `.venv\Scripts\activate` for isolation; repeat after dependency changes.
- `python -m pip install -e .` keeps edits hot-reloaded.
- Run the orchestrator with `python -m module_3_6.cli --config configs/dev.yaml --clauses samples/clauses.json --hits samples/hits.json --out artifacts/evidence.json`.
- Execute `pytest -q` for the suite or focus with `pytest tests/agents/test_router.py -k rerank`.
- Lint via `python -m ruff check module_3_6 tests` and format with `python -m black module_3_6 tests`.

## Coding Style & Naming Conventions
- Target Python 3.11, 4-space indentation, and explicit type hints on public APIs.
- Use snake_case for functions and variables, PascalCase for agent classes, and UPPER_SNAKE_CASE for constants.
- Keep orchestration declarative; push heuristics into helpers in `module_3_6/utils.py` and route logging through `module_3_6/logger.py`.

## Testing Guidelines
- Add unit tests for each agent behavior plus an end-to-end CLI scenario using representative clause and hit data.
- Name tests `test_<component>_<behavior>` and store sizable fixtures in `tests/fixtures/`.
- Maintain >=90% coverage with `pytest --cov=module_3_6 --cov-report=term-missing`; paste the summary in pull requests.

## Commit & Pull Request Guidelines
- Follow Conventional Commit headers (`feat:`, `fix:`, `chore:`) with <=72 character subjects and bodies referencing tickets or specs.
- Summarize behavior changes, data migrations, and feature flags; attach CLI transcripts or screenshots when outputs shift.
- Call out validation steps, coverage results, and follow-ups before requesting review; enlist a second reviewer for pipeline-wide refactors.

## Security & Configuration Tips
- Store secrets in `.env` (commit only `.env.example`) and document required keys in `docs/configuration.md`.
- Validate JSON with `python -m json.tool` and YAML with `python -m yamllint configs`.
- Remove customer data from `samples/` and `tests/fixtures/`; mask sensitive spans in shared logs.

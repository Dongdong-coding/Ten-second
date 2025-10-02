# Repository Guidelines

## Project Structure & Module Organization
- Initialize source package under `module_3_5/`; keep orchestration entrypoints in `module_3_5/cli.py` and core agent logic in `module_3_5/engine.py`.
- Stage reusable behaviors in `module_3_5/agents/` (per-agent folders such as `retriever/`, `planner/`, `executor/`) and shared domain contracts in `module_3_5/schemas.py`.
- Store configuration templates in `configs/` (e.g., `configs/dev.yaml`), sample payloads in `samples/`, and generated outputs in `build/` (leave `build/` ignored in git).
- Mirror package layout under `tests/` (`tests/test_engine.py`, `tests/agents/test_planner.py`) and use `tests/fixtures/` for synthetic documents or compiled rules.

## Build, Test, and Development Commands
- `python -m venv .venv` then `.venv\Scripts\activate` to isolate dependencies; reinstall after editing `pyproject.toml`.
- `python -m pip install -e .` keeps local edits hot-reloaded.
- Run the CLI locally with `python -m module_3_5.cli --config configs/dev.yaml --in samples/minimal_clauses.json --out build/hits.json`.
- Execute the full suite via `pytest -q`; scope to an agent with `pytest tests/agents/test_planner.py -k summarize`.
- `python -m ruff check module_3_5 tests` and `python -m black module_3_5 tests` enforce linting and formatting.

## Coding Style & Naming Conventions
Target Python 3.11, 4-space indentation, and full typing in public interfaces. Use snake_case for functions, PascalCase for dataclasses, and UPPER_SNAKE_CASE for constants. Keep agent classes small, favor pure functions for scoring, and log through `module_3_5.logger` to centralize formatting.

## Testing Guidelines
Every new strategy requires unit tests and a scenario run that feeds the CLI with compiled rules. Name tests `test_<component>_<behavior>` and archive fixtures under `tests/fixtures/`. Maintain >=90% coverage using `pytest --cov=module_3_5 --cov-report=term-missing`; paste the command and summary in PR descriptions.

## Commit & Pull Request Guidelines
Follow Conventional Commit prefixes (`feat:`, `fix:`, `refactor:`) with <=72 character subjects. Reference tracking tickets in the body, call out schema or config impacts explicitly, and attach sample CLI outputs for behavior changes. Pull requests need a problem summary, validation logs, and any follow-up work items.

## Security & Configuration Tips
Store secrets in `.env` and check in only `.env.example`. Validate JSON with `python -m json.tool` and YAML configs with `python -m yamllint`. Redact real customer data from `samples/` and `tests/fixtures/`, and document required API keys in `docs/configuration.md`.

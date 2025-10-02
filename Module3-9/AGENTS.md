# Repository Guidelines

## Project Structure & Module Organization
Runtime code lives in `module_3_9/`; launch the CLI through `module_3_9/cli.py`. Agent variants belong in `module_3_9/agents/` and shared utilities in `module_3_9/core/`. Store prompts and configs in `configs/`, reusable payloads in `samples/`, and throwaway outputs in gitignored `artifacts/`. Mirror this layout in `tests/`, keeping fixtures under `tests/fixtures/` and JSON snapshots in `tests/snapshots/`.

## Build, Test, and Development Commands
Create an isolated environment with `python -m venv .venv` then `.venv\Scripts\activate`; upgrade tooling via `python -m pip install -U pip`. Install local dependencies in editable mode using `python -m pip install -e .[dev]`. Smoke-test agents with `python -m module_3_9.cli --config configs/dev.yaml --inputs samples/payload.json --out artifacts/latest_run.json`. Run fast checks using `pytest -q`, deeper coverage via `pytest --cov=module_3_9 --cov-report=term-missing`, lint with `python -m ruff check module_3_9 tests`, and format code using `python -m black module_3_9 tests`.

## Coding Style & Naming Conventions
Target Python 3.11, four-space indentation, and explicit type hints on public functions. Favor `dataclasses` or `TypedDict` for structured payloads. Use snake_case for modules and functions, PascalCase for classes, and UPPER_SNAKE_CASE for constants and feature flags. Keep prompts and regex-heavy strings inside YAML or JSON assets, and add concise module docstrings when flows are non-obvious.

## Testing Guidelines
Exercise every agent decision path with unit tests, leaning on deterministic fixtures and snapshots. Name tests `test_<component>_<behavior>` and place orchestration suites under `tests/integration/` to keep the main loop quick. Maintain at least 90% statement coverage and include the coverage command in review notes.

## Commit & Pull Request Guidelines
Adopt Conventional Commits (`feat:`, `fix:`, etc.) with <=72-character subjects and descriptive bodies for behavior changes. Group related work per commit and update documentation or configs alongside code. Pull requests should state intent, link tracking issues, attach CLI transcripts or artifact diffs, and list the validation commands you ran before requesting review.

## Security & Configuration Tips
Never commit real secrets; provide `.env.example` and source credentials locally. Validate structured assets with `python -m json.tool` and `python -m yamllint configs`, and scrub customer data from samples or generated artifacts before sharing.

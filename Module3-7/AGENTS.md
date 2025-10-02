# Repository Guidelines

## Project Structure & Module Organization
- Keep source in `module_3_7/`: `cli.py` for orchestration, `agents/` for agent modules, and shared helpers in `utils.py` plus structured logging in `logger.py`.
- Store configs in `configs/` (YAML) and canonical payloads in `samples/`; write generated reports to gitignored `artifacts/`.
- Mirror the package layout inside `tests/`, placing reusable fixtures in `tests/fixtures/` and capturing architecture notes in `docs/`.

## Build, Test, and Development Commands
- Create a venv with `python -m venv .venv`, activate via `.venv\Scripts\activate`, then `python -m pip install -e .[dev]` for editable installs.
- Run the primary flow using `python -m module_3_7.cli --config configs/dev.yaml --input samples/hits.json --out artifacts/report.json`.
- Execute `pytest -q` for the suite, narrow focus with `pytest tests/agents/test_router.py -k rerank`, and lint/format via `python -m ruff check module_3_7 tests` plus `python -m black module_3_7 tests`.

## Coding Style & Naming Conventions
- Target Python 3.11, 4-space indentation, type-hinted public functions, and dataclasses for structured payloads.
- Use snake_case for modules and functions, PascalCase for classes, and UPPER_SNAKE_CASE for constants and environment keys.
- Keep prompts and templates in `configs/prompts/` and load them through helper functions instead of embedding raw strings.

## Testing Guidelines
- Add unit tests for every agent decision branch and an end-to-end CLI scenario in `tests/test_cli_flow.py` that exercises sampled payloads.
- Name tests `test_<component>_<behavior>`, share fixtures from `tests/fixtures/`, and snapshot deterministic outputs in `tests/snapshots/`.
- Sustain >=90% coverage with `pytest --cov=module_3_7 --cov-report=term-missing` and include the coverage summary in pull requests.

## Commit & Pull Request Guidelines
- Follow Conventional Commit prefixes (`feat:`, `fix:`, `refactor:`) with <=72 character subjects and link related tickets or specs in the body.
- PRs should explain behavior changes, attach CLI transcripts or diffed JSON outputs, and list the lint/test commands you executed.
- Seek review only after all checks pass; co-review pipeline-affecting changes and log follow-up tasks in the PR checklist.

## Security & Configuration Tips
- Store secrets in `.env`, keep `.env.example` current, and validate JSON/YAML with `python -m json.tool` plus `python -m yamllint configs`.
- Scrub customer data from samples, fixtures, and logs before sharing; redact identifiers in exported artifacts.

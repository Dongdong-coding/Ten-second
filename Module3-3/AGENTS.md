# Repository Guidelines

## Project Structure & Module Organization
The module ships as a Python package under `module_3_3/`; keep high-level orchestration in `module_3_3/pipeline.py`, reusable prompts or templates in `module_3_3/prompts/`, and shared utilities in `module_3_3/utils/`.
Runtime assets (sample inputs, fixtures, classification taxonomies) belong in `samples/` and `data/`. Store generated artifacts in `build/` and keep that directory in `.gitignore`.
Write tests beside features inside `tests/`. Mirror module names when adding new files (`tests/test_pipeline.py`, `tests/test_utils.py`) to simplify discovery.

## Build, Test, and Development Commands
Set up a virtual environment with `python -m venv .venv` and activate it before installing anything.
Install dependencies in editable mode once `pyproject.toml` or `requirements.txt` is updated: `python -m pip install -e .`.
Run the core CLI locally with `python -m module_3_3.cli --config configs/dev.yaml --in samples/demo.json --out build/output.json`; this should be the same command you reference when submitting a pull request.
Execute `pytest -q` for the full suite, and target individual flows with `pytest tests/test_pipeline.py -k scenario_name`.

## Coding Style & Naming Conventions
Target Python 3.11. Follow PEP 8 with 4-space indentation and pure snake_case for functions (`score_clause`), PascalCase for dataclasses (`ClauseScore`), and UPPER_SNAKE_CASE for constants.
Keep modules under 250 lines and encapsulate behaviors behind functions or lightweight classes instead of inline scripts.
Format with `black` and lint with `ruff` prior to committing; add the corresponding pre-commit hook once the tooling configuration lands.

## Testing Guidelines
All new logic requires unit coverage and at least one scenario test that exercises the CLI. Mock external services; do not rely on network calls.
Name tests `test_<subject>_<expectation>` and store reusable fixtures in `tests/conftest.py`.
Aim for 90% line coverage; include a `pytest --cov=module_3_3` report in pull request descriptions, and attach sample CLI output for end-to-end changes.

## Commit & Pull Request Guidelines
Use Conventional Commits (`feat:`, `fix:`, `docs:`) with imperative summaries under 72 characters.
Reference issue IDs or task tickets in the body, and call out data or prompt updates explicitly so reviewers can validate downstream impact.
Pull requests must include: a concise summary, testing notes with exact commands, any schema migrations, and links to relevant design docs or recordings.

## Security & Configuration Tips
Copy sensitive settings into `.env` and commit only `.env.example` with safe defaults.
Never check real customer data into `samples/`. Mask or synthesize every fixture added to the repo.
Validate JSON resources via `python -m json.tool <file>` and sanity-check YAML with `python -m yamllint` before pushing.

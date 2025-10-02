# Repository Guidelines

## Project Structure & Module Organization
- `module_3_1/clause_segmenter.py` contains the deterministic state-machine segmenter; keep helper logic close to the orchestrating classes.
- `module_3_1/schemas.py` defines dataclasses and JSON schemas; extend them instead of creating ad-hoc dicts.
- `module_3_1/cli.py` provides the CLI entrypoint; preserve streaming STDIN/STDOUT behavior for batch runs.
- `tests/test_segmenter.py` holds pytest suites, while `samples/sample_lease_contract.txt` is the canonical fixture for regression checks.
- `pyproject.toml` tracks metadata; update version pins and scripts there.

## Build, Test, and Development Commands
- `python -m module_3_1.cli samples/sample_lease_contract.txt` runs the segmenter and emits Clause JSON. Pass `--help` for usage hints when adding options.
- `pytest` executes all automated tests. Use `pytest -k clause` during focused debugging.
- `python -m compileall module_3_1` is a quick syntax sanity check when editing multiple modules.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and descriptive snake_case names; reserve CamelCase for dataclasses.
- Rely on the Python 3.11 standard library only; prefer pure functions and deterministic control flow.
- Keep state-machine stages small and document non-obvious transitions with short comments.
- Run `python -m compileall module_3_1` or `ruff check` locally if available, but do not depend on external packages in commits.

## Testing Guidelines
- Place new tests under `tests/` using `test_*.py` naming. Mirror module structure when feasible.
- Cover edge cases for clause boundaries, tag generation, and CLI parameter parsing.
- Use the provided sample lease plus anonymized real-world snippets under 200 KB; commit fresh fixtures to `samples/`.
- Target >90% branch coverage for new logic and assert deterministic IDs (`A3-1-가` style) and tag sets.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `chore:`) with concise English summaries referencing affected modules.
- Limit pull requests to a single vertical change; include CLI examples, profiling notes, or screenshots when behavior shifts.
- Describe testing evidence (`pytest`, manual CLI run) in the PR body and link related issues or documentation updates.

## Runtime & Data Handling Notes
- Enforce memory (<200 MB) and latency (<1.5 s per 100 pages) targets noted in the design brief.
- Keep contract text anonymized and scrub sensitive data before committing.
- Preserve JSON output layout (`id`, `level`, `index_path`, `start`, `end`, `text`, `tags`, `title`) to avoid consumer regressions.


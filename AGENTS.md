# Repository Guidelines

## Project Structure & Module Organization
- Source modules live under `src/`, with `lzl/` covering foundational utilities and `lzo/` handling registries, types, and helper toolkits.
- Tests mirror the source layout inside `tests/`. Newly documented suites run via `tests/lzl/` and `tests/lzo/` (for example, `tests/lzo/test_registry.py`).
- Documentation assets stay in `docs/`, including living guides such as `docs/code-style.md`, `docs/future-updates.md`, and the Mintlify workflow reference.

## Build, Test, and Development Commands
- `make test` — execute the full pytest suite.
- `make test-lzl` — run documentation-focused tests for `lzl` modules.
- `make test-lzo` — execute registry, types, and utilities coverage for `lzo`.
- `pytest path/to/test_file.py` — target an individual test while iterating locally.

## Coding Style & Naming Conventions
- Python code uses four-space indentation and prefers `import typing as t`, referencing hints like `t.Dict` to stay consistent with `docs/code-style.md`.
- Keep files ASCII-only unless the existing module already justifies Unicode content.
- Add `__all__` exports for modules that serve as public façades (for example, `lzo/types/__init__.py`).

## Testing Guidelines
- Pytest is the default framework; async tests should use helpers from `tests/conftest.py` (no external event-loop plugins required).
- Place new cases beside their source counterparts (e.g., utilities → `tests/lzo/test_utils.py`).
- Prefer deterministic mocks and local fixtures to avoid network or filesystem side effects.

## Commit & Pull Request Guidelines
- Scope each commit to a single submodule sweep (e.g., `lzo.types` documentation + tests) and describe both documentation and test updates in the subject line.
- Pull requests should summarize affected areas, link to any tracking issues, and note validation steps (`make test`, targeted pytest commands).
- Record future behavioural changes in `docs/future-updates.md` instead of altering runtime logic during documentation sprints.

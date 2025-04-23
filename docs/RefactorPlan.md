# Lazyops Refactoring Plan (lzl/lzo Focus)

This document tracks the progress of the lazyops library refactoring effort.
The primary goal is to consolidate functionality into the `lzl` (Lazy Libraries/Utilities)
and `lzo` (Lazy Objects/Registry) namespaces, deprecating the older `lazyops` namespace.

## Overall Goals

- Have a clear distinction between the `lzl` and `lzo` modules.
- Rework sub-modules within each that are outdated or have bugs.
- Cleanup and optimize the code where we can.
- Setup library documentation via Mintlify.
- Be able to automatically push documentation update whenever the library\'s version is updated.
- Improve the changelogs.
- Improve inline code annotations to be more consistent and descriptive (IDE experience).
- Prepare the repo for usage with Cursor (LLM Assistance).
- Prepare and rework the project README to be up to date.
- Greatly improve repo documentation (beyond README/CONTRIBUTING).
- Develop a clear set of guidelines and rules based on how the library has been developed thus far.

## Progress

### Phase 1: Planning & Guideline Definition (Completed)

- [X] Analyzed existing codebase structure (`lazyops`, `lzl`, `lzo`).
- [X] Clarified refactoring direction: Focus on `lzl`/`lzo`, deprecate `lazyops`.
- [X] Inferred initial coding standards from `lazyops`, `lzl`, `lzo` modules.
- [X] Created `CONTRIBUTING.md` defining coding guidelines:
    - PEP 8 / `black` formatting
    - Import standards
    - Naming conventions
    - Mandatory typing (`typing` module)
    - Mandatory Google-style docstrings
    - Guidelines for async, errors, logging, dependencies
    - Notes on preparing for LLM assistance.
- [X] Updated main `README.md` to reflect refactoring status, new structure, and link to `CONTRIBUTING.md`.

### Phase 2: Initial Standardization (In Progress)

- [X] **Apply Google-Style Docstrings in `src/lzl`:**
    - [X] `src/lzl/version.py`
    - [X] `src/lzl/types/__init__.py`
    - [X] `src/lzl/types/base.py`
    - [X] `src/lzl/types/properties.py` (incl. manual fix for linter issue)
    - [X] `src/lzl/types/common.py`
    - [X] `src/lzl/types/settings.py` (incl. fix for deprecated property)
    - [~] `src/lzl/types/typed.py` (Partially complete - up to `AsyncGenerator.asend`)

## Remaining Tasks

### Phase 2: Initial Standardization (Continued)

- [ ] **Complete Docstring Updates in `src/lzl`:**
    - [ ] Finish `src/lzl/types/typed.py` (`AsyncGenerator.athrow`, `aclose`).
    - [ ] `src/lzl/types/utils.py`
    - [ ] `src/lzl/logging/` (\*.py files)
    - [ ] `src/lzl/proxied/` (\*.py files)
    - [ ] `src/lzl/load/` (\*.py files)
    - [ ] `src/lzl/require/` (\*.py files)
    - [ ] `src/lzl/io/` (\*.py files)
    - [ ] `src/lzl/api/` (\*.py files)
    - [ ] `src/lzl/ext/` (\*.py files)
    - [ ] `src/lzl/cmd/` (\*.py files)
    - [ ] `src/lzl/db/` (\*.py files)
    - [ ] Other remaining `*.py` files in `src/lzl`.
- [ ] **Apply Google-Style Docstrings in `src/lzo`:**
    - [ ] Systematically update all `*.py` files within `src/lzo`.

### Phase 3: Code Migration & Cleanup

- [ ] Identify core functionality in `src/lazyops` to migrate.
- [ ] Migrate identified code piece-by-piece into appropriate `src/lzl` or `src/lzo` locations.
    - Apply coding standards (typing, docstrings, formatting) during migration.
    - Refactor migrated code for clarity and efficiency.
- [ ] Analyze `src/lzl` and `src/lzo` for outdated or buggy sub-modules and rework them.
- [ ] Perform general code cleanup and optimization across `lzl` and `lzo`.
- [ ] Remove/Archive the `src/lazyops` directory once migration is complete.

### Phase 4: Documentation & Tooling

- [ ] Set up `black` formatting configuration (e.g., in `pyproject.toml`) and apply it.
- [ ] Set up Mintlify for documentation generation.
    - Configure Mintlify to parse Google-style docstrings.
    - Structure documentation content.
- [ ] Implement CI/CD workflow (e.g., GitHub Actions) to automatically build and push documentation updates upon version changes/tags.
- [ ] Review and improve `changelogs.md`.
- [ ] Enhance overall repository documentation (e.g., architecture overview, detailed usage examples).

### Phase 5: Finalization

- [ ] Finalize `CONTRIBUTING.md` with Testing and Commit/PR guidelines.
- [ ] Review all changes and ensure consistency. 
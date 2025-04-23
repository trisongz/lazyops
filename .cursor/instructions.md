# Cursor Instructions for the lazyops Project

## Project Overview & Goals

*   **Core Modules:** The primary library code resides in `src/lzl/` (utilities, APIs, IO) and `src/lzo/` (registry, state, configs).
*   **Refactoring Focus:** We are actively refactoring to consolidate functionality into `lzl` and `lzo`. The code in `src/lazyops/` is being migrated or deprecated and should eventually be removed. Prioritize using/modifying code in `lzl` and `lzo`.
*   **Goal:** Create clean, well-documented, efficient, and distinct `lzl` and `lzo` modules.

## Coding Standards (Refer to `CONTRIBUTING.md`)

*   **Formatting:** Adhere strictly to `black` formatting. Assume `black` will be run.
*   **Imports:** Follow the import order specified in `CONTRIBUTING.md` (`__future__`, stdlib, third-party, internal `lzl`/`lzo`, local). Use absolute imports for `lzl`/`lzo`.
*   **Naming:** Follow conventions in `CONTRIBUTING.md` (CamelCase classes, lowercase_with_underscores functions/variables, UPPERCASE constants).
*   **Typing:** Mandatory type hints for all function/method signatures and class attributes using the `typing` module. Be explicit and prefer specific types.
*   **Docstrings:** **Mandatory Google-style docstrings** for all public modules, classes, functions, and methods. Ensure `Args:`, `Returns:`, `Raises:` sections are accurate and descriptive. See `CONTRIBUTING.md` for the exact format.
*   **Simplicity & Clarity:** Prefer clear, readable code over overly complex or "clever" solutions. Refactor complex logic into smaller, well-defined functions/methods.
*   **Error Handling:** Use specific exception types. Handle errors appropriately.
*   **Async:** Use `async`/`await` correctly for I/O-bound operations.

## Interaction Guidelines

*   **Editing:** When editing files, strictly adhere to the established coding standards (typing, docstrings, formatting).
*   **Refactoring:** When refactoring or migrating code from `src/lazyops`, ensure the resulting code in `lzl`/`lzo` meets the project standards. Place migrated code logically within the `lzl` or `lzo` structure.
*   **Docstring Generation:** When generating docstrings, use the **Google style** as defined in `CONTRIBUTING.md`. Be thorough in describing arguments, return values, and potential exceptions.
*   **Context:** Prioritize understanding the context within the `lzl` and `lzo` modules. Be aware of the interdependencies between them.
*   **Dependencies:** Use imports from `lzl` and `lzo` where appropriate, rather than duplicating utility code.

## Things to Avoid

*   Modifying or adding code to the `src/lazyops/` directory unless specifically migrating it out.
*   Introducing wildcard imports.
*   Generating docstrings that do not follow the Google style.
*   Suggesting overly complex code patterns without justification. 
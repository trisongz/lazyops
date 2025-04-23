# Contributing to lazyops (lzl/lzo)

Thank you for your interest in contributing! To ensure consistency and maintainability across the codebase, please adhere to the following guidelines.

## Code Style & Formatting

1.  **PEP 8:** Follow the [PEP 8 style guide](https://www.python.org/dev/peps/pep-0008/).
2.  **Formatting:** Use a consistent code formatter. We recommend using `black` for automated formatting. Configuration for formatters (like `pyproject.toml`) should be added if not present.
3.  **Line Length:** Keep lines under 100 characters where possible.
4.  **Imports:**
    *   Use `from __future__ import annotations` at the beginning of every Python file.
    *   Order imports as follows:
        1.  Standard library imports (e.g., `os`, `typing`, `asyncio`)
        2.  Third-party library imports (e.g., `pydantic`, `aiohttpx`, `frozendict`)
        3.  Internal `lzl` and `lzo` imports (use absolute paths, e.g., `from lzl.types import ...`, `from lzo.utils import ...`)
        4.  Local imports (`from . import ...`)
    *   Group imports logically within sections.
    *   Avoid wildcard imports (`from module import *`).
    *   Use `if TYPE_CHECKING:` blocks for imports needed only for type hinting to avoid circular dependencies at runtime.
5.  **Strings:** Use f-strings for string formatting (`f"Value is {variable}"`) where possible.

## Naming Conventions

*   **Modules:** `lowercase_with_underscores.py` (e.g., `helpers.py`, `base_client.py`)
*   **Packages:** `lowercase` (e.g., `utils`, `api`)
*   **Classes:** `CamelCase` (e.g., `OpenAIClient`, `MRegistry`)
*   **Functions & Methods:** `lowercase_with_underscores` (e.g., `configure_params`, `_get`)
*   **Variables:** `lowercase_with_underscores` (e.g., `api_key`, `base_delay`)
*   **Constants:** `UPPERCASE_WITH_UNDERSCORES` (e.g., `DEFAULT_TIMEOUT`, `MAX_RETRIES`)
*   **Protected Members:** Prefix with a single underscore (`_internal_method`, `_client_instance`).

## Type Hinting

*   **Mandatory:** Provide type hints for all function and method signatures (parameters and return types) using the `typing` module.
*   **Mandatory:** Provide type hints for class attributes.
*   **Clarity:** Use specific types where possible (e.g., `List[str]` instead of `list`, `Optional[int]` instead of `Union[int, None]`).
*   **Forward References:** Use string literals for forward references if needed (e.g., `field: 'MyClass'`), especially pre-Python 3.10 or when `from __future__ import annotations` isn't sufficient (though it usually is).

## Docstrings

*   **Mandatory:** Provide docstrings for all public modules, classes, functions, and methods.
*   **Format:** Use Google-style docstrings. This format is readable and easily parsed by documentation generators (like Sphinx or potentially Mintlify adapters) and LLMs.

    ```python
    \"\"\"One-line summary explaining the object's purpose.

    Args:
        param1 (str): Description of the first parameter.
        param2 (Optional[int]): Description of the second parameter.
            Defaults to None.

    Returns:
        bool: Description of the return value.

    Raises:
        ValueError: Explanation of when this error is raised.
        TypeError: Explanation of when this error is raised.

    Examples:
        >>> example_function('foo')
        True
    \"\"\"
    ```
*   **Content:** Clearly explain *what* the code does, its parameters, what it returns, and any exceptions it might raise. Include simple usage examples where helpful.

## Asynchronous Code

*   Use `async` and `await` for I/O-bound operations.
*   Clearly distinguish between synchronous and asynchronous functions/methods (e.g., `ping` vs `aping`).
*   Use appropriate libraries for async operations (e.g., `asyncio`, `aiohttpx`, `async_lru`).

## Error Handling

*   Use specific exception types rather than generic `Exception`.
*   Use `try...except` blocks appropriately.
*   Use `contextlib.suppress` only when intentionally ignoring specific exceptions is the correct behavior. Document why if not obvious.

## Logging

*   Use the centralized logging configuration (likely via `lzl.logging`).
*   Use appropriate log levels (e.g., `DEBUG`, `INFO`, `WARNING`, `ERROR`).
*   Provide context in log messages.

## Dependencies

*   Minimize dependencies where possible.
*   Be mindful of dependencies between `lzl` and `lzo`. Aim for clear boundaries and avoid circular imports. Document inter-dependencies if complex.

## Preparing for LLM Assistance (e.g., Cursor)

*   Adhering to the type hinting and detailed docstring guidelines above is the most critical step.
*   Clear naming and logical code structure also significantly help LLMs understand the codebase.
*   Keep functions and methods focused on a single responsibility.

## Testing

*   (To be defined) Add guidelines for writing unit and integration tests once the testing strategy is clearer.

## Commits & Pull Requests

*   (To be defined) Add guidelines for commit message format and PR process.

---

By following these guidelines, we can create a more consistent, readable, and maintainable codebase that is easier to understand for both humans and AI assistants. 
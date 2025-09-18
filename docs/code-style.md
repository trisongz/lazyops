# LazyOps Code Style Guide

This document captures incremental conventions as we touch the codebase.  Keep
it updated so new contributors have a single reference for style expectations.

## Typing and Imports
- Always import the typing module as `import typing as t`; prefer `t.Dict`,
  `t.Optional`, etc., over direct names from `typing`.
- Forward references should remain in quotes and grouped near their usage to
  minimise runtime import overhead.
- Add `__all__` lists when modules act as façades or re-export symbols to make
  the public surface explicit for documentation generators.

## Documentation
- Every module modified during this effort should include a narrative
  module-level docstring that explains its role within the `lzl`/`lzo`
  ecosystem.  Keep the tone practical so Mintlify can produce helpful
  summaries.
- Expand class and function docstrings with concise context-first language,
  followed by parameter descriptions when behaviour is not self-evident.
- Avoid documenting implementation details that may change; focus on intent and
  usage to prevent churn when functionality evolves.

## General Style
- Prefer enriching existing structures (docstrings, typing, comments) over
  altering runtime behaviour during documentation-focused sprints.
- When adding clarifying comments, keep them short and purpose-driven.  Do not
  annotate trivial assignments or control flow.
- Maintain ASCII encoding in source files unless there is a clear reason to do
  otherwise and the file already uses non-ASCII characters.

## Testing
- Prefer deterministic transports (for example `httpx.MockTransport`) when
  exercising HTTP clients to keep tests network-free and CI friendly.
- Use `tmp_path`/`tmp_path_factory` for filesystem-heavy utilities such as
  `lzl.io.persistence` to avoid leaving artefacts on developer machines.

_Last updated: September 18, 2025_

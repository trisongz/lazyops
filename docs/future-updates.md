# Future Enhancements

Tracks potential improvements discovered while documenting the codebase.  These
items should be evaluated in a dedicated refactor sprint so behaviour changes
remain intentional.

## lzl.api.aiohttpx
- Consider handling environments where `os.cpu_count()` returns `None` when
  computing preset connection limits; today we mirror the original behaviour
  which raises.
- Evaluate exposing a public API for registering custom preset profiles to
  reduce reliance on the mutable `PresetMap` dictionary.
- Explore replacing the global monkey patch of `httpx.Response.raise_for_status`
  with a scoped wrapper to avoid affecting consumers outside `lzl`.

## lzl.db
- Several backend helper methods (for example sqlite `get_table_column_size`)
  remain unimplemented placeholders; document desired semantics before adding
  behaviour in a future sprint.
- Evaluate whether importing heavy SQLAlchemy dependencies at module import time
  can be deferred to improve startup performance for non-database use cases.

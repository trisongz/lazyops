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

## lzl.io
- `lzl.io.queue.background` references an `EventQueue` class that is not
  defined within the package.  Confirm intended implementation and wire in the
  missing queue before advertising the API publicly.
- `PersistentDict` still mixes legacy ``typing`` aliases (`Optional`,
  `Dict`, …); migrate the remainder to ``import typing as t`` once behaviour
  stabilises to keep type hints consistent with newer modules.

## lzl.load
- Investigate whether the default ``install_missing=True`` flag for
  :class:`LazyLoad` should be scoped behind an explicit opt-in to avoid
  surprising installations at runtime.
- Consider exposing a public API for clearing the module/object caches managed
  by ``lazy_import`` to support long-lived processes that hot-reload
  configuration.

## lzl.pool
- `ThreadPool.run` currently requires `anyio`; evaluate providing a graceful
  fallback or clearer error message when the optional dependency is missing.
- Consider pooling executors across interpreter restarts to avoid spinning up
  multiple thread pools in short-lived CLI contexts.

## lzl.proxied
- `ProxyDict` shares class-level caches across subclasses; evaluate providing a
  context manager or helper to reset state when used in long-lived processes.
- Explore exposing thread-safety controls for `ProxyObject` beyond a simple
  boolean to support custom lock strategies when profiling indicates issues.

## lzl.sysmon
- GPU/CPU sampling currently depends on `lzo.utils.system`; consider adding
  graceful degradation when those utilities are unavailable.
- Evaluate emitting structured data (JSON) alongside formatted strings so the
  metrics can be ingested by observability tooling without parsing log text.

from __future__ import annotations

"""No-op logger implementation that still triggers LazyOps hooks."""

import logging
import traceback
import typing as t

from .mixins import LoggingMixin
from .utils import format_item, format_message, get_logging_level

if t.TYPE_CHECKING:
    from .base import Logger
    from .utils import MsgItem


class NullLoggerV1(logging.Logger):
    """Backwards-compatible stand-in that simply swallows log calls."""

    def info(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    def debug(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    def warning(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    def error(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    def critical(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    def exception(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    def log(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    def trace(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    def success(self, *args: t.Any, **kwargs: t.Any) -> None: ...


class NullLogger(logging.Logger, LoggingMixin):
    """Logger that delegates output to hooks without emitting messages."""

    def _format_item(
        self,
        msg: MsgItem,
        max_length: int | None = None,
        colored: bool | None = False,
        level: str | None = None,
        _is_part: bool | None = False,
    ) -> str:
        return format_item(msg, max_length=max_length, colored=colored, level=level, _is_part=_is_part)

    def _format_message(
        self,
        message: MsgItem,
        *args: MsgItem,
        prefix: str | None = None,
        max_length: int | None = None,
        level: str | None = None,
        colored: bool | None = False,
        extra: dict[str, t.Any] | None = None,
    ) -> str:
        return format_message(
            message,
            *args,
            prefix=prefix,
            max_length=max_length,
            level=level,
            colored=colored,
            extra=extra,
        )

    def _get_level(self, level: t.Union[str, int]) -> str:
        return get_logging_level(level)

    def log(
        self,
        level: t.Union[str, int],
        message: t.Any,
        *args: MsgItem,
        prefix: str | None = None,
        max_length: int | None = None,
        colored: bool | None = False,
        hook: t.Callable[[str], None] | None = None,
        **kwargs: t.Any,
    ) -> None:  # noqa: N805
        if not hook:
            return
        resolved_level = self._get_level(level)
        extra = kwargs.get("extra")
        rendered = self._format_message(
            message,
            *args,
            prefix=prefix,
            max_length=max_length,
            colored=colored,
            level=resolved_level,
            extra=extra,
        )
        self.run_logging_hooks(rendered, hook=hook)

    def info(self, *args: t.Any, **kwargs: t.Any) -> None:
        self.log("INFO", *args, **kwargs)

    def debug(self, *args: t.Any, **kwargs: t.Any) -> None:
        self.log("DEBUG", *args, **kwargs)

    def warning(self, *args: t.Any, **kwargs: t.Any) -> None:
        self.log("WARNING", *args, **kwargs)

    def error(self, *args: t.Any, **kwargs: t.Any) -> None:
        self.log("ERROR", *args, **kwargs)

    def trace(
        self,
        msg: t.Union[str, t.Any],
        error: type[BaseException] | None = None,
        level: str = "ERROR",
        limit: int | None = None,
        chain: bool | None = True,
        colored: bool | None = False,
        prefix: str | None = None,
        max_length: int | None = None,
        hook: t.Callable[[str], None] | None = None,
        **kwargs: t.Any,
    ) -> None:
        if not hook:
            return
        depth = kwargs.pop("depth", None)
        if depth is not None:
            limit = depth
        extra = kwargs.get("extra")
        if isinstance(msg, str):
            rendered = msg
            if extra:
                extra_rendered = format_item(extra, max_length=max_length, colored=colored, level=level)
                extra_rendered = extra_rendered.lstrip("\n")
                if extra_rendered:
                    rendered = f"{rendered}\n{extra_rendered}" if rendered else extra_rendered
        else:
            rendered = self._format_message(
                msg,
                colored=colored,
                prefix=prefix,
                max_length=max_length,
                level=level,
                extra=extra,
            )
        rendered += f"\n{traceback.format_exc(chain=chain, limit=limit)}"
        if error:
            rendered += f" - {error}"
        self.run_logging_hooks(rendered, hook=hook)

    def exception(self, *args: t.Any, **kwargs: t.Any) -> None:
        self.log("ERROR", *args, **kwargs)

    def success(self, *args: t.Any, **kwargs: t.Any) -> None:
        self.log("SUCCESS", *args, **kwargs)


__all__ = ["NullLogger", "NullLoggerV1"]

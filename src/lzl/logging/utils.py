from __future__ import annotations

"""Utility helpers for formatting LazyOps log messages."""

import re
import warnings
import typing as t

warnings.filterwarnings("ignore", category=SyntaxWarning)

from .static import (
    COLORED_MESSAGE_MAP,
    DEFAULT_STATUS_COLORS,
    LOGLEVEL_MAPPING,
    RESET_COLOR,
)

if t.TYPE_CHECKING:
    from dataclasses import _DataclassT
    from pydantic import BaseModel

    Primitives = t.Union[str, int, float, bool, tuple, list, type(None)]
    MsgItem = t.Union[BaseModel, _DataclassT, dict[str, t.Any], Primitives]
else:
    MsgItem = t.Any


def find_and_format_seps(msg: str) -> str:
    """Expand short colour directives (``|a,b|`` → ``|a||b|``)."""

    for sep_match in re.finditer(r"\|\w+,(\w+,*)+\|", msg):
        candidate = sep_match.group()
        if len(candidate) >= 10:
            continue
        msg = msg.replace(candidate, "||".join(candidate.split(",")))
    return msg


def extract_module_name(name: str) -> str:
    """Return the root module component from ``name``."""

    return name.split(".")[0]


def get_prefix_and_suffix(
    colored: bool | None = False,
    level: str | None = None,
) -> tuple[str, str]:
    """Return colour prefixes/suffixes for a message when enabled."""

    prefix = suffix = ""
    if colored:
        if level:
            level = level.lower()
            prefix = DEFAULT_STATUS_COLORS.get(level, "|g|")
        suffix = "|e|"
    return prefix, suffix


def format_item(
    msg: MsgItem,
    max_length: int | None = None,
    colored: bool | None = False,
    level: str | None = None,
    _is_part: bool | None = False,
) -> str:  # sourcery skip: extract-duplicate-method, low-code-quality, split-or-ifs
    """Normalise diverse message inputs into a printable string."""

    if isinstance(msg, str):
        return msg[:max_length] if max_length else msg
    if isinstance(msg, (float, int, bool, type(None))):
        rendered = str(msg)
        return rendered[:max_length] if max_length else rendered
    if isinstance(msg, (list, set)):
        rendered = str(msg) if _is_part else "\n" + "".join(f"- {item}\n" for item in msg)
        return rendered[:max_length] if max_length else rendered

    prefix, suffix = get_prefix_and_suffix(colored=colored, level=level)
    if isinstance(msg, dict):
        rendered = "\n"
        for key, value in msg.items():
            value_text = f"{value}"
            if max_length and len(value_text) > max_length:
                value_text = f"{value_text[:max_length]}..."
            rendered += f"- {prefix}{key}{suffix}: {value_text}\n"
        return rendered.rstrip()

    if isinstance(msg, tuple):
        rendered = "".join(
            f"- {prefix}{key}{suffix}: {format_item(value, max_length=max_length, colored=colored, level=level, _is_part=True)}\n"
            for key, value in zip(msg[0], msg[1])
        )
        return rendered[:max_length] if max_length else rendered

    if hasattr(msg, "is_fsspec"):
        return format_item(repr(msg), max_length=max_length, colored=colored, level=level, _is_part=_is_part)

    if (hasattr(msg, "dict") and hasattr(msg, "Config")) or hasattr(msg, "fields"):
        rendered = f"{prefix}[{msg.__class__.__name__}]{suffix}"
        fields = msg.fields.keys() if hasattr(msg, "fields") else msg.__fields__.keys()
        for field in fields:
            field_str = f"{prefix}{field}{suffix}"
            value_text = f"\n  {field_str}: {getattr(msg, field)!r}"
            if max_length is not None and len(value_text) > max_length:
                value_text = f"{value_text[:max_length]}..."
            rendered += value_text
        return rendered

    if hasattr(msg, "model_dump"):
        return format_item(msg.model_dump(mode="json"), max_length=max_length, colored=colored, level=level, _is_part=_is_part)

    if hasattr(msg, "dict"):
        return format_item(msg.dict(), max_length=max_length, colored=colored, level=level, _is_part=_is_part)

    if hasattr(msg, "json"):
        return format_item(msg.json(), max_length=max_length, colored=colored, level=level, _is_part=_is_part)

    if hasattr(msg, "__dict__"):
        return format_item(msg.__dict__, max_length=max_length, colored=colored, level=level, _is_part=_is_part)

    rendered = str(msg)
    return rendered[:max_length] if max_length else rendered


def format_message(
    message: MsgItem,
    *args: MsgItem,
    prefix: str | None = None,
    max_length: int | None = None,
    level: str | None = None,
    colored: bool | None = False,
    extra: dict[str, t.Any] | None = None,
) -> str:
    """Render a message plus optional extras into a single string."""

    rendered = ""
    if prefix:
        if colored and "|" not in prefix:
            base_color = "|g|"
            if level:
                level = level.lower()
                base_color = DEFAULT_STATUS_COLORS.get(level, "|g|")
            prefix = f"{base_color}{prefix}|e|"
        rendered += f"[{prefix}] "
    rendered += format_item(message, max_length=max_length, colored=colored, level=level)
    if args:
        for arg in args:
            rendered += "\n"
            rendered += format_item(arg, max_length=max_length, colored=colored, level=level)
    if extra:
        extras_rendered = format_item(extra, max_length=max_length, colored=colored, level=level)
        extras_rendered = extras_rendered.lstrip("\n")
        if extras_rendered:
            if rendered:
                rendered += "\n"
            rendered += extras_rendered
    if colored:
        rendered = rendered.replace("<fg", ">|fg")
        rendered = rendered.replace("<", "\\</")
        rendered = find_and_format_seps(rendered)
        for key, value in COLORED_MESSAGE_MAP.items():
            rendered = rendered.replace(key, value)
        rendered = rendered.replace(">|fg", "<fg")
        rendered = rendered.replace("\\</", "\\<")
        rendered += RESET_COLOR
    return rendered


def get_logging_level(level: t.Union[str, int]) -> str:
    """Normalise numeric/string levels into upper-case strings."""

    if isinstance(level, str):
        return level.upper()
    if isinstance(level, int):
        return LOGLEVEL_MAPPING.get(level, "INFO")
    return str(level)


__all__ = [
    "MsgItem",
    "find_and_format_seps",
    "extract_module_name",
    "get_prefix_and_suffix",
    "format_item",
    "format_message",
    "get_logging_level",
]

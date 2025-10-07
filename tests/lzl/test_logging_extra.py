from __future__ import annotations

from lzl.logging.null_logger import NullLogger
from lzl.logging.utils import format_message


def test_format_message_includes_extra_dict() -> None:
    result = format_message("base message", extra={"user": "alice", "request_id": "abc123"})

    lines = result.splitlines()
    assert lines[0] == "base message"
    assert "- user: alice" in lines[1:]
    assert "- request_id: abc123" in lines[1:]


def test_null_logger_formats_extra_into_message() -> None:
    captured: list[str] = []
    logger = NullLogger("test_null_logger")

    logger.info("processing", extra={"status": "ok", "duration": "42ms"}, hook=captured.append)

    assert captured, "Logger hook should capture at least one message"
    message = captured[-1]
    lines = message.splitlines()
    assert lines[0] == "processing"
    assert "- status: ok" in lines[1:]
    assert "- duration: 42ms" in lines[1:]

from __future__ import annotations

"""
File Decoders
"""

# from lzl import load

try:
    from httpx._decoders import ByteChunker, TextDecoder, TextChunker, LineDecoder

except ImportError:

    import io
    import codecs

    class ByteChunker:
        """
        Handles returning byte content in fixed-size chunks.
        """

        def __init__(self, chunk_size: int | None = None) -> None:
            self._buffer = io.BytesIO()
            self._chunk_size = chunk_size

        def decode(self, content: bytes) -> list[bytes]:
            if self._chunk_size is None:
                return [content] if content else []

            self._buffer.write(content)
            if self._buffer.tell() < self._chunk_size:
                return []
            value = self._buffer.getvalue()
            chunks = [
                value[i : i + self._chunk_size]
                for i in range(0, len(value), self._chunk_size)
            ]
            if len(chunks[-1]) == self._chunk_size:
                self._buffer.seek(0)
                self._buffer.truncate()
                return chunks
            else:
                self._buffer.seek(0)
                self._buffer.write(chunks[-1])
                self._buffer.truncate()
                return chunks[:-1]

        def flush(self) -> list[bytes]:
            value = self._buffer.getvalue()
            self._buffer.seek(0)
            self._buffer.truncate()
            return [value] if value else []
        

    class TextChunker:
        """
        Handles returning text content in fixed-size chunks.
        """

        def __init__(self, chunk_size: int | None = None) -> None:
            self._buffer = io.StringIO()
            self._chunk_size = chunk_size

        def decode(self, content: str) -> list[str]:
            if self._chunk_size is None:
                return [content] if content else []

            self._buffer.write(content)
            if self._buffer.tell() < self._chunk_size:
                return []
            value = self._buffer.getvalue()
            chunks = [
                value[i : i + self._chunk_size]
                for i in range(0, len(value), self._chunk_size)
            ]
            if len(chunks[-1]) == self._chunk_size:
                self._buffer.seek(0)
                self._buffer.truncate()
                return chunks
            else:
                self._buffer.seek(0)
                self._buffer.write(chunks[-1])
                self._buffer.truncate()
                return chunks[:-1]

        def flush(self) -> list[str]:
            value = self._buffer.getvalue()
            self._buffer.seek(0)
            self._buffer.truncate()
            return [value] if value else []


    class TextDecoder:
        """
        Handles incrementally decoding bytes into text
        """

        def __init__(self, encoding: str = "utf-8") -> None:
            self.decoder = codecs.getincrementaldecoder(encoding)(errors="replace")

        def decode(self, data: bytes) -> str:
            return self.decoder.decode(data)

        def flush(self) -> str:
            return self.decoder.decode(b"", True)


    class LineDecoder:
        """
        Handles incrementally reading lines from text.

        Has the same behaviour as the stdllib splitlines,
        but handling the input iteratively.
        """

        def __init__(self) -> None:
            self.buffer: list[str] = []
            self.trailing_cr: bool = False

        def decode(self, text: str) -> list[str]:
            # See https://docs.python.org/3/library/stdtypes.html#str.splitlines
            NEWLINE_CHARS = "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"

            # We always push a trailing `\r` into the next decode iteration.
            if self.trailing_cr:
                text = "\r" + text
                self.trailing_cr = False
            if text.endswith("\r"):
                self.trailing_cr = True
                text = text[:-1]

            if not text:
                # NOTE: the edge case input of empty text doesn't occur in practice,
                # because other httpx internals filter out this value
                return []  # pragma: no cover

            trailing_newline = text[-1] in NEWLINE_CHARS
            lines = text.splitlines()

            if len(lines) == 1 and not trailing_newline:
                # No new lines, buffer the input and continue.
                self.buffer.append(lines[0])
                return []

            if self.buffer:
                # Include any existing buffer in the first portion of the
                # splitlines result.
                lines = ["".join(self.buffer) + lines[0]] + lines[1:]
                self.buffer = []

            if not trailing_newline:
                # If the last segment of splitlines is not newline terminated,
                # then drop it from our output and start a new buffer.
                self.buffer = [lines.pop()]

            return lines

        def flush(self) -> list[str]:
            if not self.buffer and not self.trailing_cr:
                return []

            lines = ["".join(self.buffer)]
            self.buffer = []
            self.trailing_cr = False
            return lines
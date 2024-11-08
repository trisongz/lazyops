"""
Borrowed from
https://github.com/asyncdef/apyio/blob/master/apyio/__init__.py
"""

"""Async compatibility wrappers for Python io module stream objects."""

import io as sync_io


def open(
        file,
        mode="r",
        buffering=-1,
        encoding=None,
        errors=None,
        newline=None,
        closefd=True,
        opener=None,
):
    r"""Open file and return a stream.  Raise OSError upon failure.

    file is either a text or byte string giving the name (and the path
    if the file isn't in the current working directory) of the file to
    be opened or an integer file descriptor of the file to be
    wrapped. (If a file descriptor is given, it is closed when the
    returned I/O object is closed, unless closefd is set to False.)

    mode is an optional string that specifies the mode in which the file is
    opened. It defaults to 'r' which means open for reading in text mode. Other
    common values are 'w' for writing (truncating the file if it already
    exists), 'x' for exclusive creation of a new file, and 'a' for appending
    (which on some Unix systems, means that all writes append to the end of the
    file regardless of the current seek position). In text mode, if encoding is
    not specified the encoding used is platform dependent. (For reading and
    writing raw bytes use binary mode and leave encoding unspecified.) The
    available modes are:

    ========= ===============================================================
    Character Meaning
    --------- ---------------------------------------------------------------
    'r'       open for reading (default)
    'w'       open for writing, truncating the file first
    'x'       create a new file and open it for writing
    'a'       open for writing, appending to the end of the file if it exists
    'b'       binary mode
    't'       text mode (default)
    '+'       open a disk file for updating (reading and writing)
    'U'       universal newline mode (deprecated)
    ========= ===============================================================

    The default mode is 'rt' (open for reading text). For binary random
    access, the mode 'w+b' opens and truncates the file to 0 bytes, while
    'r+b' opens the file without truncation. The 'x' mode implies 'w' and
    raises an `FileExistsError` if the file already exists.

    Python distinguishes between files opened in binary and text modes,
    even when the underlying operating system doesn't. Files opened in
    binary mode (appending 'b' to the mode argument) return contents as
    bytes objects without any decoding. In text mode (the default, or when
    't' is appended to the mode argument), the contents of the file are
    returned as strings, the bytes having been first decoded using a
    platform-dependent encoding or using the specified encoding if given.

    'U' mode is deprecated and will raise an exception in future versions
    of Python.  It has no effect in Python 3.  Use newline to control
    universal newlines mode.

    buffering is an optional integer used to set the buffering policy.
    Pass 0 to switch buffering off (only allowed in binary mode), 1 to select
    line buffering (only usable in text mode), and an integer > 1 to indicate
    the size of a fixed-size chunk buffer.  When no buffering argument is
    given, the default buffering policy works as follows:

    * Binary files are buffered in fixed-size chunks; the size of the buffer
      is chosen using a heuristic trying to determine the underlying device's
      "block size" and falling back on `io.DEFAULT_BUFFER_SIZE`.
      On many systems, the buffer will typically be 4096 or 8192 bytes long.

    * "Interactive" text files (files for which isatty() returns True)
      use line buffering.  Other text files use the policy described above
      for binary files.

    encoding is the str name of the encoding used to decode or encode the
    file. This should only be used in text mode. The default encoding is
    platform dependent, but any encoding supported by Python can be
    passed.  See the codecs module for the list of supported encodings.

    errors is an optional string that specifies how encoding errors are to
    be handled---this argument should not be used in binary mode. Pass
    'strict' to raise a ValueError exception if there is an encoding error
    (the default of None has the same effect), or pass 'ignore' to ignore
    errors. (Note that ignoring encoding errors can lead to data loss.)
    See the documentation for codecs.register for a list of the permitted
    encoding error strings.

    newline is a string controlling how universal newlines works (it only
    applies to text mode). It can be None, '', '\n', '\r', and '\r\n'.  It
    works as follows:

    * On input, if newline is None, universal newlines mode is
      enabled. Lines in the input can end in '\n', '\r', or '\r\n', and
      these are translated into '\n' before being returned to the
      caller. If it is '', universal newline mode is enabled, but line
      endings are returned to the caller untranslated. If it has any of
      the other legal values, input lines are only terminated by the given
      string, and the line ending is returned to the caller untranslated.

    * On output, if newline is None, any '\n' characters written are
      translated to the system default line separator, os.linesep. If
      newline is '', no translation takes place. If newline is any of the
      other legal values, any '\n' characters written are translated to
      the given string.

    closedfd is a bool. If closefd is False, the underlying file descriptor
    will be kept open when the file is closed. This does not work when a file
    name is given and must be True in that case.

    The newly created file is non-inheritable.

    A custom opener can be used by passing a callable as *opener*. The
    underlying file descriptor for the file object is then obtained by calling
    *opener* with (*file*, *flags*). *opener* must return an open file
    descriptor (passing os.open as *opener* results in functionality similar to
    passing None).

    open() returns a file object whose type depends on the mode, and
    through which the standard file operations such as reading and writing
    are performed. When open() is used to open a file in a text mode ('w',
    'r', 'wt', 'rt', etc.), it returns a TextIOWrapper. When used to open
    a file in a binary mode, the returned class varies: in read binary
    mode, it returns a BufferedReader; in write binary and append binary
    modes, it returns a BufferedWriter, and in read/write mode, it returns
    a BufferedRandom.

    It is also possible to use a string or bytearray as a file for both
    reading and writing. For strings StringIO can be used like a file
    opened in a text mode, and for bytes a BytesIO can be used like a file
    opened in a binary mode.
    """
    result = sync_io.open(
        file,
        mode,
        buffering,
        encoding,
        errors,
        newline,
        closefd,
        opener,
    )

    return wrap_file(result)


def wrap_file(file_like_obj):
    """Wrap a file like object in an async stream wrapper.

    Files generated with `open()` may be one of several types. This
    convenience function retruns the stream wrapped in the most appropriate
    wrapper for the type. If the stream is already wrapped it is returned
    unaltered.
    """
    if isinstance(file_like_obj, AsyncIOBaseWrapper):

        return file_like_obj

    if isinstance(file_like_obj, sync_io.FileIO):

        return AsyncFileIOWrapper(file_like_obj)

    if isinstance(file_like_obj, sync_io.BufferedRandom):

        return AsyncBufferedRandomWrapper(file_like_obj)

    if isinstance(file_like_obj, sync_io.BufferedReader):

        return AsyncBufferedReaderWrapper(file_like_obj)

    if isinstance(file_like_obj, sync_io.BufferedWriter):

        return AsyncBufferedWriterWrapper(file_like_obj)

    if isinstance(file_like_obj, sync_io.TextIOWrapper):

        return AsyncTextIOWrapperWrapper(file_like_obj)

    raise TypeError(
        'Unrecognized file stream type {}.'.format(file_like_obj.__class__),
    )


class AsyncIOBaseWrapper:

    """IOBase object wrapper for async compatibility."""

    def __init__(self, stream):
        """Wrap an IOBase stream object."""
        self._stream = stream

    async def seek(self, pos, whence=0):
        """Change stream position.

        Change the stream position to byte offset pos. Argument pos is
        interpreted relative to the position indicated by whence.  Values
        for whence are ints:

        * 0 -- start of stream (the default); offset should be zero or positive
        * 1 -- current stream position; offset may be negative
        * 2 -- end of stream; offset is usually negative
        Some operating systems / file systems could provide additional values.

        Return an int indicating the new absolute position.
        """
        return self._stream.seek(pos, whence)

    async def tell(self):
        """Return an int indicating the current stream position."""
        return self._stream.tell()

    async def truncate(self, pos=None):
        """Truncate file to size bytes.

        Size defaults to the current IO position as reported by tell().  Return
        the new size.
        """
        return self._stream.truncate(pos)

    async def flush(self):
        """Flush write buffers, if applicable.

        This is not implemented for read-only and non-blocking streams.
        """
        return self._stream.flush()

    async def drain(self):
        """Flush the write buffers, if applicable.

        This exists for compatibility with the async stream drain method which
        forces a buffer flush.
        """
        return self._stream.flush()

    def close(self):
        """Flush and close the IO object.

        This method has no effect if the file is already closed.
        """
        return self._stream.close()

    def seekable(self):
        """Return a bool indicating whether object supports random access.

        If False, seek(), tell() and truncate() raise UnsupportedOperation.
        This method may need to do a test seek().
        """
        return self._stream.seekable()

    def readable(self):
        """Return a bool indicating whether object was opened for reading.

        If False, read() will raise UnsupportedOperation.
        """
        return self._stream.readable()

    def writable(self):
        """Return a bool indicating whether object was opened for writing.

        If False, write() and truncate() will raise UnsupportedOperation.
        """
        return self._stream.writable()

    @property
    def closed(self):
        """closed: bool.  True if the file has been closed.

        For backwards compatibility, this is a property, not a predicate.
        """
        return self._stream.closed

    async def __aenter__(self):
        """Context management protocol.  Returns self."""
        self._stream.__enter__()
        return self

    async def __aexit__(self, *args):
        """Context management protocol.  Calls close()."""
        self._stream.__exit__(*args)

    def fileno(self):
        """Return the underlying file descriptor (an int) if one exists.

        An OSError is raised if the IO object does not use a file descriptor.
        """
        return self._stream.fileno()

    def isatty(self):
        """Return a bool indicating whether this is an 'interactive' stream.

        Return False if it can't be determined.
        """
        return self._stream.isatty()

    async def readline(self, size=-1):
        r"""Read and return a line of bytes from the stream.

        If size is specified, at most size bytes will be read.
        Size should be an int.

        The line terminator is always b'\n' for binary files; for text
        files, the newlines argument to open can be used to select the line
        terminator(s) recognized.
        """
        return self._stream.readline(size)

    async def __aiter__(self):
        """Return self."""
        return self

    async def __anext__(self):
        """Get the next value. Convert StopIteration to StopAsyncIteration."""
        try:

            return self._stream.__next__()

        except StopIteration as exc:

            raise StopAsyncIteration() from exc

    async def readlines(self, hint=None):
        """Return all the lines."""
        return self._stream.readlines(hint)

    def writelines(self, lines):
        """Write an iterable of lines to the stream."""
        return self._stream.writelines(lines)

sync_io.IOBase.register(AsyncIOBaseWrapper)


class AsyncRawIOBaseWrapper(AsyncIOBaseWrapper):

    """RawIOBase object wrapper for async compatibility."""

    async def read(self, size=-1):
        """Read and return up to size bytes, where size is an int.

        Returns an empty bytes object on EOF, or None if the object is
        set not to block and has no data to read.
        """
        return self._stream.read(size)

    async def readall(self):
        """Read until EOF, using multiple read() call."""
        return self._stream.readall()

    async def readinto(self, b):
        """Read up to len(b) bytes into bytearray b.

        Returns an int representing the number of bytes read (0 for EOF), or
        None if the object is set not to block and has no data to read.
        """
        return self._stream.readinto(b)

    def write(self, b):
        """Write the given buffer to the IO stream.

        Returns the number of bytes written, which may be less than len(b).
        """
        return self._stream.write(b)

sync_io.RawIOBase.register(AsyncRawIOBaseWrapper)


class AsyncBufferedIOBaseWrapper(AsyncIOBaseWrapper):

    """BufferedIOBase object wrapper for async compatibility."""

    async def read(self, size=None):
        """Read and return up to size bytes, where size is an int.

        If the argument is omitted, None, or negative, reads and
        returns all data until EOF.

        If the argument is positive, and the underlying raw stream is
        not 'interactive', multiple raw reads may be issued to satisfy
        the byte count (unless EOF is reached first).  But for
        interactive raw streams (XXX and for pipes?), at most one raw
        read will be issued, and a short result does not imply that
        EOF is imminent.

        Returns an empty bytes array on EOF.

        Raises BlockingIOError if the underlying raw stream has no
        data at the moment.
        """
        return self._stream.read(size)

    async def read1(self, size=None):
        """Read up to size bytes with at most one read() system call."""
        return self._stream.read1(size)

    async def readinto(self, b):
        """Read up to len(b) bytes into bytearray b.

        Like read(), this may issue multiple reads to the underlying raw
        stream, unless the latter is 'interactive'.

        Returns an int representing the number of bytes read (0 for EOF).

        Raises BlockingIOError if the underlying raw stream has no
        data at the moment.
        """
        return self._stream.readinto(b)

    async def readinto1(self, b):
        """Read up to len(b) bytes into *b*, using at most one system call.

        Returns an int representing the number of bytes read (0 for EOF).

        Raises BlockingIOError if the underlying raw stream has no
        data at the moment.
        """
        return self._stream.readinto1(b)

    def write(self, b):
        """Write the given bytes buffer to the IO stream.

        Return the number of bytes written, which is never less than
        len(b).

        Raises BlockingIOError if the buffer is full and the
        underlying raw stream cannot accept more data at the moment.
        """
        return self._stream.write(b)

    def detach(self):
        """
        Separate the underlying raw stream from the buffer and return it.

        After the raw stream has been detached, the buffer is in an unusable
        state.
        """
        return self._stream.detach()

sync_io.BufferedIOBase.register(AsyncBufferedIOBaseWrapper)


class AsyncBytesIOWrapper(AsyncBufferedIOBaseWrapper):

    """BytesIO object wrapper for async compatibility."""

    def __getstate__(self):
        """Return a pickle dictionary."""
        body = self.__dict__.copy()
        body['_stream'] = body['_stream'].__getstate__()
        return body

    def getvalue(self):
        """Return the bytes value (contents) of the buffer."""
        return self._stream.getvalue()

    def getbuffer(self):
        """Return a readable and writable view of the buffer."""
        return self._stream.getbuffer()

    def close(self):
        """Close the stream."""
        return self._stream.close()

    async def read(self, size=None):
        """Read from the stream."""
        return self._stream.read(size)

    async def read1(self, size):
        """Read from the stream."""
        return self._stream.read1(size)

    def write(self, b):
        """Write to the stream."""
        return self._stream.write(b)

    async def seek(self, pos, whence=0):
        """Change the stream position."""
        return self._stream.seek(pos, whence)

    async def tell(self):
        """Get the stream position."""
        return self._stream.tell()

    async def truncate(self, pos=None):
        """Truncate the stream."""
        return self._stream.truncate(pos)

    def readable(self):
        """Get if the stream is readable."""
        return self._stream.readable()

    def writable(self):
        """Get if the stream is writable."""
        return self._stream.writable()

    def seekable(self):
        """Get if the stream is seekable."""
        return self._stream.seekable()


class AsyncBufferedReaderWrapper(AsyncBufferedIOBaseWrapper):

    """BufferedReader object wrapper for async compatibility."""

    async def read(self, size=None):
        """Read size bytes.

        Returns exactly size bytes of data unless the underlying raw IO
        stream reaches EOF or if the call would block in non-blocking
        mode. If size is negative, read until EOF or until read() would
        block.
        """
        return self._stream.read(size)

    async def peek(self, size=0):
        """Return buffered bytes without advancing the position.

        The argument indicates a desired minimal number of bytes; we
        do at most one raw read to satisfy it.  We never return more
        than self.buffer_size.
        """
        return self._stream.peek(size)

    async def read1(self, size):
        """Read up to size bytes, with at most one read() system call."""
        return self._stream.read1(size)

    async def tell(self):
        """Get the current position."""
        return self._stream.tell()

    async def seek(self, pos, whence=0):
        """Change the stream position."""
        return self._stream.seek(pos, whence)


class AsyncBufferedWriterWrapper(AsyncBufferedIOBaseWrapper):

    """BufferedWriter object wrapper for async compatibility."""

    def write(self, b):
        """Write to the stream."""
        return self._stream.write(b)

    async def truncate(self, pos=None):
        """Truncate the stream."""
        return self._stream.truncate(pos)

    async def flush(self):
        """Flush the stream buffer."""
        return self._stream.flush()

    async def tell(self):
        """Get the current stream position."""
        return self._stream.tell()

    async def seek(self, pos, whence=0):
        """Change the stream position."""
        return self._stream.seek(pos, whence)


class AsyncBufferedRandomWrapper(
        AsyncBufferedWriterWrapper,
        AsyncBufferedReaderWrapper,
):

    """BufferedRandom object wrapper for async compatibility."""


class AsyncFileIOWrapper(AsyncRawIOBaseWrapper):

    """FileIO object wrapper for async compatibility."""

    def __getstate__(self):
        """Get the pickle dictionary for the stream."""
        body = self.__dict__.copy()
        body['_stream'] = body['_stream'].__getstate__()

    def __repr__(self):
        """Get the human representation of the wrapper."""
        return '<AsyncFileIOWrapper {}>'.format(self._stream)

    async def read(self, size=None):
        """Read at most size bytes, returned as bytes.

        Only makes one system call, so less data may be returned than requested
        In non-blocking mode, returns None if no data is available.
        Return an empty bytes object at EOF.
        """
        return self._stream.read(size)

    async def readall(self):
        """Read all data from the file, returned as bytes.

        In non-blocking mode, returns as much as is immediately available,
        or None if no data is available.  Return an empty bytes object at EOF.
        """
        return self._stream.readall()

    async def readinto(self, b):
        """Replicate the RawIO readinto."""
        return self._stream.readinto(b)

    def write(self, b):
        """Write bytes b to file, return number written.

        Only makes one system call, so not all of the data may be written.
        The number of bytes actually written is returned.  In non-blocking
        mode, returns None if the write would block.
        """
        return self._stream.write(b)

    async def seek(self, pos, whence=sync_io.SEEK_SET):
        """Move to new file position.

        Argument offset is a byte count.  Optional argument whence defaults to
        SEEK_SET or 0 (offset from start of file, offset should be >= 0); other
        values are SEEK_CUR or 1 (move relative to current position, positive
        or negative), and SEEK_END or 2 (move relative to end of file, usually
        negative, although many platforms allow seeking beyond the end of a
        file).

        Note that not all file objects are seekable.
        """
        return self._stream.seek(pos, whence)

    async def tell(self):
        """Get the current file position.

        Can raise OSError for non seekable files.
        """
        return self._stream.tell()

    async def truncate(self, size=None):
        """Truncate the file to at most size bytes.

        Size defaults to the current file position, as returned by tell().
        The current file position is changed to the value of size.
        """
        return self._stream.truncate(size)

    def close(self):
        """Close the file.

        A closed file cannot be used for further I/O operations.  close() may
        be called more than once without error.
        """
        return self._stream.close()

    def seekable(self):
        """True if file supports random-access."""
        return self._stream.seekable()

    def readable(self):
        """True if file was opened in a read mode."""
        return self._stream.readable()

    def writable(self):
        """True if file was opened in a write mode."""
        return self._stream.readable()

    def fileno(self):
        """Return the underlying file descriptor (an integer)."""
        return self._stream.fileno()

    def isatty(self):
        """True if the file is connected to a TTY device."""
        return self._stream.isatty()

    @property
    def closefd(self):
        """True if the file descriptor will be closed by close()."""
        return self._stream.closefd

    @property
    def mode(self):
        """Return the string giving the file mode."""
        return self._stream.mode


class AsyncTextIOBaseWrapper(AsyncIOBaseWrapper):

    """TextIOBase object wrapper for async compatibility."""

    async def read(self, size=-1):
        """Read at most size characters from stream, where size is an int.

        Read from underlying buffer until we have size characters or we hit
        EOF. If size is negative or omitted, read until EOF.

        Returns a string.
        """
        return self._stream.read(size)

    def write(self, s):
        """Write string s to stream and returning an int."""
        return self._stream.write(s)

    async def truncate(self, pos=None):
        """Truncate size to pos, where pos is an int."""
        return self._stream.truncate(pos)

    async def readline(self):
        """Read until newline or EOF.

        Returns an empty string if EOF is hit immediately.
        """
        return self._stream.readlines()

    def detach(self):
        """
        Separate the underlying buffer from the TextIOBase and return it.

        After the underlying buffer has been detached, the TextIO is in an
        unusable state.
        """
        return self._stream.detach()

    @property
    def encoding(self):
        """Get the stream encoding."""
        return self._stream.encoding

    @property
    def newlines(self):
        """Line endings translated so far.

        Only line endings translated during reading are considered.

        Subclasses should override.
        """
        return self._stream.newlines

    @property
    def errors(self):
        """Error setting of the decoder or encoder.

        Subclasses should override.
        """
        return self._stream.errors

sync_io.TextIOBase.register(AsyncTextIOBaseWrapper)


class AsyncTextIOWrapperWrapper(AsyncTextIOBaseWrapper):

    """TextIOWrapper object wrapper for async compatibility."""

    def __repr__(self):
        """Get the human representation of the wrapper."""
        return '<AsyncTextIOWrapperWrapper {}>'.format(self._stream)

    @property
    def encoding(self):
        """Get the stream encoding."""
        return self._stream.encoding

    @property
    def errors(self):
        """Get the stream errors."""
        return self._stream.errors

    @property
    def line_buffering(self):
        """Get the stream line buffering."""
        return self._stream.line_buffering

    @property
    def buffer(self):
        """Get the stream buffer."""
        return self._stream.buffer

    def seekable(self):
        """Get if the stream is seekable."""
        return self._stream.seekable()

    def readable(self):
        """Get if the stream is readable."""
        return self._stream.readable()

    def writable(self):
        """Get if the stream is writable."""
        return self._stream.writable()

    async def flush(self):
        """Flush the stream buffer."""
        return self._stream.flush()

    def close(self):
        """Close the stream."""
        return self._stream.close()

    @property
    def closed(self):
        """Get if the stream is closed."""
        return self._stream.closed

    @property
    def name(self):
        """Get the stream name."""
        return self._stream.name

    def fileno(self):
        """Get the stream fileno."""
        return self._stream.fileno()

    def isatty(self):
        """Get if the stream is a tty."""
        return self._stream.isatty()

    def write(self, s):
        """Write data, where s is a str."""
        return self._stream.write(s)

    async def tell(self):
        """Get the current stream position."""
        return self._stream.tell()

    async def truncate(self, pos=None):
        """Truncate the stream."""
        return self._stream.truncate(pos)

    def detach(self):
        """Detach the underlying stream buffer."""
        return self._stream.detach()

    async def seek(self, cookie, whence=0):
        """Set the stream position."""
        return self._stream.seek(cookie, whence)

    async def read(self, size=None):
        """Read from the stream."""
        return self._stream.read(size)

    async def __anext__(self):
        """Call the stream __next__."""
        try:
            return self._stream.__next__()

        except StopIteration as exc:

            raise StopAsyncIteration() from exc

    async def readline(self, size=None):
        """Read a line from the stream."""
        return self._stream.readline(size)

    @property
    def newlines(self):
        """Get the stream newlines."""
        return self._stream.newlines


class AsyncStringIOWrapper(AsyncTextIOWrapperWrapper):

    """StringIO object wrapper for async compatibility."""

    def getvalue(self):
        """Get the stream value."""
        return self._stream.getvalue()

    def __repr__(self):
        """Get the human representation of the wrapper."""
        return '<AsyncStringIOWrapper {}>'.format(self._stream)

    @property
    def errors(self):
        """Get the stream errors."""
        return self._stream.errors

    @property
    def encoding(self):
        """Get the stream encoding."""
        return self._stream.encoding

    def detach(self):
        """Detach the underlying stream buffer."""
        return self._stream.detach


def StringIO(*args, **kwargs):
    """StringIO constructor shim for the async wrapper."""
    raw = sync_io.StringIO(*args, **kwargs)
    return AsyncStringIOWrapper(raw)


def BytesIO(*args, **kwargs):
    """BytesIO constructor shim for the async wrapper."""
    raw = sync_io.BytesIO(*args, **kwargs)
    return AsyncBytesIOWrapper(raw)
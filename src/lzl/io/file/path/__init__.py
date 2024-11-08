import os
import sys
import anyio
import typing as t

# if 3.10
if sys.version_info.minor < 9:
    import pathlib
    from pathlib import PosixPath, WindowsPath, Path, PurePath, _ignore_error
    from pathlib import _NormalAccessor as NormalAccessor
    from pathlib import _make_selector as _sync_make_selector
    from pathlib import _PosixFlavour, _WindowsFlavour
    try:
        from pathlib import _getfinalpathname
        from aiopath.wrap import func_to_async_func
        _async_getfinalpathname = func_to_async_func(_getfinalpathname)
    except ImportError:
        def _getfinalpathname(*args, **kwargs):
            raise ImportError("_getfinalpathname() requires a Windows/NT platform")
    
        async def _async_getfinalpathname(*args, **kwargs):
            raise ImportError("_getfinalpathname() requires a Windows/NT platform")
else:
    from . import lib as pathlib
    from .lib import PosixPath, WindowsPath, Path, PurePath, _ignore_error
    from .lib import _NormalAccessor as NormalAccessor
    from .lib import _make_selector as _sync_make_selector
    from .lib import _PosixFlavour, _WindowsFlavour
    from .lib import _getfinalpathname, _async_getfinalpathname

from .lib import get_file_info, guess_type

TextMode = \
  t.Literal['r', 'w', 'a', 'x', 'r+', 'w+', 'a+', 'x+']
BinaryMode = \
  t.Literal['rb', 'wb', 'ab', 'xb', 'r+b', 'w+b', 'a+b', 'x+b']
FileMode = t.Union[TextMode, BinaryMode]


DEFAULT_ENCODING: t.Final[str] = 'utf-8'
ON_ERRORS: t.Final[str] = 'ignore'
NEWLINE: t.Final[str] = '\n'

BEGINNING: t.Final[int] = 0
CHUNK_SIZE: t.Final[int] = 4 * 1_024

SEP: t.Final[str] = '\n'
ENCODING: t.Final[str] = 'utf-8'
ERRORS: t.Final[str] = 'replace'

FileData = t.Union[bytes, str]
Handle = anyio.AsyncFile
Paths = t.Union[Path, os.PathLike, str]
from __future__ import annotations

import typing as t
import contextlib
from lzl.proxied import ProxyObject

if t.TYPE_CHECKING:    
    from lzl.io.ser import JsonSerializer
    from lzl.io import FileLike


def get_json_ser(*args, **kwargs) -> 'JsonSerializer':
    """
    [str] Get the JSON serializer.
    """
    from lzl.io.ser import get_serializer
    return get_serializer('json')

def get_jsonb_ser(*args, **kwargs) -> 'JsonSerializer':
    """
    [bytes] Get the JSON serializer.
    """
    from lzl.io.ser import get_serializer
    return get_serializer('json', enforce_byte_value=True)


jsonb_ser: 'JsonSerializer' = ProxyObject(obj_getter = get_jsonb_ser)
json_ser: 'JsonSerializer' = ProxyObject(obj_getter = get_json_ser)

_registered_file_aexit: bool = False
_registered_file_exit: bool = False

_created_tempfiles: t.Set['FileLike'] = set()

def cleanup_files_on_exit():
    """
    Cleanup temporary files on exit.
    """
    # for f in _created_tempfiles:
    while _created_tempfiles:
        f = _created_tempfiles.pop()
        with contextlib.suppress(Exception):
            f.unlink(missing_ok=True)
            # print(f"Deleted temporary file: {f}")
        # _created_tempfiles.discard(f)

async def acleanup_files_on_exit():
    """
    Cleanup temporary files on exit.
    """
    # for f in _created_tempfiles:
    while _created_tempfiles:
        f = _created_tempfiles.pop()
        with contextlib.suppress(Exception):
            await f.aunlink(missing_ok=True)
            # print(f"Deleted temporary file: {f}")
        # _created_tempfiles.discard(f)

def register_file_exit(*args, **kwargs):
    """
    Register a file exit handler.
    """
    global _registered_file_exit, _registered_file_aexit
    if not _registered_file_exit:
        import atexit
        atexit.register(cleanup_files_on_exit)
        _registered_file_exit = True
    # if not _registered_file_aexit:
    #     from lzo.utils import aioexit
    #     aioexit.register(cleanup_files_on_exit)


def add_file_to_cleanup(file: 'FileLike'):
    """
    Add a file to the cleanup list.
    """
    register_file_exit()
    _created_tempfiles.add(file)
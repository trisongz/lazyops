from __future__ import annotations

import os
from errno import EINVAL
from typing import Optional, Callable, Awaitable, Dict, List, TYPE_CHECKING
from aiopath.wrap import func_to_async_func
from .lib import _PosixFlavour, _WindowsFlavour, _getfinalpathname, _async_getfinalpathname

if TYPE_CHECKING:  # keep mypy quiet
    from ..types.base import FilePath, _FileAccessor
    # from fileio.lib.base import FilePath, _FileAccessor


class _FilePosixFlavour(_PosixFlavour):
    
    def gethomedir(self, username: str) -> str:
        return super().gethomedir(username)

    async def agethomedir(self, username: str) -> str:
        gethomedir: Callable[[str], Awaitable[str]] = func_to_async_func(super().gethomedir)
        return await gethomedir(username)

    def resolve(self, path: FilePath, strict: bool = False) -> Optional[str]:
        sep: str = self.sep
        accessor: '_FileAccessor' = path._accessor
        seen: Dict[str, Optional[str]] = {}

        def _resolve(path: str, rest: str) -> str:
            if rest.startswith(sep): path = ''

            for name in rest.split(sep):
                if not name or name == '.': continue

                if name == '..':
                    # parent dir
                    path, _, _ = path.rpartition(sep)
                    continue

                newpath = path + name if path.endswith(sep) else path + sep + name
                if newpath in seen:
                    # Already seen this path
                    path = seen[newpath]
                    if path is not None: continue

                    # The symlink is not resolved, so we must have a symlink loop.
                    raise RuntimeError(f"Symlink loop from {newpath}")

                # Resolve the symbolic link
                try: target = accessor.readlink(newpath)

                except OSError as e:
                    if e.errno != EINVAL and strict: raise
                    # Not a symlink, or non-strict mode. We just leave the path
                    # untouched.
                    path = newpath
                else:
                    seen[newpath] = None # not resolved symlink
                    path = _resolve(path, target)
                    seen[newpath] = path # resolved symlink

            return path
        
        # NOTE: according to POSIX, getcwd() cannot contain path components
        # which are symlinks.
        base = '' if path.is_absolute() else os.getcwd()
        result = _resolve(base, str(path))
        return result or sep

    async def aresolve(self, path: FilePath, strict: bool = False) -> Optional[str]:
        sep: str = self.sep
        accessor: '_FileAccessor' = path._accessor
        seen: Dict[str, Optional[str]] = {}

        async def _resolve(path: str, rest: str) -> str:
            if rest.startswith(sep): path = ''

            for name in rest.split(sep):
                if not name or name == '.': continue

                if name == '..':
                    # parent dir
                    path, _, _ = path.rpartition(sep)
                    continue

                newpath = path + name if path.endswith(sep) else path + sep + name
                if newpath in seen:
                    # Already seen this path
                    path = seen[newpath]
                    if path is not None: continue

                    # The symlink is not resolved, so we must have a symlink loop.
                    raise RuntimeError(f"Symlink loop from {newpath}")

                # Resolve the symbolic link
                try: target = await accessor.areadlink(newpath)

                except OSError as e:
                    if e.errno != EINVAL and strict: raise
                    # Not a symlink, or non-strict mode. We just leave the path
                    # untouched.
                    path = newpath
                else:
                    seen[newpath] = None # not resolved symlink
                    path = await _resolve(path, target)
                    seen[newpath] = path # resolved symlink

            return path
        
        # NOTE: according to POSIX, getcwd() cannot contain path components
        # which are symlinks.
        base = '' if path.is_absolute() else os.getcwd()
        result = await _resolve(base, str(path))
        return result or sep


class _FileWindowsFlavour(_WindowsFlavour):
    def gethomedir(self, username: str) -> str: 
        return super().gethomedir(username)

    async def agethomedir(self, username: str) -> str: 
        gethomedir: Callable[[str], Awaitable[str]] = func_to_async_func(super().gethomedir)
        return await gethomedir(username)

    def resolve(self, path: 'FilePath', strict: bool = False) -> Optional[str]:
        s = str(path)

        if not s: return os.getcwd()

        previous_s: Optional[str] = None
        if _getfinalpathname is not None:
            if strict: return self._ext_to_normal(_getfinalpathname(s))
      
        else:
            tail_parts: List[str] = []  # End of the path after the first one not found
            while True:
                try: s = self._ext_to_normal(_getfinalpathname(s))
                except FileNotFoundError:
                    previous_s = s
                    s, tail = os.path.split(s)
                    tail_parts.append(tail)
                    if previous_s == s: return path
                else: return os.path.join(s, *reversed(tail_parts))
        return None
    
    async def aresolve(self, path: '_FileAccessor', strict: bool = False) -> Optional[str]:
        s = str(path)

        if not s: return os.getcwd()

        previous_s: Optional[str] = None
        if _async_getfinalpathname is not None:
            if strict: return self._ext_to_normal(await _async_getfinalpathname(s))
      
        else:
            tail_parts: List[str] = []  # End of the path after the first one not found
            while True:
                try: s = self._ext_to_normal(await _async_getfinalpathname(s))
                except FileNotFoundError:
                    previous_s = s
                    s, tail = os.path.split(s)
                    tail_parts.append(tail)
                    if previous_s == s: return path
                else: return os.path.join(s, *reversed(tail_parts))
        return None


_pathz_windows_flavour = _FileWindowsFlavour()
_pathz_posix_flavour = _FilePosixFlavour()

_pathz_default_flavor = _pathz_posix_flavour if os.name != 'nt' else _pathz_windows_flavour
from __future__ import annotations

"""Helpers for temporary, self-cleaning persistence files."""

import abc
import atexit
import contextlib
import os
import pathlib
import tempfile
import typing as t

from lzl import load
from lzl.logging import logger

if load.TYPE_CHECKING:
    import filelock
else:
    filelock = load.LazyLoad("filelock", install_missing=True)

if t.TYPE_CHECKING:
    from filelock import SoftFileLock

MutableMappingT = dict[str, t.Any]


class TemporaryData(abc.ABC):
    """Dictionary-like interface backed by an auto-cleaned JSON file."""

    def __init__(
        self,
        filepath: str | pathlib.Path | None = None,
        filedir: pathlib.Path | None = None,
        is_multithreaded: bool | None = False,
        timeout: int | None = 10,
    ) -> None:
        """Prepare the on-disk file and optional file lock used by the store."""

        if filedir is not None:
            if filepath is not None:
                filepath = filedir.joinpath(filepath)
            else:
                filepath = filedir.joinpath(f"{os.getpid()}.tmp.json")
        if not filepath:
            filepath = pathlib.Path(tempfile.mktemp())
        self.filepath = pathlib.Path(filepath)
        self._created_dir = not self.filepath.parent.exists()

        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filelock_path = self.filepath.with_suffix(".lock")
        self.timeout = timeout
        self.is_multithreaded = bool(is_multithreaded)
        self._filelock: "SoftFileLock | None" = None
        from lzl.io.ser import get_serializer

        self.serializer = get_serializer("json")

    @property
    def filelock(self) -> "SoftFileLock":
        """Return (and lazily create) the file lock guarding the JSON file."""

        if self._filelock is None:
            try:
                self._filelock = filelock.SoftFileLock(
                    self.filelock_path.as_posix(),
                    timeout=self.timeout,
                    thread_local=False,
                )
                with self._filelock.acquire():
                    if not self.filepath.exists():
                        self.filepath.write_text("{}")
                    data = self.serializer.loads(self.filepath.read_text())
                    if self.is_multithreaded and not data.get("process_id"):
                        data["process_id"] = os.getpid()
                        self.filepath.write_text(self.serializer.dumps(data, indent=2))
                atexit.register(self.cleanup_on_exit)
            except Exception as exc:  # pragma: no cover - logging path
                from lazyops.libs.logging import logger as lazy_logger

                lazy_logger.trace(f"Error creating filelock for {self.filepath}", exc)
                raise exc
        return self._filelock

    def _load_data(self) -> MutableMappingT:
        """Load the backing JSON document into memory."""

        if not self.filepath.exists():
            self.filepath.write_text("{}")
        return self.serializer.loads(self.filepath.read_text())

    @property
    def data(self) -> MutableMappingT:
        """Return the current JSON payload guarded by the file lock."""

        try:
            with self.filelock.acquire():
                return self._load_data()
        except filelock.Timeout as exc:  # pragma: no cover - timing dependent
            from lazyops.libs.logging import logger as lazy_logger

            lazy_logger.trace(f"Filelock timeout for {self.filepath}")
            raise exc

    @contextlib.contextmanager
    def ctx(self) -> t.Generator[MutableMappingT, None, None]:
        """Context manager yielding mutable JSON data with automatic flush."""

        try:
            with self.filelock.acquire():
                data = self._load_data()
                try:
                    yield data
                finally:
                    self.filepath.write_text(self.serializer.dumps(data, indent=2))
        except filelock.Timeout as exc:  # pragma: no cover - timing dependent
            logger.trace(f"Filelock timeout for {self.filepath}", exc)
            raise exc

    def get(self, key: str, default: t.Any | None = None) -> t.Any:
        """Return ``data[key]`` if present, otherwise ``default``."""

        return self.data.get(key, default)

    def __contains__(self, key: str) -> bool:
        """Return ``True`` when ``key`` exists in the cached data."""

        return key in self.data

    def __getitem__(self, key: str) -> t.Any:
        """Return the value stored for ``key`` or ``None`` when missing."""

        return self.data.get(key)

    def __setitem__(self, key: str, value: t.Any) -> None:
        """Persist ``value`` under ``key`` and flush to disk immediately."""

        with self.ctx() as data:
            data[key] = value

    def __delitem__(self, key: str) -> None:
        """Remove ``key`` from the stored data."""

        with self.ctx() as data:
            del data[key]

    def __iter__(self) -> t.Iterator[str]:
        """Return an iterator over stored keys."""

        return iter(self.data)

    def __len__(self) -> int:
        """Return the number of stored keys."""

        return len(self.data)

    def __repr__(self) -> str:  # pragma: no cover - convenience method
        return repr(self.data)

    def __str__(self) -> str:  # pragma: no cover - convenience method
        return str(self.data)

    def __bool__(self) -> bool:
        """Return ``True`` when the store contains at least one value."""

        return bool(self.data)

    def __eq__(self, other: t.Any) -> bool:
        """Compare the stored data with an arbitrary object."""

        return self.data == other

    def keys(self) -> t.Set[str]:
        """Return the set-like view of stored keys."""

        return self.data.keys()

    def setdefault(self, key: str, default: t.Any) -> t.Any:
        """Return ``data[key]`` if present, otherwise persist and return ``default``."""

        with self.ctx() as data:
            value = data.setdefault(key, default)
        return value

    def close(self) -> None:
        """Release the file lock safeguarding the JSON payload."""

        self.filelock.release()

    def append(self, key: str, value: t.Any) -> bool:
        """Append ``value`` to the list stored at ``key`` if it is unique."""

        with self.ctx() as data:
            if key not in data:
                data[key] = []
            if value not in data[key]:
                data[key].append(value)
                return False
        return True

    def cleanup_on_exit(self) -> None:
        """Remove the persisted files when the interpreter shuts down."""

        if not self.filepath.exists() and not self.filelock_path.exists():
            return
        if self.is_multithreaded and self["process_id"] != os.getpid():
            return
        with contextlib.suppress(Exception):
            self.close()
            self.filepath.unlink()
            self.filelock_path.unlink()
            if self._created_dir:
                contents = os.listdir(self.filepath.parent.as_posix())
                if not contents:
                    self.filepath.parent.rmdir()

    def has_logged(self, key: str) -> bool:
        """Return ``True`` if ``key`` has already been appended to ``logged``."""

        return self.append("logged", key)

    @classmethod
    def from_module(
        cls,
        module_name: str,
        data_dir: str | None = ".data",
        is_multithreaded: bool | None = False,
        **kwargs: t.Any,
    ) -> "TemporaryData":
        """Construct a :class:`TemporaryData` instance scoped to ``module_name``."""

        from lzo.utils.helpers.base import get_module_path

        module_path = get_module_path(module_name)
        module_dir = module_path.joinpath(data_dir or ".data")
        module_dir.mkdir(parents=True, exist_ok=True)
        filepath = module_dir.joinpath(f"{module_name}.tmp.json")
        if not filepath.exists():
            filepath.write_text("{}")
        return cls(filepath=filepath, is_multithreaded=is_multithreaded, **kwargs)


__all__ = ["TemporaryData"]

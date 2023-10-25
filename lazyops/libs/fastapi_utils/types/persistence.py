from __future__ import annotations

import os
import abc
import atexit
import tempfile
import pathlib
import filelock
import contextlib
from lazyops.utils.serialization import Json
from typing import Optional, Dict, Any, Set, List, Union, TYPE_CHECKING



class TemporaryData(abc.ABC):
    """
    Temporary Data that deletes itself on exit
    """
    def __init__(
        self, 
        filepath: Optional[pathlib.Path] = None,
        is_multithreaded: Optional[bool] = False,
    ):
        if not filepath: filepath = pathlib.Path(tempfile.mktemp())
        self.filepath = filepath
        self.filelock_path = filepath.with_suffix('.lock')
        self.filelock = filelock.FileLock(lock_file = self.filelock_path.as_posix(), thread_local = False)
        self.is_multithreaded = is_multithreaded
        with self.filelock:
            if not self.filepath.exists():
                self.filepath.write_text('{}')
        if self.is_multithreaded and not self.get('process_id'):
            self['process_id'] = os.getpid()
        atexit.register(self.cleanup_on_exit)

    @property
    def data(self) -> Dict[str, Any]:
        """
        Returns the data
        """
        with self.filelock:
            return Json.loads(self.filepath.read_text())
        
    @contextlib.contextmanager
    def ctx(self) -> Dict[str, Union[List[Any], Dict[str, Any], Any]]:
        """
        Returns the context
        """
        with self.filelock:
            try:
                data = self.data
                yield data
            finally:
                self.filepath.write_text(Json.dumps(data, indent = 2))
    
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Returns the value for the given key
        """
        return self.data.get(key, default)
    
    def __contains__(self, key: str) -> bool:
        """
        Returns whether the key is in the data
        """
        return key in self.data
    
    def __getitem__(self, key: str) -> Any:
        """
        Returns the value for the given key
        """
        return self.data.get(key)
    
    def __setitem__(self, key: str, value: Any):
        """
        Sets the value for the given key
        """
        with self.ctx() as data:
            data[key] = value

    def __delitem__(self, key: str):
        """
        Deletes the value for the given key
        """
        with self.ctx() as data:
            del data[key]


    def __iter__(self):
        """
        Returns the iterator
        """
        return iter(self.data)
    
    def __len__(self) -> int:
        """
        Returns the length
        """
        return len(self.data)
    
    def __repr__(self) -> str:
        """
        Returns the representation
        """
        return repr(self.data)
    
    def __str__(self) -> str:
        """
        Returns the string representation
        """
        return str(self.data)
    
    def __bool__(self) -> bool:
        """
        Returns whether the data is empty
        """
        return bool(self.data)
    
    def __eq__(self, other: Any) -> bool:
        """
        Returns whether the data is equal to the other
        """
        return self.data == other
    
    def keys(self) -> Set[str]:
        """
        Returns the keys
        """
        return self.data.keys()
    
    def setdefault(self, key: str, default: Any) -> Any:
        """
        Sets the default value for the given key
        """
        with self.ctx() as data:
            value = data.setdefault(key, default)
        return value
        
    def close(self):
        """
        Closes the filelock
        """
        self.filelock.release()

    def append(self, key: str, value: Any) -> bool:
        """
        Appends the value to the list
        """
        with self.ctx() as data:
            if key not in data:
                data[key] = []
            if value not in data[key]:
                data[key].append(value)
                return False
        return True

    def cleanup_on_exit(self):
        """
        Cleans up on exit
        """
        if not self.filepath.exists() and not self.filelock_path.exists():
            return
        if self.is_multithreaded and self['process_id'] != os.getpid():
            return
        with contextlib.suppress(Exception):
            self.close()
            self.filepath.unlink()
            self.filelock_path.unlink()


    def has_logged(self, key: str) -> bool:
        """
        Returns whether the key has been logged
        """
        return self.append('logged', key)
        
    @classmethod
    def from_module(
        cls, 
        module_name: str, 
        data_dir: Optional[str] = '.data', 
        is_multithreaded: Optional[bool] = False,
        **kwargs
    ) -> TemporaryData:
        """
        Returns a temporary data from the module
        """
        from lazyops.utils.assets import get_module_path
        module_path = get_module_path(module_name)
        module_dir = module_path.joinpath(data_dir)
        module_dir.mkdir(parents = True, exist_ok = True)
        filepath = module_dir.joinpath(f'{module_name}.tmp.json')
        return cls(filepath = filepath, is_multithreaded = is_multithreaded, **kwargs)
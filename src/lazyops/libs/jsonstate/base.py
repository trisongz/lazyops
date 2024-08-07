import os
import json
import aiofile
import contextlib
import functools
import hashlib
from pathlib import Path
from abc import ABC, abstractmethod
from filelock import FileLock
from typing import Callable, Optional, Dict, Any

json_dumps_func = functools.partial(json.dumps, ensure_ascii=False, indent=4)

class BaseJsonState(ABC):

    def __init__(
        self,
        name: str,
        dir_path: str,
        json_dumps: Callable[[dict], str] = json_dumps_func,
        json_loads: Callable[[str], dict] = json.loads,
        **kwargs,
    ):
        self.name = name
        self.dir_path = dir_path
        self.file_name = os.path.join(self.dir_path, f'{self.name}.json')
        self.lockfile_name = os.path.join(self.dir_path, f'{self.name}.lock')
        self.file_path = Path(self.file_name)
        self.lockfile_path = Path(self.lockfile_name)
        self.lock = FileLock(self.lockfile_name)
        self.json_dumps = json_dumps
        self.json_loads = json_loads
        self._data: Optional[Dict[Any, Any]] = {}

    
    @property
    def _checksum(self):
        return os.stat(self.file_name).st_size

    def _write(self):
        """
        Write data to file
        """
        with self.lock:
            with self.file_path.open('w', encoding='utf-8') as f:
                f.write(self.json_dumps(self._data))
    
    def _read(self):
        """
        Read data from file
        """
        if not self.file_path.exists():
            self.file_path.touch()
            return
        with self.lock:
            with self.file_path.open('r+', encoding='utf-8') as f:
                self._data = self.json_loads(f.read())

    @contextlib.contextmanager
    def ctx(self, is_writer: bool = False):
        """
        Handle the file lock for writing
        """
        try:
            yield
        finally:
            if is_writer: 
                self._write()





    


    

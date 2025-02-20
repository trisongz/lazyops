from __future__ import annotations

"""
Remote Object Storage Backend Dict-Like Persistence
"""

import re
import abc
import time
import datetime
import contextlib
from lzo.types import BaseModel, Field, model_validator, Literal, eproperty
from lzl.io.file import File
from typing import TypeVar, Generic, Any, Dict, Optional, Union, Tuple, Iterable, List, Type, Callable, Generator, AsyncGenerator, TYPE_CHECKING
from ..base import logger

if TYPE_CHECKING:
    from kvdb import Lock, AsyncLock
    from lzl.io.file import FileLike
    from .main import ObjStorageStatefulBackend


class ExpObject(BaseModel):
    """
    The Expiration Object
    """
    key: str
    ex: int
    expires_at: datetime.datetime
    
    @property
    def is_expired(self) -> bool:
        """
        Returns True if the Object is Expired

        - We only cache it if it is expired
        """
        if 'is_expired' not in self._extra and \
            self.expires_at < datetime.datetime.now(tz=datetime.timezone.utc):
                self._extra['is_expired'] = True
        return self._extra.get('is_expired', False)
    
    def set_new_exp(self, ex: int):
        """
        Sets a New Expiration
        """
        self.expires_at = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(seconds = ex)

    @classmethod
    def create(cls, key: str, ex: int):
        """
        Creates a new expiration object
        """
        return cls(key = key, ex = ex, expires_at = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(seconds = ex))


class ExpirationFile(BaseModel):
    """
    The Expiration File
    """
    index: Dict[str, ExpObject] = Field(default_factory = dict)

    def add_exp(self, key: str, ex: int):
        """
        Adds an Expiration
        """
        self.index[key] = ExpObject(key = key, ex = ex, expires_at = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(seconds = ex))


    def set_exp(self, key: str, ex: int):
        """
        Sets an Expiration
        """
        if key not in self.index:
            self.add_exp(key, ex)
        else:
            self.index[key].set_new_exp(ex)

    def set_exps(self, *keys: str, ex: int):
        """
        Sets an Expiration
        """
        for key in keys:
            self.set_exp(key, ex)

    def remove_exps(self, *keys: str):
        """
        Removes an Expiration
        """
        for key in keys:
            _ = self.index.pop(key, None)

    def get_expired_keys(self) -> List[str]:
        """
        Returns the Expired Keys
        """
        return [
            key
            for key, exp_obj in self.index.items()
            if exp_obj.is_expired
        ]

class ExpirationBackend(abc.ABC):
    """
    Expiration Backend
    """
    name: Optional[str] = None

    def __init__(self, backend: 'ObjStorageStatefulBackend'):
        """
        Initializes the Expiration Backend
        """
        self._extra: Dict[str, Any] = {}
        self.backend = backend
        self._setup_()
        self._handle_migration_()

    def _handle_migration_(self):
        """
        Handles the migration
        """
        pass
    
    def _setup_(self):
        """
        Sets up the expiration backend
        """
        pass
    
    @classmethod
    def is_available(cls) -> bool:
        """
        Returns whether the backend is available
        """
        return True
    

    def _check(self, *keys: str, validate: Optional[bool] = False, **kwargs):
        """
        Runs the expiration check

        Previously: `_run_expiration_check`
        """
        pass

    async def _acheck(self, *keys: str, validate: Optional[bool] = False, **kwargs):
        """
        Runs the expiration check

        Previously: `_arun_expiration_check`
        """
        pass


    def _set(self, *keys: str, ex: Optional[int] = None, validate: Optional[bool] = False, **kwargs):
        """
        Sets the expiration

        Previously: `_set_expiration`
        """
        pass

    async def _aset(self, *keys: str, ex: Optional[int] = None, validate: Optional[bool] = False, **kwargs):
        """
        Sets the expiration

        Previously: `_set_expiration`
        """
        pass

    def _remove(self, *keys: str, **kwargs):
        """
        Removes the expiration
        
        Previously: `_remove_expiration`
        """
        pass

    async def _aremove(self, *keys: str, **kwargs):
        """
        Removes the expiration
        
        Previously: `_remove_expiration`
        """
        pass


class FileExpirationBackend(ExpirationBackend):
    """
    File Expiration Backend
    """
    name: Optional[str] = 'file'

    def _setup_(self):
        """
        Sets up the expiration backend
        """
        from lzl.io.ser import get_serializer
        self.exp_file: 'File' = self.backend.base_key.joinpath(f'.{self.backend.name}.metadata.expires')
        self.ser = get_serializer(serializer = 'json')

    def _load(self, *args, **kwargs) -> 'ExpirationFile':
        """
        Loads the Expirations
        """
        if not self.exp_file.exists(): return ExpirationFile()
        try:
            return self.ser.loads(self.exp_file.read_text())
        except Exception as e:
            logger.error(f'Error Loading Expirations: {e}')
            return ExpirationFile()

    def _save(self, exps: 'ExpirationFile', **kwargs):
        """
        Saves the Expirations
        """
        self.exp_file.write_text(self.ser.dumps(exps))
    
    async def _aload(self, *args, **kwargs) -> 'ExpirationFile':
        """
        Loads the Expirations
        """
        if not await self.exp_file.aexists(): return ExpirationFile()
        try:
            return await self.ser.aloads(await self.exp_file.aread_text())
        except Exception as e:
            logger.error(f'Error Loading Expirations: {e}')
            return ExpirationFile()

    async def _asave(self, exps: 'ExpirationFile', **kwargs):
        """
        Saves the Expirations
        """
        await self.exp_file.awrite_text(await self.ser.adumps(exps))

    @contextlib.contextmanager
    def handler(self, *args, **kwargs) -> Generator['ExpirationFile', None, None]:
        """
        Handles the expiration file
        """
        exps = self._load()
        try:
            yield exps
        except Exception as e:
            logger.error(f'Error Handling Expirations: {e}')
        finally:
            self._save(exps)
            # logger.info(f'Saved Expirations: {exps}')
            
    @contextlib.asynccontextmanager
    async def ahandler(self, *args, **kwargs) -> AsyncGenerator['ExpirationFile', None]:
        """
        Handles the expiration file
        """
        exps = await self._aload()
        try:
            yield exps
        except Exception as e:
            logger.error(f'Error Handling Expirations: {e}')
        finally:
            await self._asave(exps)
            # logger.info(f'Saved Expirations: {exps}')

    def _check(self, *keys: str, **kwargs):
        """
        Runs the expiration check
        """
        # Maps to _arun_expiration_check
        if not self.exp_file.exists(): return
        with self.handler() as exps:
            expired_keys = exps.get_expired_keys()
            if expired_keys: 
                self.backend._clear(*expired_keys)
                exps.remove_exps(*keys)

    async def _acheck(self, *keys: str, **kwargs):
        """
        Runs the expiration check
        """
        # Maps to _arun_expiration_check
        # if self.exp_file is None: return
        if not await self.exp_file.aexists(): return
        async with self.ahandler() as exps:
            expired_keys = exps.get_expired_keys()
            if expired_keys: 
                await self.backend._aclear(*expired_keys)
                exps.remove_exps(*keys)

    def _set(self, *keys: str, ex: Optional[int] = None, validate: Optional[bool] = False, **kwargs):
        """
        Sets the expiration for the keys
        """
        # logger.info(f'Setting Expirations: {keys} -> {ex}')
        ex = ex or self.backend.expiration
        if ex is None: return
        with self.handler() as exps:
            exps.set_exps(*keys, ex = ex)
            if validate: 
                expired_keys = exps.get_expired_keys()
                if expired_keys: 
                    self.backend._clear(*expired_keys)
                    exps.remove_exps(*expired_keys)

    async def _aset(self, *keys: str, ex: Optional[int] = None, validate: Optional[bool] = False, **kwargs):
        """
        Sets the expiration
        """
        # logger.info(f'Setting Expirations: {keys} -> {ex}')
        ex = ex or self.backend.expiration
        if ex is None: return
        async with self.ahandler() as exps:
            exps.set_exps(*keys, ex = ex)
            if validate: 
                expired_keys = exps.get_expired_keys()
                if expired_keys: 
                    await self.backend._aclear(*expired_keys)
                    exps.remove_exps(*expired_keys)

    def _remove(self, *keys: str, **kwargs):
        """
        Removes the expiration
        """
        if not self.exp_file.exists(): return
        with self.handler() as exps:
            exps.remove_exps(*keys)

    async def _aremove(self, *keys: str, **kwargs):
        """
        Removes the expiration
        """
        if not await self.exp_file.aexists(): return
        async with self.ahandler() as exps:
            exps.remove_exps(*keys)


class RedisExpirationBackend(ExpirationBackend):
    """
    Redis Expiration Backend
    """
    name: Optional[str] = 'redis'
    _is_avail: Optional[bool] = None

    def _setup_(self):
        """
        Sets up the expiration backend
        """
        from kvdb import KVDBClient
        from lzl.io.ser import get_serializer
        from lzl.ext.aiorun import create_task
        from lzo.utils.aioexit import register
        
        # >>> s3://mybucket/mykey/file.metadata.expires
        # >>> mybucket.mykey.file.metadata:expirations
        self.create_task = create_task
        self.keybase = self.backend.base_key.as_posix().split('://', 1)[-1].replace('/', '.')
        self.exp_base_key = f'_fexp_:{self.keybase}'
        self.ser = get_serializer(serializer = 'json')
        self.session = KVDBClient.get_session(
            name = f'{self.backend.name}.expirations',
            serializer = None,
            decode_responses = True, 
            # serializer = 'json',
        )
        # register(self._finalize_)
    
    @eproperty
    def lock(self) -> 'Lock':
        """
        Returns the lock
        """
        return self.session.lock(
            f'{self.keybase}:lock',
            timeout = 60 * 5,
            blocking = True,
        )
    
    @eproperty
    def alock(self) -> 'AsyncLock':
        """
        Returns the async lock
        """
        return self.session.alock(
            f'{self.keybase}:lock',
            timeout = 60 * 5,
            blocking = True,
        )

        
    def _handle_migration_(self):
        """
        Handles the migration
        """
        # Check whether the key exists
        with self.lock:
            if self.session.exists(self.exp_base_key): return

            exp_file: 'File' = self.backend.base_key.joinpath(f'.{self.backend.name}.metadata.expires')
            if not exp_file.exists(): return

            logger.info(f'Migrating Expirations from {exp_file} to {self.exp_base_key} (File -> Redis)')
            exps: 'ExpirationFile' = self.ser.loads(exp_file.read_text())
            set_data = {key: exp.expires_at.timestamp() for key, exp in exps.index.items()}

            self.session.hmset(self.exp_base_key, set_data)
            logger.info(f'Migrated `{len(set_data)}` Expirations from {exp_file} to {self.exp_base_key} (File -> Redis)')
        
        # exp_file.unlink()

    @classmethod
    def is_available(cls) -> bool:
        """
        Returns whether the backend is available
        """
        if cls._is_avail is not None: return cls._is_avail
        try:
            import os
            import kvdb
            import socket
            from lzo.utils.helpers.envvars import is_in_ci_env
            if not os.getenv('REDIS_URL') or is_in_ci_env(): return False
            # Check that the host is available
            socket.gethostbyname(os.getenv('REDIS_URL').split('://', 1)[-1].split(':', 1)[0])
            cls._is_avail = True
            return True
        
        except ImportError as e:
            cls._is_avail = False
            return False
        
        except Exception as e:
            logger.error(f'Error validating Redis Availability: {e}')
            return False


    def _validate(self, *args, ignore_keys: Iterable[str] = None, **kwargs):
        """
        Validates the expired keys
        """
        expired_keys = []
        with self.lock:
            now = time.time()
            if not self.session.exists(self.exp_base_key): return
            exps = self.session.hgetall(self.exp_base_key)
            for key, exp in exps.items():
                if ignore_keys and key in ignore_keys: continue
                try:
                    exp = float(exp)
                    if exp <= now:
                        expired_keys.append(key)
                        continue
                except Exception as e:
                    logger.error(f'Error Parsing Expiration: {e} - {key}')
                    expired_keys.append(key)
                    continue
            
        if expired_keys: 
            self.session.hdel(self.exp_base_key, *expired_keys)
            self.backend._clear(*expired_keys)

    async def _avalidate(self, *args, ignore_keys: Iterable[str] = None, **kwargs):
        """
        Validates the expired keys
        """
        expired_keys = []
        async with self.alock:
            now = time.time()
            if not await self.session.aexists(self.exp_base_key): return
            exps = await self.session.ahgetall(self.exp_base_key)
            for key, exp in exps.items():
                if ignore_keys and key in ignore_keys: continue
                try:
                    exp = float(exp)
                    if exp <= now:
                        expired_keys.append(key)
                        continue
                except Exception as e:
                    logger.error(f'Error Parsing Expiration: {e} - {key}')
                    expired_keys.append(key)
                    continue
        if expired_keys: 
            await self.session.ahdel(self.exp_base_key, *expired_keys)
            await self.backend._aclear(*expired_keys)

    def _check(self, *keys: str, validate: Optional[bool] = False, **kwargs):
        """
        Runs the expiration check

        Previously: `_run_expiration_check`
        """
        # with self.lock:
        if not self.session.exists(self.exp_base_key): return
        expired_keys = []
        now = time.time()
        for key in keys:
            if self.session.hexists(self.exp_base_key, key):
                try:
                    exp = float(self.session.hget(self.exp_base_key, key))
                    if exp <= now:
                        expired_keys.append(key)
                        continue
                except Exception as e:
                    logger.error(f'Error Parsing Expiration: {e} - {key}')
                    expired_keys.append(key)
                    continue
        
        # if keys: self.session.hdel(self.exp_base_key, *keys)
        if expired_keys: 
            self.session.hdel(self.exp_base_key, *expired_keys)
            self.backend._clear(*expired_keys)
        if validate: self._validate(ignore_keys=keys)
    

    async def _acheck(self, *keys: str, validate: Optional[bool] = False, **kwargs):
        """
        Runs the expiration check

        Previously: `_arun_expiration_check`
        """
        # async with self.alock:
        if not await self.session.aexists(self.exp_base_key): return
        expired_keys = []
        now = time.time()
        for key in keys:
            if await self.session.ahexists(self.exp_base_key, key):
                try:
                    exp = float(await self.session.ahget(self.exp_base_key, key))
                    if exp <= now:
                        expired_keys.append(key)
                        continue
                except Exception as e:
                    logger.error(f'Error Parsing Expiration: {e} - {key}')
                    expired_keys.append(key)
                    continue
        if expired_keys: 
            await self.session.ahdel(self.exp_base_key, *expired_keys)
            await self.backend._aclear(*expired_keys)

            # if keys: await self.session.ahdel(self.exp_base_key, *keys)
        if validate: await self._avalidate(ignore_keys = keys)

    def _set(self, *keys: str, ex: Optional[int] = None, validate: Optional[bool] = False, **kwargs):
        """
        Sets the expiration

        Previously: `_set_expiration`
        """
        ex = ex or self.backend.expiration
        if ex is None: return
        with self.lock:
            exp = time.time() + ex
            mapping = {
                key: exp for key in keys
            } 
            self.session.hmset(self.exp_base_key, mapping)
        if validate: self._validate(ignore_keys = keys)

    async def _aset(self, *keys: str, ex: Optional[int] = None, validate: Optional[bool] = False, **kwargs):
        """
        Sets the expiration

        Previously: `_set_expiration`
        """
        ex = ex or self.backend.expiration
        if ex is None: return
        async with self.alock:
            exp = time.time() + ex
            mapping = {
                key: exp for key in keys
            } 
            await self.session.ahmset(self.exp_base_key, mapping)
        if validate: await self._avalidate(ignore_keys = keys)

    def _remove(self, *keys: str, **kwargs):
        """
        Removes the expiration
        
        Previously: `_remove_expiration`
        """
        if not self.session.exists(self.exp_base_key): return
        self.session.hdel(self.exp_base_key, *keys)

    async def _aremove(self, *keys: str, **kwargs):
        """
        Removes the expiration
        
        Previously: `_remove_expiration`
        """
        if not await self.session.aexists(self.exp_base_key): return
        await self.session.ahdel(self.exp_base_key, *keys)
            

"""
I/O utilities.
"""

import functools
from csv import DictReader
from lazyops.libs import lazyload
from typing import Optional, Dict, Any, List, Union, Type, Callable, TYPE_CHECKING

if lazyload.TYPE_CHECKING:
    import aiocsv
    import aiohttpx
    from pydantic import BaseModel
else:
    aiocsv = lazyload.LazyLoad("aiocsv")
    aiohttpx = lazyload.LazyLoad("aiohttpx")

if TYPE_CHECKING:
    from fileio import File


class HTTPStreamReader:
    """
    Implements an async iterator for reading from an HTTP response stream.
    """
    def __init__(
        self, 
        response: 'aiohttpx.Response', 
        chunk_size: int = 2048,
    ):
        self.response = response
        self.iterator = self.response.aiter_text(chunk_size = chunk_size)
        self.line_num = 0


    def __aiter__(self):
        return self

    async def read(self, *args, **kwargs) -> str:
        """
        Reads the next chunk from the stream.
        """
        try:
            return await anext(self.iterator)
        except StopAsyncIteration:
            return ''



class HTTPSyncStreamReader:
    """
    Implements an sync iterator for reading from an HTTP response stream.
    """
    def __init__(
        self, 
        response: 'aiohttpx.Response', 
        chunk_size: int = 2048,
    ):
        self.response = response
        # self.iterator = self.response.iter_text(chunk_size = chunk_size)
        self.iterator = self.response.iter_lines()
        self.line_num = 0

    def __iter__(self):
        return self.iterator
    
    def __next__(self):
        # self.line_num += 1
        return next(self.iterator)
    
    def read(self, *args, **kwargs) -> str:
        """
        Reads the next chunk from the stream.
        """
        try:
            # self.line_num += 1
            return next(self.iterator)
        except StopIteration:
            return ''


class CSVStreamReader:
    """
    Implements an async iterator for reading from an HTTP response stream.
    """
    def __init__(
        self, 
        response: 'aiohttpx.Response', 
        chunk_size: int = 2048,
        hooks: Optional[List[Callable]] = None,
        enable_async: Optional[bool] = True,
        **kwargs,
    ):
        self.hooks = hooks or []
        self.is_async = enable_async
        self.stream = HTTPStreamReader(response, chunk_size = chunk_size) if enable_async else HTTPSyncStreamReader(response, chunk_size = chunk_size)
        self.reader = aiocsv.AsyncDictReader(self.stream) if enable_async else DictReader(self.stream, dialect='unix')
        self.post_init(**kwargs)

    def post_init(self, **kwargs):
        """
        Post initialization hook.
        """
        pass

    def __aiter__(self):
        return self
    
    def __iter__(self):
        return self
    
    def run_hooks(self, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Runs the hooks.
        """
        for hook in self.hooks:
            values = hook(values)
            if values is None:
                return None
        return values

    async def arun_hooks(self, values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Runs the hooks.
        """
        from lazyops.libs.pooler import ThreadPooler
        for hook in self.hooks:
            values = await hook(values) if ThreadPooler.is_coro(hook) else hook(values)
            if values is None:
                return None
        return values

    async def __anext__(self) -> Dict[str, str]:
        """
        Reads the next chunk from the stream.
        """
        values = await anext(self.reader)
        return await self.arun_hooks(values)

    def __next__(self) -> Dict[str, str]:
        """
        Reads the next chunk from the stream.
        """
        values = next(self.reader)
        return self.run_hooks(values)
    

async def _parse_jsonl_record(
    record: Dict[str, Any],
    model: Type['BaseModel'],
) -> 'BaseModel':
    """
    Parses the JSONL record.
    """
    from lazyops.libs.pooler import ThreadPooler
    return await ThreadPooler.run_async(
        model.model_validate_json,
        record
    )


async def read_jsonl_records(
    file: 'File',
    model: Type['BaseModel'],
    return_ordered: Optional[bool] = False,
    **kwargs,
) -> List['BaseModel']:
    """
    Reads the JSONL records from the file.
    """
    parse_one_func = functools.partial(_parse_jsonl_record, model = model)
    records = []
    from lazyops.libs.pooler import ThreadPooler
    async with file.async_open('r') as f:
        async for item in ThreadPooler.async_iterate(
            parse_one_func,
            f, 
            return_ordered = return_ordered,
            **kwargs,
        ):
            records.append(item)
    return records
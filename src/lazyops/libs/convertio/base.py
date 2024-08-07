from __future__ import annotations

"""
The Base Class for Convertio Handlers
"""

import abc
import tempfile
from pathlib import Path, PurePath
from lazyops.utils.pooler import ThreadPoolV2
from lazyops.utils.logs import default_logger, null_logger, Logger
from typing import Any, Union, Optional, Type, Iterable, Callable, Dict, List, Tuple, TypeVar, TYPE_CHECKING

try:
    from xxhash import xxh64 as hash_func
except ImportError:
    from hashlib import md5 as hash_func

try:
    from fileio import File
except ImportError:
    File = Path

if TYPE_CHECKING:
    # from magic import FileMagic
    from fileio import FileLike

InputContentType = TypeVar('InputContentType', Union[bytes, Iterable[Union[bytes, Any]]], File, str, Any)
InputPathType = TypeVar('InputPathType', File, str, Any) # Union[Path, str, Any]
InputSourceType = TypeVar('InputSourceType', File, str, bytes, Any)
InputSourceTupleType = Tuple[int, InputSourceType]
InputSourceT = Union[InputSourceType, InputSourceTupleType]

OutputType = TypeVar('OutputType')

class InvalidTargetError(Exception):
    """
    Invalid Target Error
    """
    def __init__(
        self,
        converter: 'BaseConverter',
        target: str,
    ):
        """
        Initialize the Invalid Target Error
        """
        self.converter = converter
        self.target = target
        super().__init__(f'[{self.converter.name}] Invalid conversion target: {target} (supported: {self.converter.targets})')

class InvalidSourceError(Exception):
    """
    Invalid Source Error
    """
    def __init__(
        self,
        converter: 'BaseConverter',
        source: str,
    ):
        """
        Initialize the Invalid Source Error
        """
        self.converter = converter
        self.source = source
        super().__init__(f'[{self.converter.name}] Invalid conversion source: {source} (supported: {self.converter.source})')


class BaseConverter(abc.ABC):
    """
    The Base Conversion Class
    """
    name: Optional[str] = None
    source: Optional[str] = None # The source format
    targets: Optional[List[str]] = None # List of supported targets
    enabled: Optional[bool] = None # Whether the converter is enabled
    async_enabled: Optional[bool] = None # Whether the converter is async enabled


    def __init__(
        self,
        source: Optional[str] = None,
        targets: Optional[List[str]] = None,
        enabled: Optional[bool] = None,
        async_enabled: Optional[bool] = None,
        **kwargs,
    ):
        """
        Initialize the Converter
        """
        if source is not None: self.source = source
        if targets is not None: self.targets = targets
        if enabled is not None: self.enabled = enabled
        if async_enabled is not None: self.async_enabled = async_enabled
        
        # Remove the leading dot and convert to lowercase
        if self.source: self.source = self.source.lstrip('.').lower()
        if self.targets: self.targets = [t.lstrip('.').lower() for t in self.targets]
        
        self.pre_init(**kwargs)
        if self.enabled is None: self.enabled = self.validate_enabled(**kwargs)
        self.post_init(**kwargs)
        self.finalize_init(**kwargs)
    
    @property
    def logger(self) -> Logger:
        """
        Return the logger
        """
        return default_logger
    
    @property
    def null_logger(self) -> Logger:
        """
        Return the null logger
        """
        return null_logger
    
    @property
    def pool(self) -> Type[ThreadPoolV2]:
        """
        Return the pool
        """
        return ThreadPoolV2

    def pre_init(self, **kwargs):
        """
        Pre-initialize the converter
        """
        pass

    def post_init(self, **kwargs):
        """
        Post-initialize the converter
        """
        pass

    def finalize_init(self, **kwargs):
        """
        Finalize the converter
        """
        pass
    
    @property
    def source_ext(self) -> str:
        """
        Return the source extension
        """
        return f'.{self.source}' if self.source else None
    
    @property
    def source_mime_type(self) -> str:
        """
        Return the source mime type
        """
        return f'application/{self.source}' if self.source else None
    
    @property
    def target_exts(self) -> List[str]:
        """
        Return the target extensions
        """
        return [f'.{t}' for t in self.targets] if self.targets else None
    
    @property
    def target_mime_types(self) -> List[str]:
        """
        Return the target mime types
        """
        return [f'application/{t}' for t in self.targets] if self.targets else None

    def validate_enabled(self, **kwargs) -> bool:
        """
        Validate whether the converter is enabled
        """
        return True

    def is_valid_source_content_type(
        self,
        content_type: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Validate whether the content type is valid

        content-type: application/pdf
        """
        if '.' in content_type: content_type = content_type.split('.')[-1]
        return self.source in content_type.lower() if content_type else False
    
    def is_valid_source_type(
        self,
        data: Optional[InputSourceType] = None,
        **kwargs,
    ) -> bool:
        """
        Validate whether the data is a valid source type for conversion

        data: .pdf
        """
        if data is None: return False
        if isinstance(data, Path) or hasattr(data, 'suffix'): return data.suffix == self.source_ext
        if isinstance(data, str):
            if len(data) < 5:
                return data == self.source_ext if '.' in data else data == self.source
            return self.detect_content_type(data, mime = True) == self.source_mime_type
        return self.is_valid_source_path(data, **kwargs)

    def is_valid_source_path(
        self,
        path: Optional[InputPathType] = None,
        **kwargs,
    ) -> bool:
        """
        Validate whether the path is valid

        path: /path/to/file.pdf
        """
        if path is None: return False
    
        if not isinstance(path, str) and hasattr(path, 'suffix'): return path.suffix == self.source_ext
        return str(path).endswith(self.source_ext)
    
    def is_valid_target_content_type(
        self,
        content_type: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Validate whether the content type is a valid target content type for conversion

        content-type: application/pdf
        """
        if '.' in content_type: content_type = content_type.split('.')[-1]
        return (
            any(t in content_type.lower() for t in self.targets)
            if content_type
            else False
        )
    

    def is_valid_target_type(
        self,
        data: Optional[InputContentType] = None,
        **kwargs,
    ) -> bool:
        """
        Validate whether the data is a valid target type for conversion
        """
        if data is None: return False
        if not isinstance(data, str) and hasattr(data, 'suffix'): return data.suffix in self.target_exts
        if isinstance(data, str):
            if len(data) < 5:
                return data in self.target_exts if '.' in data else data in self.targets
            return self.detect_content_type(data, mime = True) in self.target_mime_types
        return self.is_valid_target_path(data, **kwargs)
    
    def is_valid_target_path(
        self,
        path: Optional[InputPathType] = None,
        **kwargs,
    ) -> bool:
        """
        Validate whether the path is a valid target path for conversion

        path: /path/to/file.pdf
        """
        if path is None: return False
    
        if not isinstance(path, str) and hasattr(path, 'suffix'): return path.suffix in self.target_exts
        return any(str(path).endswith(t) for t in self.target_exts)
    

    def _convert_source_to_target(
        self,
        source: InputSourceT,
        target: str, 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> OutputType:
        """
        Convert the source to the target

        source: /path/to/file.pdf
        target: '.docx'
        """
        raise NotImplementedError
    

    def convert_source_to_target(
        self,
        source: InputSourceType,
        target: str, 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> OutputType:
        """
        Convert the source to the target

        source: /path/to/file.pdf
        target: '.docx'
        """
        if not self.enabled: raise NotImplementedError(f'{self.name} is not enabled')
        return self._convert_source_to_target(
            source=source,
            target=target,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )
    
    def _convert_source_to_targets_one(
        self,
        target: Tuple[int, str], 
        source: InputSourceT,
        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,
        **kwargs,
    ) -> Tuple[int, OutputType]:
        """
        Single Process Conversion for Multiple Targets
        """
        index, target = target
        return index, self._aconvert_source_to_target(
            source=source,
            target=target,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )
    
    def _convert_source_to_targets(
        self,
        source: InputSourceType,
        targets: List[str], 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> List[OutputType]:
        """
        Convert the source to the targets

        source: /path/to/file.pdf
        targets: ['.docx', '.txt']
        """
        results = {}
        data_iterator = list(enumerate(targets))
        for item in self.pool.sync_iterate(
            self._convert_source_to_targets_one,
            data_iterator,
            source = source,
            source_filename = source_filename,
            target_output = target_output,
            return_ordered = False,
            **kwargs,
        ):
            index, output = item
            results[index] = output
        
        # Reorder the results to match the input order
        return [results[i] for i in range(len(results))]
    
    

    def convert_source_to_targets(
        self,
        source: InputSourceType,
        targets: List[str], 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> Dict[str, OutputType]:
        """
        Convert the source to the targets

        source: /path/to/file.pdf
        targets: ['.docx', '.txt']
        """
        if not self.enabled: raise NotImplementedError(f'{self.name} is not enabled')
        return self._convert_source_to_targets(
            source=source,
            targets=targets,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )
    
    def _convert_sources_to_target_one(
        self,
        source: Tuple[int, InputSourceType],
        target: str, 
        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,
        **kwargs,
    ) -> Tuple[int, OutputType]:
        """
        Single Process Conversion for Multiple Sources
        """
        index, source = source
        return index, self._convert_source_to_target(
            source=source,
            target=target,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )
    
    def _convert_sources_to_target(
        self,
        sources: Iterable[InputSourceType],
        target: str,
        
        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> List[OutputType]:
        """
        Convert the sources to the target

        sources: ['/path/to/file.pdf', '/path/to/file2.pdf']
        target: '.docx'
        """
        results = {}
        data_iterator = list(enumerate(sources))
        for item in self.pool.sync_iterate(
            self._convert_sources_to_target_one,
            data_iterator,
            target = target,
            source_filename = source_filename,
            target_output = target_output,
            return_ordered = False,
            **kwargs,
        ):
            index, output = item
            results[index] = output

        # Reorder the results to match the input order
        return [results[i] for i in range(len(results))]
    
    def convert_sources_to_target(
        self,
        sources: Iterable[InputSourceType],
        target: str, 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> Dict[str, OutputType]:
        """
        Convert the sources to the target

        sources: ['/path/to/file.pdf', '/path/to/file2.pdf']
        target: '.docx'
        """
        if not self.enabled: raise NotImplementedError(f'{self.name} is not enabled')
        return self._convert_sources_to_target(
            sources=sources,
            target=target,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )


    async def _aconvert_source_to_target(
        self,
        source: InputSourceT,
        target: str, 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,
        **kwargs,
    ) -> OutputType:
        """
        Convert the source to the target

        source: /path/to/file.pdf
        target: '.docx'
        """
        raise NotImplementedError
    

    async def _aconvert_source_to_targets_one(
        self,
        target: Tuple[int, str], 
        source: InputSourceT,
        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,
        **kwargs,
    ) -> Tuple[int, OutputType]:
        """
        Single Process Conversion for Multiple Targets
        """
        index, target = target
        return index, await self._aconvert_source_to_target(
            source=source,
            target=target,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )
    
    async def _aconvert_sources_to_target_one(
        self,
        source: Tuple[int, InputSourceType],
        target: str, 
        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,
        **kwargs,
    ) -> Tuple[int, OutputType]:
        """
        Single Process Conversion for Multiple Sources
        """
        index, source = source
        return index, await self._aconvert_source_to_target(
            source=source,
            target=target,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )
    
    async def aconvert_source_to_target(
        self,
        source: InputSourceType,
        target: str, 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> OutputType:
        """
        Convert the source to the target

        source: /path/to/file.pdf
        target: '.docx'
        """
        if not self.enabled: raise NotImplementedError(f'{self.name} is not enabled')
        return await self._aconvert_source_to_target(
            source=source,
            target=target,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )
    

    async def _aconvert_source_to_targets(
        self,
        source: InputSourceType,
        targets: List[str], 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> List[OutputType]:
        """
        Convert the source to the targets

        source: /path/to/file.pdf
        targets: ['.docx', '.txt']
        """
        results = {}
        data_iterator = list(enumerate(targets))
        async for item in self.pool.async_iterate(
            self._aconvert_source_to_targets_one,
            data_iterator,
            source = source,
            source_filename = source_filename,
            target_output = target_output,
            return_ordered = False,
            **kwargs,
        ):
            index, output = item
            results[index] = output

        # Reorder the results to match the input order
        return [results[i] for i in range(len(results))]
    

    async def aconvert_source_to_targets(
        self,
        source: InputSourceType,
        targets: List[str], 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> Dict[str, OutputType]:
        """
        Convert the source to the targets

        source: /path/to/file.pdf
        targets: ['.docx', '.txt']
        """
        if not self.enabled: raise NotImplementedError(f'{self.name} is not enabled')
        return await self._aconvert_source_to_targets(
            source=source,
            targets=targets,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )
    
    async def _aconvert_sources_to_target(
        self,
        sources: Iterable[InputSourceType],
        target: str, 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> List[OutputType]:
        """
        Convert the sources to the target

        sources: ['/path/to/file.pdf', '/path/to/file2.pdf']
        target: '.docx'
        """
        results = {}
        data_iterator = list(enumerate(sources))
        async for item in self.pool.async_iterate(
            self._aconvert_sources_to_target_one,
            data_iterator,
            target = target,
            source_filename = source_filename,
            target_output = target_output,
            return_ordered = False,
            **kwargs,
        ):
            index, output = item
            results[index] = output

        # Reorder the results to match the input order
        return [results[i] for i in range(len(results))]
    
    async def aconvert_sources_to_target(
        self,
        sources: Iterable[InputSourceType],
        target: str, 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        **kwargs,
    ) -> Dict[str, OutputType]:
        """
        Convert the sources to the target

        sources: ['/path/to/file.pdf', '/path/to/file2.pdf']
        target: '.docx'
        """
        if not self.enabled: raise NotImplementedError(f'{self.name} is not enabled')
        return await self._aconvert_sources_to_target(
            sources=sources,
            target=target,
            source_filename=source_filename,
            target_output=target_output,
            **kwargs,
        )
    
    """
    Misc. Utilities
    """

    @classmethod
    def convert_bytes_to_text(cls, data: bytes, encoding: Optional[str] = 'utf-8', errors: Optional[str] = 'ignore', **kwargs) -> str:
        """
        Converts file bytes to text
        """
        return data.decode(encoding, errors=errors)
    
    @classmethod
    def convert_text_to_bytes(cls, data: str, encoding: Optional[str] = 'utf-8', errors: Optional[str] = 'ignore', **kwargs) -> bytes:
        """
        Converts file text to bytes
        """
        return data.encode(encoding, errors=errors)
    
    @classmethod
    def convert_bytes_to_file(cls, data: bytes, path: Optional[InputPathType] = None, make_temp: Optional[bool] = False, **kwargs) -> 'FileLike':
        """
        Converts file bytes to a file
        """
        path = File(path) if path and not make_temp else File(tempfile.mktemp())
        path.write_bytes(data)
        return path
    
    @classmethod
    def convert_text_to_file(cls, data: str, path: Optional[InputPathType] = None, make_temp: Optional[bool] = False, **kwargs) -> 'FileLike':
        """
        Converts file text to a file
        """
        path = File(path) if path and not make_temp else File(tempfile.mktemp())
        path.write_text(data)
        return path
    
    @classmethod
    def convert_file_to_bytes(cls, path: InputPathType, **kwargs) -> bytes:
        """
        Converts a file to bytes
        """
        return Path(path).read_bytes()
    
    @classmethod
    def convert_file_input_to_bytes(
        cls, 
        data: InputContentType, 
        **kwargs
    ) -> bytes:
        """
        Converts input to bytes
        """
        if isinstance(data, bytes): return data
        if isinstance(data, str): return Path(data).read_bytes()
        if isinstance(data, Iterable): return b''.join(data)
        if isinstance(data, Path) or hasattr(data, 'read_bytes'): return data.read_bytes()
        raise TypeError(f'Invalid data type: {type(data)}')
    
    @classmethod
    def convert_file_input_to_file(
        cls, 
        data: InputContentType, 
        path: Optional[InputPathType] = None, 
        make_temp: Optional[bool] = False,
        **kwargs
    ) -> 'FileLike':
        """
        Converts input to a file
        """
        if isinstance(data, bytes): 
            return cls.convert_bytes_to_file(data, path=path, make_temp=make_temp)
        if isinstance(data, Path) or hasattr(data, 'as_posix'): 
            return cls.convert_bytes_to_file(data.read_bytes()) if make_temp else data
        if isinstance(data, str):
            # Try to validate it as a path
            p = File(data)
            if p.exists():
                return cls.convert_bytes_to_file(p.read_bytes()) if make_temp else p
            return cls.convert_text_to_file(data, path=path, make_temp=make_temp)
        if isinstance(data, Iterable): return cls.convert_bytes_to_file(b''.join(data), path=path, make_temp=make_temp)
        raise TypeError(f'Invalid data type: {type(data)}')

    
    @classmethod
    def detect_content_type(
        cls, 
        data: InputContentType,
        mime: Optional[bool] = False,
        **kwargs
    ) -> str:
        """
        Detect the content type of the data
        """
        from lazyops.imports._filemagic import resolve_magic
        resolve_magic(True)
        from magic import from_file, from_buffer
        if isinstance(data, str): return from_file(data, mime=mime)
        if isinstance(data, bytes): return from_buffer(data, mime = mime)
        return from_buffer(cls.convert_file_input_to_bytes(data), mime = mime)

    @classmethod
    def create_hash(cls, data: Union[bytes, Iterable[Union[bytes, Any]]]) -> str:
        """
        Create a hash for the data
        """
        if isinstance(data, bytes): return hash_func(data).hexdigest()
        return hash_func(b''.join(data)).hexdigest()
    
    @classmethod
    async def acreate_hash(cls, data: Union[bytes, Iterable[Union[bytes, Any]]]) -> str:
        """
        Create a hash for the data
        """
        return await ThreadPoolV2.run_async(cls.create_hash, data)
from __future__ import annotations

"""Primary entry-point for LazyOps file abstractions.

The implementations stay untouched; only documentation and typing surface areas
are clarified to make downstream usage explicit for auto-generated docs.
"""

import os
import typing as t
from lzl.types import PYDANTIC_VERSION
if PYDANTIC_VERSION == 2:
    from pydantic import TypeAdapter

if t.TYPE_CHECKING:
    from .spec.main import FileLike, FileLikeT, PathLike, CloudFileSystemPath
    from .configs.main import FileIOConfig
    from .types.misc import ObjectSize


if t.TYPE_CHECKING:
    
    class File(t.Generic[FileLikeT], CloudFileSystemPath):
        """Lightweight wrapper over provider-specific path implementations."""
        
        settings: 'FileIOConfig'

        @classmethod
        def get_dir(cls, path: PathLike) -> FileLike:
            """
            Returns the directory of the file
            """
            ...



else:
    from .path import Path
    from .types.base import FilePath
    from .spec.paths.aws import FileS3Path
    from .spec.paths.minio import FileMinioPath
    from .utils.registry import fileio_settings

    # TypeAdapter(FileMinioPath)
    # TypeAdapter(FileS3Path)

    PathLike = t.TypeVar(
        'PathLike', 
        bound = t.Union[
            str, 
            os.PathLike[str],
            Path,
            FilePath,
            FileS3Path,
            FileMinioPath,
        ]
    )
    
    FileLike = t.Union[
        Path,
        FilePath,
        FileS3Path,
        FileMinioPath,
    ]
    
    FileLikeT = t.TypeVar(
        'FileLikeT',
        Path,
        FilePath,
        FileS3Path,
        FileMinioPath,
    )

    class File(t.Generic[FileLikeT]):
        """Factory that instantiates concrete path objects for various backends."""

        settings: 'FileIOConfig' = fileio_settings

        @classmethod
        def _get_filelike(cls, *args: t.Any, **kwargs: t.Any) -> 'FileLike':
            """Resolve the correct :class:`FileLike` instance for given input.

            Args:
                *args: Positional arguments forwarded to
                    :func:`lzl.io.file.spec.main.get_filelike`.
                **kwargs: Keyword arguments forwarded to the same helper.
            """
            from .spec.main import get_filelike
            return get_filelike(*args, **kwargs)
        
        @classmethod
        def get_object_size(cls, obj: t.Any) -> 'ObjectSize':
            """Return a convenience wrapper reporting object size in bytes."""
            from .types.misc import ObjectSize
            return ObjectSize(obj)

        def __new__(
            cls, 
            *args, 
            **kwargs
        ) -> 'FileLike':
            """Instantiate a file path object for the configured backend."""
            return cls._get_filelike(*args, **kwargs)


        @classmethod
        def get_dir(cls, path: 'PathLike') -> 'FileLike':
            """Return the parent directory for the provided path-like value."""
            new = cls._get_filelike(path)
            return new if new.is_dir() else new.parent
        
            
        @classmethod
        def register_loader(cls, ext: str, loader: t.Union[t.Callable[['FileLike'], None], t.Awaitable['FileLike', None]], overwrite: t.Optional[bool] = None) -> None:
            """Register a loader callback for the given file extension.

            Args:
                ext: Extension (``.json``, ``.csv``…) to register the loader
                    against.  A leading dot is optional.
                loader: Callable that receives the resolved :class:`FileLike`
                    instance and should return either a processed value or
                    coroutine.
                overwrite: When ``True`` the loader replaces any existing
                    registration for ``ext``.
            """
            from lzl.io.file.registry import register_loader
            register_loader(ext, loader, overwrite)

        @classmethod
        def register_protocol(
            cls,
            protocol: str,
            kind: str,
            env_prefix: t.Optional[str] = None,
            **kwargs,
        ):
            """
            Registers a new protocol
            
            :param protocol: The protocol to register (e.g. mc2://)
            :param kind: The kind of provider (e.g. minio)
            :param env_prefix: The env prefix to use (e.g. MINIO2_)
            :param kwargs: Additional config kwargs
            """
            if protocol.endswith('://'): protocol = protocol[:-3]
            name = protocol.replace('+', '_')
            
            # 1. Register the provider config
            cls.settings.register_provider(name, kind, env_prefix = env_prefix, **kwargs)
            
            # 2. Create the Path Class
            # We need to import the base classes
            from .spec.main import register_path_protocol
            from .spec.path import CloudFileSystemPath, PureCloudFileSystemPosixPath, PureCloudFileSystemWindowsPath
            from .spec.paths.minio import FileMinioPath
            from .spec.paths.aws import FileS3Path
            from .spec.paths.r2 import FileR2Path
            from .spec.paths.s3c import FileS3CPath

            _BaseMap = {
                'minio': FileMinioPath,
                's3': FileS3Path,
                'aws': FileS3Path,
                'r2': FileR2Path,
                's3c': FileS3CPath,
                's3_compat': FileS3CPath,
            }
            if kind not in _BaseMap:
                raise ValueError(f"Unsupported Provider Kind for Path Creation: {kind}")
            
            base_cls = _BaseMap[kind]
            
            # Create the dynamic path class
            # This replicates logic in FileMinioPath etc
            
            _path_cls_name = f"File{name.title()}Path"
            _pure_posix_name = f"PureFile{name.title()}PosixPath"
            _pure_win_name = f"PureFile{name.title()}WindowsPath"
            
            def _resolve_cls(cls_attr, module_name):
                import sys
                if isinstance(cls_attr, str):
                    return getattr(sys.modules[module_name], cls_attr)
                return cls_attr
            
            _base_posix_pathz = _resolve_cls(base_cls._posix_pathz, base_cls.__module__)
            _base_win_pathz = _resolve_cls(base_cls._win_pathz, base_cls.__module__)
            
            # Dynamic Pure Classes
            class _DynamicPurePosixPath(PureCloudFileSystemPosixPath):
                _flavour = _base_posix_pathz._flavour
                _pathlike = _base_posix_pathz._pathlike
                _prefix = name
                _provider = kind.title()
                __slots__ = ()

            class _DynamicPureWindowsPath(PureCloudFileSystemWindowsPath):
                _flavour = _base_win_pathz._flavour
                _pathlike = _base_win_pathz._pathlike
                _prefix = name
                _provider = kind.title()
                __slots__ = ()

            # Dynamic Main Path Class
            # We must override _prefix, _provider, _posix_pathz, _win_pathz
            
            # We need to set the module name for the pure classes to be found?
            # Or we can just set them directly as classes if the base class supports it
            # Checking CloudFileSystemPath:
            # _win_pathz: t.ClassVar['CloudFileSystemWindowsPath'] = 'CloudFileSystemWindowsPath'
            # __new__ uses globals()[cls] if string. 
            # We should probably set them as classes if possible or register them in globals?
            # Registering in globals of the MODULE defining the class is tricky here.
            
            # Let's look at CloudFileSystemPath.__new__:
            # if cls is CloudFileSystemPath ... cls = globals()[cls]
            # If we pass a subclass, it might skip that?
            
            # FileMinioPath.__new__:
            # if cls is FileMinioPath or issubclass(cls, FileMinioPath): 
            #    cls = cls._posix_pathz if os.name != 'nt' else cls._win_pathz
            #    cls = globals()[cls]
            
            # This relies on the pure classes being in globals() of that module. 
            # Since we are defining dynamically, we need to handle this.
            
            # Strategy: Define the class such that __new__ logic works or is overridden.
            
            _new_conf = {
                '_prefix': name,
                '_provider': kind.title(),
                '_posix_prefix': kwargs.get('posix_prefix', 's3'),
                # We can't easily rely on string lookups in globals() for dynamic classes
                # unless we inject them into the module's globals where they are defined.
                # But here we are defining them inside a function.
            }
            
            # Override __new__ to pick the correct class directly
            # Override __new__ to pick the correct class directly
            # We need to define the concrete classes first or use a factory
            # But _new_new needs to reference them.
            
            _DynamicPath = type(_path_cls_name, (base_cls,), _new_conf)

            from .path import PosixPath, WindowsPath

            class _DynamicPosixPath(PosixPath, _DynamicPath, _DynamicPurePosixPath):
                __slots__ = ()
            
            class _DynamicWindowsPath(WindowsPath, _DynamicPath, _DynamicPureWindowsPath):
                __slots__ = ()

            def _new_new(cls, *parts, **kwargs):
                if cls.__name__ == _path_cls_name:
                    cls = _DynamicPosixPath if os.name != 'nt' else _DynamicWindowsPath
                self = cls._from_parts(parts, init=False)
                if hasattr(self, '_init'):
                    self._init()
                return self
            
            _DynamicPath.__new__ = _new_new
            
            # Also need to init
            def _init_dynamic(self, template = None):
                self._accessor = self._get_provider_accessor(self._prefix)
                self._closed = False
                self._fileio = None
                self._extra: t.Dict[str, t.Any] = {}

            _DynamicPath._init = _init_dynamic
            
            # 3. Register Protocol
            register_path_protocol(protocol, _DynamicPath)
            
            return _DynamicPath

        # Pydantic methods
        if PYDANTIC_VERSION == 2:
            from pydantic_core import core_schema, SchemaSerializer
            from pydantic.annotated_handlers import GetCoreSchemaHandler, GetJsonSchemaHandler
            from pydantic.json_schema import JsonSchemaValue

            @classmethod
            def __get_pydantic_json_schema__(
                cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
            ) -> JsonSchemaValue:
                
                field_schema = handler(core_schema)
                field_schema.update(format = 'path', type = 'string')
                return field_schema

            @classmethod
            def __get_pydantic_core_schema__(
                cls, 
                source: type[t.Any], 
                handler: GetCoreSchemaHandler
            ) -> core_schema.CoreSchema:
                """Return the Pydantic v2 CoreSchema for :class:`File` fields."""
                from pydantic_core import core_schema, SchemaSerializer
                schema = core_schema.with_info_plain_validator_function(
                    cls._validate,
                    serialization = core_schema.to_string_ser_schema(),
                )
                cls.__pydantic_serializer__ = SchemaSerializer(schema)
                return schema
            

            @classmethod
            def _validate(cls, __input_value: t.Any, _: core_schema.ValidationInfo) -> FileLike:
                """Pydantic validator that coerces inputs into :class:`File` objects."""
                return cls._get_filelike(__input_value) if __input_value is not None else None
            

            def __hash__(self: FileLike) -> int:
                return hash(self.as_posix())


        else:
            @classmethod
            def __get_validators__(cls):
                yield cls.validate

            @classmethod
            def validate(cls, v: t.Union[FileLike, t.Any]) -> FileLike:
                return cls._get_filelike(v) if v is not None else None
            
            @classmethod
            def __modify_schema__(cls, field_schema: t.Dict[str, t.Any]) -> None:
                field_schema.update(
                    type='string',
                    format='binary',
                )


if PYDANTIC_VERSION == 2:
    TypeAdapter(File)
    

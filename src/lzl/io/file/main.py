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
    

from __future__ import annotations

"""
Models for Argo Events
"""
import fnmatch
import typing as t

from pydantic import Field, AliasChoices
from lzl.types import BaseModel, eproperty
from pydantic import PrivateAttr, AliasChoices, ConfigDict, AliasGenerator, RootModel
from pydantic.alias_generators import to_camel

if t.TYPE_CHECKING:
    from lzl.io import File


def validation_gen(field: str) -> AliasChoices:
    """
    Generate validation aliases for a field.
    """
    return AliasChoices(to_camel(field), field)


default_alias_gen = AliasGenerator(
    validation_alias=validation_gen,
    serialization_alias=to_camel,
)


class BaseEventModel(BaseModel):
    """
    Base Argo Event Model
    """
    # The other stuff we don't really care about
    _extra: t.Dict[str, t.Any] = PrivateAttr(default_factory=dict)
    model_config = ConfigDict(
        extra = "allow",
        arbitrary_types_allowed = True,
        alias_generator = default_alias_gen,
        serialize_by_alias = True,
    )


class MinioBucket(BaseEventModel):
    """
    MinIO Bucket Data
    """
    name: t.Optional[str] = Field(default=None)
    owner_identity: t.Optional[dict] = Field(default=None)
    arn: t.Optional[str] = Field(default=None)


class MinioObject(BaseEventModel):
    """
    MinIO Object Data
    """
    key: t.Optional[str] = Field(default=None)
    size: t.Optional[int] = Field(default=None)
    e_tag: t.Optional[str] = Field(default=None)
    content_type: t.Optional[str] = Field(default=None)
    user_metadata: t.Optional[dict] = Field(default=None)
    sequencer: t.Optional[str] = Field(default=None)

class MinioS3Data(BaseEventModel):
    """
    MinIO S3 Event Data
    """
    s3_schema_version: t.Optional[str] = Field(default=None)
    configuration_id: t.Optional[str] = Field(default=None)

    bucket: MinioBucket = Field(default_factory=MinioBucket)
    object: MinioObject = Field(default_factory=MinioObject)

class MinioEvent(BaseEventModel):
    """
    MinIO S3 Event Notification
    """
    event_version: t.Optional[str] = Field(default=None)
    event_source: t.Optional[str] = Field(default=None)
    aws_region: t.Optional[str] = Field(default=None)
    event_time: t.Optional[str] = Field(default=None)
    event_name: t.Optional[str] = Field(default=None)
    user_identity: t.Optional[dict] = Field(default=None)
    request_parameters: t.Optional[dict] = Field(default=None)
    response_elements: t.Optional[dict] = Field(default=None)
    s3: t.Optional[MinioS3Data] = Field(default_factory=MinioS3Data)
    source: t.Optional[dict] = Field(default=None)

    @eproperty
    def is_create_event(self) -> bool:
        """
        Returns whether the event is a creation event.
        """
        return fnmatch.fnmatch(self.event_name, "s3:ObjectCreated:*")

    @eproperty
    def is_delete_event(self) -> bool:
        """
        Returns whether the event is a deletion event.
        """
        return fnmatch.fnmatch(self.event_name, "s3:ObjectRemoved:*")
    
    def get_bucket_object(self, scheme: t.Optional[str] = 'mc://', **kwargs) -> 'File':
        """
        Returns the bucket object as a File.
        """
        from lzl.io import File
        return File(path=f"{scheme}{self.s3.bucket.name}")

    def get_file_object(self, scheme: t.Optional[str] = 'mc://', **kwargs) -> 'File':
        """
        Returns a File object representing the MinIO object.
        """
        return self.get_bucket_object(scheme = scheme).joinpath(self.s3.object.key)


class MinioEvents(RootModel):
    root: t.List[MinioEvent]

    def __iter__(self) -> t.Iterator[MinioEvent]:
        return iter(self.root)

    def __getitem__(self, item: int) -> MinioEvent:
        return self.root[item]

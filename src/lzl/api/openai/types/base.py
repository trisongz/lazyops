from __future__ import annotations

"""
Base OpenAI Types
"""
import os
import json
import datetime
import pathlib
import tempfile
from enum import Enum
from lzo.types.base import BaseModel, Field, eproperty
from lzl.types.base import get_pydantic_field_names, ByteSize, validator, get_pydantic_fields
from lzl.api.openai.version import DEFAULT_AZURE_VERSION
from lazyops.utils import ObjectDecoder, ObjectEncoder
from ..utils.helpers import aparse_stream, parse_stream
from ..utils.logs import logger
from typing import Optional, Union, Dict, List, Any, Type, Tuple, Iterator, AsyncIterator, TYPE_CHECKING


try:
    from fileio import File, FileType
    _has_fileio = True
except ImportError:
    from pathlib import Path as File
    FileType = Union[File, str, os.PathLike]
    _has_fileio = False


if TYPE_CHECKING:
    from aiohttpx import Response

class ApiType(str, Enum):
    openai = "openai"
    azure = "azure"
    azure_ad = "azure_ad"

    def get_version(
        self, 
        version: Optional[str] = None
    ):
        """
        Returns the API Version
        """
        if self.value in {"azure", "azure_ad", "azuread"} and not version:
            return DEFAULT_AZURE_VERSION
        return version

    @classmethod
    def parse(cls, value: str) -> "ApiType":
        """
        Parses the API Type
        """
        return cls(value) if "azure" in value.lower() else cls.openai




class FilePurpose(str, Enum):
    """
    File Purpose
    """

    finetune = "fine-tune"
    fine_tune = "fine-tune"
    train = "fine-tune-train"
    search = "search"
    batch = "batch"

    @classmethod
    def parse_str(cls, value: Union[str, 'FilePurpose'], raise_error: bool = True):
        if isinstance(value, cls): return value
        if "train" in value:
            return cls.train
        elif "finetune" in value:
            return cls.finetune
        elif "fine-tune" in value:
            return cls.fine_tune
        elif "search" in value:
            return cls.search
        elif "batch" in value:
            return cls.batch
        if not raise_error: return None
        raise ValueError(f"Cannot convert {value} to FilePurpose")

class Usage(BaseModel):
    prompt_tokens: Optional[int] = 0
    completion_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0

    # @lazyproperty
    @property
    def consumption(self) -> int:
        """
        Gets the consumption
        """
        return self.total_tokens
    
    def update(self, usage: Union['Usage', Dict[str, int]]):
        """
        Updates the consumption
        """
        if isinstance(usage, Usage):
            if usage.prompt_tokens: self.prompt_tokens += usage.prompt_tokens
            if usage.completion_tokens: self.completion_tokens += usage.completion_tokens
            if usage.total_tokens: self.total_tokens += usage.total_tokens
            return
        if usage.get('prompt_tokens'): self.prompt_tokens += usage['prompt_tokens']
        if usage.get('completion_tokens'): self.completion_tokens += usage['completion_tokens']
        if usage.get('total_tokens'): self.total_tokens += usage['total_tokens']

    def __iadd__(self, other: Union['Usage', Dict[str, int]]):
        """
        Adds the usage
        """
        self.update(other)
        return self.consumption


class ModelCosts(BaseModel):
    """
    Represents a model's costs
    """
    unit: Optional[int] = 1000
    input: Optional[float] = 0.0
    output: Optional[float] = 0.0
    total: Optional[float] = 0.0


class ModelCostItem(BaseModel):
    """
    Represents a model's Cost Item
    """
    name: str
    aliases: Optional[List[str]] = None
    context_length: Optional[int] = 0
    costs: Optional[ModelCosts] = Field(default_factory=ModelCosts)
    batch_costs: Optional[ModelCosts] = None
    endpoints: Optional[List[str]] = None

    def get_costs(
        self, 
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        usage: Optional[Union['Usage', Dict[str, int]]] = None,
        is_batch: Optional[bool] = None,
        **kwargs
    ) -> float:
        """
        Gets the costs
        """
        if usage is not None:
            if isinstance(usage, dict): 
                usage = Usage(**usage)
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
        if kwargs.get('prompt_tokens'): input_tokens = kwargs['prompt_tokens']
        if kwargs.get('completion_tokens'): output_tokens = kwargs['completion_tokens']
        assert input_tokens is not None or output_tokens is not None or total_tokens is not None, "Must provide either input_tokens, output_tokens, or total_tokens"
        cost_ref = self.batch_costs if is_batch else self.costs
        if cost_ref is None: return 0.0
        cost = 0.0
        if cost_ref.input: cost += cost_ref.input * input_tokens / cost_ref.unit
        if cost_ref.output: cost += cost_ref.output * output_tokens / cost_ref.unit
        if cost_ref.total and total_tokens is not None: cost += cost_ref.total * total_tokens / cost_ref.unit
        return cost



class BaseResource(BaseModel):

    """
    Base Object class for resources to
    inherit from
    """


    if TYPE_CHECKING:
        id: Optional[str]
        file_id: Optional[str]
        fine_tune_id: Optional[str]
        model_id: Optional[str]
        completion_id: Optional[str]
        openai_id: Optional[str]
        model: Optional[str]


    @eproperty
    def resource_id(self):
        """
        Returns the resource id
        """
        if hasattr(self, 'id'):
            return self.id
        if hasattr(self, 'file_id'):
            return self.file_id
        if hasattr(self, 'fine_tune_id'):
            return self.fine_tune_id
        if hasattr(self, 'model_id'):
            return self.model_id
        if hasattr(self, 'completion_id'):
            return self.completion_id
        return self.openai_id if hasattr(self, 'openai_id') else None
    
    @staticmethod
    def create_resource(
        resource: Type['BaseResource'],
        **kwargs
    ) -> Tuple['BaseResource', Dict]:
        """
        Extracts the resource from the kwargs and returns the resource 
        and the remaining kwargs
        """
        resource_fields = get_pydantic_field_names(resource)
        resource_kwargs = {k: v for k, v in kwargs.items() if k in resource_fields}
        return_kwargs = {k: v for k, v in kwargs.items() if k not in resource_fields}
        resource_obj = resource.model_validate(resource_kwargs)
        return resource_obj, return_kwargs
    

    @staticmethod
    def create_batch_resource(
        resource: Type['BaseResource'],
        batch: List[Union[Dict[str, Any], Any]],
        **kwargs
    ) -> Tuple[List['BaseResource'], Dict]:
        """
        Extracts the resource from the kwargs and returns the resource 
        and the remaining kwargs
        """
        resource_fields = get_pydantic_field_names(resource)
        resource_kwargs = {k: v for k, v in kwargs.items() if k in resource_fields}
        return_kwargs = {k: v for k, v in kwargs.items() if k not in resource_fields}
        resource_objs = []
        for item in batch:
            if isinstance(item, dict):
                item.update(resource_kwargs)
                resource_objs.append(resource.model_validate(item))
            else:
                resource_objs.append(item)
        return resource_objs, return_kwargs

    @classmethod
    def create_many(cls, data: List[Dict]) -> List['BaseResource']:
        """
        Creates many resources
        """
        return [cls.model_validate(d) for d in data]
    
    @staticmethod
    def handle_json(
        content: Any,
        **kwargs
    ) -> Union[Dict, List]:
        """
        Handles the json response
        """
        return json.loads(content, cls = ObjectDecoder, **kwargs)


    @staticmethod
    def handle_stream(
        response: 'Response',
        streaming: Optional[bool] = False,
    ) -> Iterator[Dict]:
        """
        Handles the stream response
        """
        for line in parse_stream(response):
            if not line.strip(): continue
            try:
                yield json.loads(line)
            except Exception as e:
                logger.error(f'Error: {line}: {e}')
    
    @staticmethod
    async def ahandle_stream(
        response: 'Response',
        streaming: Optional[bool] = False,
    ) -> AsyncIterator[Dict]:
        """
        Handles the stream response
        """
        async for line in aparse_stream(response):
            if not line.strip(): continue
            try:
                yield json.loads(line)
            except Exception as e:
                logger.error(f'Error: {line}: {e}')


    def __getitem__(self, key: str) -> Any:
        """
        Mimic dict
        """
        return getattr(self, key)


class Permission(BaseResource):
    id: str
    object: str
    created: datetime.datetime
    allow_create_engine: bool
    allow_sampling: bool
    allow_logprobs: bool
    allow_search_indices: bool
    allow_view: bool
    allow_fine_tuning: bool
    organization: str
    group: Optional[str]
    is_blocking: bool

    @property
    def since_seconds(self):
        return (datetime.datetime.now(datetime.timezone.utc) - self.created).total_seconds()


class FileObject(BaseResource):
    id: str
    object: Optional[str] = 'file'
    bytes: Optional[ByteSize]
    created_at: Optional[datetime.datetime]
    filename: Optional[str]
    purpose: Optional[FilePurpose] = FilePurpose.fine_tune

    @validator("created_at")
    def validate_created_at(cls, value):
        return datetime.datetime.fromtimestamp(value, datetime.timezone.utc) if value else value
    
    @classmethod
    def create_many(cls, data: List[Dict]) -> List['FileObject']:
        """
        Creates many resources
        """
        return [cls.model_validate(d) for d in data]

class EventObject(BaseResource):
    object: Optional[str]
    created_at: Optional[datetime.datetime]
    level: Optional[str]
    message: Optional[str]

    @property
    def since_seconds(self) -> int:
        if self.created_at is None: return -1
        return (datetime.datetime.now(datetime.timezone.utc) - self.created_at).total_seconds()


class FileResource(BaseResource):
    file: Optional[Union[str, FileType, Any]] # type: ignore
    file_id: Optional[str]
    filename: Optional[str] = None
    purpose: FilePurpose = FilePurpose.fine_tune
    model: Optional[str] = None

    @validator("purpose")
    def validate_purpose(cls, value):
        return FilePurpose.parse_str(value) if isinstance(value, str) else value
    
    def get_params(self, **kwargs) -> List:
        """
        Transforms the data to the req params
        """
        files = [("purpose", (None, self.purpose.value))]
        if self.purpose == FilePurpose.search and self.model:
            files.append(("model", (None, self.model)))
        if self.file:
            file = File(self.file)
            files.append(
                ("file", (self.filename or file.name, file.read_bytes(), "application/octet-stream"))
            )
        return files
    
    async def async_get_params(self, **kwargs) -> List:
        """
        Transforms the data to the req params
        """
        files = [("purpose", (None, self.purpose.value))]
        if self.purpose == FilePurpose.search and self.model:
            files.append(("model", (None, self.model)))
        if self.file:
            file = File(self.file)
            files.append(
                ("file", (self.filename or file.name, (await file.async_read_bytes() if _has_fileio else file.read_bytes()), "application/octet-stream"))
            )
        return files

    @classmethod
    def create_from_batch(
        cls,
        batch: List[Union[Dict[str, Any], str]],
        output_path: Optional[str] = None,
        file_id: Optional[str] = None,
        filename: Optional[str] = None,
        purpose: Optional[FilePurpose] = None,
        **kwargs,
    ) -> Tuple['FileObject', Dict[str, Any]]:
        """
        Creates a file object from a batch in jsonl format
        """
        for n, b in enumerate(batch):
            if isinstance(b, dict):
                batch[n] = json.dumps(b, cls = ObjectEncoder)
        if output_path:
            output = pathlib.Path(output_path)
        else:
            tmp = tempfile.NamedTemporaryFile(delete = False)
            tmp.close()
            output = pathlib.Path(tmp.name)

        with output.open('w') as f:
            for b in batch:
                f.write(f'{b}\n')
        resource_fields = get_pydantic_field_names(cls)
        resource_kwargs = {k: v for k, v in kwargs.items() if k in resource_fields}
        return_kwargs = {k: v for k, v in kwargs.items() if k not in resource_fields}
        return cls(
            file = output,
            purpose = purpose,
            filename = filename,
            file_id = file_id,
            **resource_kwargs
        ), return_kwargs
        

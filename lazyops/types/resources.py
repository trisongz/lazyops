
from lazyops.types.models import BaseModel
from lazyops.types.static import VALID_REQUEST_KWARGS
from lazyops.types.classprops import lazyproperty
from lazyops.imports._aiohttpx import aiohttpx
from typing import Optional, Dict, Any, Tuple, Type, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic.typing import AbstractSetIntStr, MappingIntStrAny

__all__ = [
    'BaseResource',
    'ResourceType',
    'ResponseResource',
    'ResponseResourceType',
]


class BaseResource(BaseModel):

    @property
    def exclude_none(self):
        return True

    @property
    def exclude_fields(self):
        return {'exclude_none', 'exclude_fields'}

    @classmethod
    def parse_resource(
        cls,
        **kwargs
    ) -> Tuple[Type['BaseResource'], Dict]:
        """
        Extracts the resource from the kwargs and returns the resource 
        and the remaining kwargs
        """
        resource_fields = [field.name for field in cls.__fields__.values()]
        resource_kwargs = {k: v for k, v in kwargs.items() if k in resource_fields}
        return_kwargs = {k: v for k, v in kwargs.items() if k not in resource_fields and k in VALID_REQUEST_KWARGS}
        resource_obj = cls.parse_obj(resource_kwargs)
        return resource_obj, return_kwargs


    @staticmethod
    def create_resource(
        resource: Type['BaseResource'],
        **kwargs
    ) -> Tuple[Type['BaseResource'], Dict]:
        """
        Extracts the resource from the kwargs and returns the resource 
        and the remaining kwargs
        """
        resource_fields = [field.name for field in resource.__fields__.values()]
        resource_kwargs = {k: v for k, v in kwargs.items() if k in resource_fields}
        return_kwargs = {k: v for k, v in kwargs.items() if k not in resource_fields and k in VALID_REQUEST_KWARGS}
        resource_obj = resource.parse_obj(resource_kwargs)
        return resource_obj, return_kwargs
    

    def dict(
        self,
        *,
        include: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
        exclude: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
        by_alias: bool = False,
        skip_defaults: Optional[bool] = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: Optional[bool] = None,
    ):
        """
        Returns the dict representation of the response
        """
        if exclude is None: exclude = set()
        if self.exclude_fields:
            exclude = set(exclude) | self.exclude_fields

        return super().dict(
            include = include, 
            exclude = exclude, 
            by_alias = by_alias,
            skip_defaults = skip_defaults,
            exclude_unset = exclude_unset,
            exclude_defaults = exclude_defaults,
            exclude_none = exclude_none if exclude_none is not None else self.exclude_none
        )

    def parse_data(
        self,
        **kwargs
    ):
        """
        Parses the prediction response
        """
        pass


ResourceType = Type[BaseResource]


class ResponseResource(BaseResource):
    _input_obj: Optional[ResourceType] = None
    _response: Optional['aiohttpx.Response'] = None
    _streamed_data: Optional[str] = None

    @property
    def exclude_fields(self):
        return {'_input_obj', '_response', '_streamed_data', 'exclude_none', 'exclude_fields'}

    @lazyproperty
    def headers(self):
        return self._response.headers
    
    @lazyproperty
    def status_code(self):
        return self._response.status_code

    @lazyproperty
    def has_stream(self):
        return "text/event-stream" in self.headers.get("content-type", "")
    
    @lazyproperty
    def json_data(self) -> Dict[str, Any]:
        return self._response.json()

    @classmethod
    def parse_from(
        cls,
        input_obj: ResourceType,
        response: 'aiohttpx.Response',
        **kwargs
    ) -> 'ResponseResourceType':
        """
        Parses the response and returns the response object
        """
        resp = cls(
            _input_obj = input_obj,
            _response = response,
            **response.json()
        )
        resp.parse_data(**kwargs)
        return resp

ResponseResourceType = Type[ResponseResource]
import os
import pathlib

from typing import Any, Type, Tuple, Dict, List, Union, Optional
from pydantic import Field, validator
from pydantic import BaseModel as _BaseModel
from pydantic import BaseSettings as _BaseSettings
from lazyops.types.formatting import to_snake_case, to_graphql_format
from lazyops.types.classprops import classproperty
from lazyops.utils.serialization import Json

class BaseSettings(_BaseSettings):

    class Config:
        env_prefix: str = ""
        case_sensitive: bool = False

    def update_config(self, **kwargs):
        """
        Update the config for the other settings
        """
        for k, v in kwargs.items():
            if not hasattr(self, k): continue
            if isinstance(getattr(self, k), pathlib.Path):
                setattr(self, k, pathlib.Path(v))
            elif isinstance(getattr(self, k), BaseSettings):
                val = getattr(self, k)
                if hasattr(val, 'update_config'):
                    val.update_config(**v)
                else:
                    val = val.__class__(**v)
                setattr(self, k, val)
            else: 
                setattr(self, k, v)

    def set_env(self):
        """
        Update the Env variables for the current session
        """
        data = self.dict(exclude_none=True)
        for k, v in data.items():
            if isinstance(v, BaseSettings):
                v.set_env()
            else:
                os.environ[self.Config.env_prefix + k.upper()] = str(v)


class BaseModel(_BaseModel):
    class Config:
        extra = 'allow'
        arbitrary_types_allowed = True
        alias_generator = to_snake_case
        
    def get(self, name, default: Any = None):
        return getattr(self, name, default)
    
    def update(self, **kwargs):
        for k, v in kwargs.items():
            if not hasattr(self, k): continue
            setattr(self, k, v)


    @classmethod
    def create_one(
        cls,
        **kwargs
    ) -> Tuple[Type['BaseModel'], Dict]:
        """
        Extracts the resource from the kwargs and returns the resource 
        and the remaining kwargs
        """
        resource_fields = [field.name for field in cls.__fields__.values()]
        resource_kwargs = {k: v for k, v in kwargs.items() if k in resource_fields}
        return_kwargs = {k: v for k, v in kwargs.items() if k not in resource_fields}
        resource_obj = cls.parse_obj(resource_kwargs)
        return resource_obj, return_kwargs
    
    @classmethod
    def create_many(cls, data: List[Dict]) -> List['BaseModel']:
        return [cls.parse_obj(d) for d in data]
    
    @classproperty
    def model_fields(cls) -> List[str]:
        return [field.name for field in cls.__fields__.values()]
    
    def get_model_fields(self) -> List[str]:
        return [field.name for field in self.__fields__.values()]

    def replace(self, obj: Type['BaseModel']):
        """Replace current attributes with `obj` attributes."""
        for field in obj.model_fields:
            if hasattr(self, field):
                setattr(self, field, getattr(obj, field))

    def graphql(
        self,
        *,
        include: Optional[Any] = None,
        exclude: Optional[Any] = None,
        by_alias: bool = False,
        skip_defaults: Optional[bool] = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> Union[Dict, Any]:
        """
        Return the data in `graphql` format
        """
        data = self.dict(
            include = include, exclude = exclude, \
            by_alias = by_alias, skip_defaults = skip_defaults, \
            exclude_unset = exclude_unset, exclude_defaults = exclude_defaults, \
            exclude_none = exclude_none
        )
        return to_graphql_format(data)



class Schema(BaseModel):

    class Config:
        extra = 'allow'
        arbitrary_types_allowed = True
        json_dumps = Json.dumps

    def get(self, name, default: Any = None):
        return getattr(self, name, default)


class Constant(tuple):
    "Pretty display of immutable constant."

    def __new__(cls, name):
        return tuple.__new__(cls, (name,))

    def __repr__(self):
        return f'{self[0]}'

__all__ = [
    'Field',
    'BaseModel',
    'BaseSettings',
    'Schema',
    'validator',
]
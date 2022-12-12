import os
import pathlib

from typing import Any
from pydantic import Field, validator
from pydantic import BaseModel as _BaseModel
from pydantic import BaseSettings as _BaseSettings
from lazyops.types.formatting import to_snake_case

class BaseSettings(_BaseSettings):

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


class Schema(BaseModel):

    class Config:
        extra = 'allow'
        arbitrary_types_allowed = True
        

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
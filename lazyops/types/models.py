import os
import pathlib

from typing import Any, Type, Tuple, Dict, List, Union, Optional
from pydantic import Field, validator
from pydantic.networks import AnyUrl
from pydantic import BaseModel as _BaseModel
from pydantic import BaseSettings as _BaseSettings
from lazyops.types.formatting import to_snake_case, to_graphql_format
from lazyops.types.classprops import classproperty, lazyproperty
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


class UrlModel(BaseModel):
    """
    Parse a URL into its components
    """
    url: AnyUrl
    scheme: Optional[str] = 'http'
    adapter: Optional[str] = None

    @lazyproperty
    def db(self):
        return self.url.path[1:]
    
    @lazyproperty
    def path(self):
        return self.url.path

    @lazyproperty
    def host(self):
        return self.url.host

    @lazyproperty
    def port(self):
        return self.url.port

    @lazyproperty
    def user(self):
        return self.url.user or None
    
    @lazyproperty
    def password(self):
        return self.url.password or None
    
    @lazyproperty
    def api_key(self):
        return self.url.user or None
    
    @lazyproperty
    def token(self):
        return self.url.password or None

    @lazyproperty
    def server_uri(self):
        """
        Returns the bare connection uri without the database/path/auth
        """
        return self.get_uri(include_auth = False, include_db = False, include_path = False)
    
    @lazyproperty
    def base_uri(self):
        """
        Returns the connection uri without the database/path
        """
        return self.get_uri(include_path = False, include_db = False)
    
    @lazyproperty
    def safe_uri(self):
        """
        Returns the connection uri without the password
        """
        return self.get_uri(include_auth = True, include_db = True, include_path = True, include_adapter = True, _safe = True)

    @lazyproperty
    def connection_uri(self):
        """
        Returns the connection uri with the database/path
        """
        return self.get_uri(include_path = True, include_db = True, include_auth = True, include_adapter = True, _safe = False)

    def get_uri(
        self, 
        scheme: Optional[str] = None, 
        db: Optional[str] = None,
        path: Optional[str] = None,
        include_path: Optional[bool] = True,
        include_db: Optional[bool] = True,
        include_auth: Optional[bool] = True,
        include_adapter: Optional[bool] = True,
        _safe: Optional[bool] = False,
        **kwargs,
    ):
        scheme = scheme or self.scheme
        if include_adapter and self.adapter and self.adapter not in scheme:
            scheme = f'{self.adapter}+{scheme}'
        uri = f'{scheme}://'
        if include_auth and self.user:
            uri += '*****' if _safe else f'{self.user}'
            if self.password:
                uri += ':*****' if _safe else f':{self.password}'
            uri += '@'
        uri += f'{self.host}'
        if self.port:
            uri += f':{self.port}'
        if 'http' in scheme and include_path:
            path = path or self.path
            if path: uri += f'/{path}'
        elif include_db:
            db = db or self.db
            if db: uri += f'/{db}'
        return uri

    @classmethod
    def parse(
        cls, 
        url: Optional[str] = None, 
        scheme: Optional[str] = 'http',
        adapter: Optional[str] = None,
        **config
    ):
        path = config.get('path')
        db = config.get('db')
        if url: 
            if 'http' in scheme and path: url += f'/{path}'
            elif db: url += f'/{db}'    
            return cls(url = url, scheme=scheme, adapter=adapter)
        url = f'{scheme}://'
        host = config.get('host')
        port = config.get('port')
        user = config.get('user')
        password = config.get('password')
        api_key = config.get('api_key')
        token = config.get('token')
        
        if user:
            url += f'{user}'
            if password:
                url += f':{password}'
            url += '@'
        elif api_key:
            url += f'{api_key}@'
        elif token:
            url += f'{token}@'
        url += f'{host}'
        if port: url += f':{port}'
        if 'http' in scheme and path: url += f'/{path}'
        elif db: url += f'/{db}'
        return cls(url = url, scheme = scheme, adapter = adapter)

class BaseDBUrl(UrlModel):

    @classmethod
    def parse(
        cls, 
        url: Optional[str] = None, 
        scheme: Optional[str] = 'http',
        adapter: Optional[str] = None,
        **config
    ):
        config_key = cls.__name__.split('DB', 1)[0].lower()
        db = config.get(f'{config_key}_db', config.get('db'))
        path = config.get(f'{config_key}_path', config.get('path'))
        
        if url: 
            if 'http' in scheme and path: url += f'/{path}'
            elif db: url += f'/{db}'    
            return cls(url = url, scheme=scheme, adapter=adapter)

        
        url = f'{scheme}://'
        host = config.get(f'{config_key}_host', config.get('host'))
        port = config.get(f'{config_key}_port', config.get('port'))
        user = config.get(f'{config_key}_user', config.get('user'))
        password = config.get(f'{config_key}_password', config.get('password'))
        api_key = config.get(f'{config_key}_api_key', config.get('api_key'))
        token = config.get(f'{config_key}_token', config.get('token'))
        
        if user:
            url += f'{user}'
            if password: url += f':{password}'
            url += '@'
        elif api_key:
            url += f'{api_key}@'
        elif token:
            url += f'{token}@'
        url += f'{host}'
        if port:
            url += f':{port}'
        if 'http' in scheme and path: url += f'/{path}'
        elif db: url += f'/{db}'
        return cls(url = url, scheme = scheme, adapter = adapter)


class PostgresDB(BaseDBUrl):
    url: AnyUrl
    scheme: Optional[str] = 'postgresql'
    adapter: Optional[str] = 'postgresql'
    
    @classmethod
    def parse(
        cls, 
        url: Optional[str] = None, 
        scheme: Optional[str] = 'postgresql',
        adapter: Optional[str] = 'postgresql',
        **config
    ):
        return super().parse(url = url, scheme = scheme, adapter = adapter, **config)

class RedisDB(BaseDBUrl):
    url: AnyUrl
    scheme: Optional[str] = 'redis'
    adapter: Optional[str] = None
    
    @classmethod
    def parse(
        cls, 
        url: Optional[str] = None, 
        scheme: Optional[str] = 'redis',
        adapter: Optional[str] = None,
        **config
    ):
        return super().parse(url = url, scheme = scheme, adapter = adapter, **config)

class NatsDB(BaseDBUrl):
    url: AnyUrl
    scheme: Optional[str] = 'nats'
    adapter: Optional[str] = None
    
    @classmethod
    def parse(
        cls, 
        url: Optional[str] = None, 
        scheme: Optional[str] = 'nats',
        adapter: Optional[str] = None,
        **config
    ):
        return super().parse(url = url, scheme = scheme, adapter = adapter, **config)



__all__ = [
    'Field',
    'BaseModel',
    'BaseSettings',
    'Schema',
    'validator',
    'UrlModel',
    'BaseDBUrl',
    'PostgresDB',
    'RedisDB',
    'NatsDB',
]
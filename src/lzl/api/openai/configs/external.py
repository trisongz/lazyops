from __future__ import annotations

import json
import pathlib
import random
from lzl.api import aiohttpx
from lzl.types import BaseModel, Field, eproperty, model_validator, field_validator, validator, root_validator, PYDANTIC_VERSION
from lzl.proxied import proxied, ProxyObject
# from lzo.types import AppEnv


from lzl.api.openai.assets import load_preset_config, load_provider_prices
from lzl.api.openai.types.base import ModelCostItem
from lzl.api.openai.types.handlers import ModelContextHandler
from typing import Optional, Dict, Union, Any, List, Type, TYPE_CHECKING


# from lazyops.types import BaseSettings, validator, BaseModel, lazyproperty, Field, PYD_VERSION
# from lazyops.libs.proxyobj import ProxyObject
# from lazyops.libs.abcs.configs.types import AppEnv
# from async_openai.version import VERSION
# from async_openai.types.options import ApiType
# from async_openai.types.context import ModelCostItem, ModelContextHandler

# if PYD_VERSION == 2:
#     from pydantic import model_validator
# else:
#     from lazyops.types.models import root_validator

if TYPE_CHECKING:
    from lzl.api.openai.types.routes import BaseRoute, BaseResource


# preset_path = pathlib.Path(__file__).parent.joinpath('presets')


class ExternalProviderConfig(BaseModel):
    """
    External Provider - Configuration
    """
    api_base: str = Field(..., description="The base URL for the API")
    api_path: Optional[str] = Field(None, description="The path for the API")
    api_key_header: Optional[str] = Field(None, description="The header for the API Key")
    api_key_scheme: Optional[str] = Field(None, description="The scheme for the API Key")
    api_key: Optional[str] = Field(None, description="The API Key")
    api_keys: Optional[List[str]] = Field(None, description="The API Keys")

    max_retries: Optional[int] = Field(None, description="The maximum number of retries for the API")
    weight: Optional[float] = Field(None, description="The weight of the provider")

    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom Headers")
    proxy_url: Optional[str] = Field(None, description="The Proxy URL")
    proxy_headers: Optional[Dict[str, str]] = Field(None, description="Proxy Headers")
    hf_compatible: Optional[bool] = Field(None, description="Whether the provider is HuggingFace Compatible for Tokenization")

    # @validator("custom_headers", "proxy_headers", pre=True)
    @field_validator("custom_headers", "proxy_headers", mode = 'before')
    def validate_headers(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """
        Validates the Headers
        """
        if value is None: return {}
        value = {k: v for k,v in value.items() if v is not None}
        for k,v in value.items():
            value[k.strip()] = json.dumps(v) if isinstance(v, (list, dict)) else str(v).strip()
        return value
    
    # @validator("max_retries", pre=True)
    @field_validator("max_retries", mode = 'before')
    def validate_max_retries(cls, value: Optional[Union[str, int]]) -> Optional[int]:
        """
        Validates the Max Retries
        """
        if value is None: return None
        try:
            return int(value)
        except ValueError:
            return None
        
    # @validator("weight", pre=True)
    @field_validator("weight", mode = 'before')
    def validate_weight(cls, value: Optional[Union[str, float]]) -> Optional[float]:
        """
        Validates the Weight
        """
        if value is None: return None
        try: return float(value)
        except ValueError:
            return None

    @property
    def has_api_key(self) -> bool:
        """
        Returns whether the API Key is present
        """
        return self.api_key is not None
    
    @property
    def api_key_value(self) -> Optional[str]:
        """
        Returns the API Key Value
        """
        if not self.has_api_key: return None
        return f"{self.api_key_scheme} {self.api_key}" if self.api_key_scheme else self.api_key
    
    @property
    def has_api_keys(self) -> bool:
        """
        Returns whether the API Keys are present
        """
        return self.api_keys is not None
    
    @property
    def api_keys_value(self) -> Optional[List[str]]:
        """
        Returns the API Keys Value
        """
        if not self.has_api_keys: return None
        return [f"{self.api_key_scheme} {k}" if self.api_key_scheme else k for k in self.api_keys]

    @property
    def has_proxy(self) -> bool:
        """
        Returns whether the Proxy is present
        """
        return self.proxy_url is not None
    
    @property
    def api_url(self) -> str:
        """
        Returns the API URL
        """
        if not self.api_path: return self.api_base
        return aiohttpx.urljoin(self.api_base, self.api_path)


class ProviderModel(ModelCostItem):
    """
    A Provider Model
    """
    name: str = Field(..., description="The Model Name")
    tokenizer: Optional[str] = Field(None, description="The Tokenizer Name") 


class ProviderRoute(BaseModel):
    """
    A Provider Route
    """
    name: Optional[str] = Field(None, description="The Route Name")
    api_resource: Optional[str] = Field(None, description="The Route Path")
    root_name: Optional[str] = Field(None, description="The Root Name")
    # params: Optional[Dict[str, Type]] = Field(None, description="The Route Parameters and expected Types")

    if TYPE_CHECKING:
        route_class: Optional[Type['BaseRoute']] = Field(None, description="The Route Class")
        object_class: Optional[Type['BaseResource']] = Field(None, description="The Resource Class")
        response_class: Optional[Type['BaseResource']] = Field(None, description="The Response Class")
    else:
        route_class: Optional[Any] = Field(None, description="The Route Class")
        object_class: Optional[Any] = Field(None, description="The Resource Class")
        response_class: Optional[Any] = Field(None, description="The Response Class")
    

    # @validator("route_class", "object_class", "response_class", pre=True)
    @field_validator("route_class", "object_class", "response_class", mode = 'before')
    def validate_route_classes(cls, value: Union[str, Type]) -> Type:
        """
        Validates the Route Classes
        """
        if value is None: return None
        if isinstance(value, str):
            from lzl.load import lazy_import
            return lazy_import(value)
        return value


class ExternalProviderRoutes(BaseModel):
    """
    External Provider - Routes
    """
    completions: Optional[ProviderRoute] = Field(None, description="The Completion Route")
    chat: Optional[ProviderRoute] = Field(None, description="The Chat Route")
    embeddings: Optional[ProviderRoute] = Field(None, description="The Embedding Route")
    # if TYPE_CHECKING:

    if PYDANTIC_VERSION == 2:
        @model_validator(mode = 'after')
        def validate_routes(self):
            """
            Validates the Routes
            """
            from lzl.api.openai.schemas import (
                ChatRoute, ChatResponse, ChatObject,
                CompletionRoute, CompletionResponse, CompletionObject,
                EmbeddingRoute, EmbeddingResponse, EmbeddingObject,
                # TODO - Add the rest of the routes
            )
            # from async_openai.schemas import (
            #     ChatRoute, ChatResponse, ChatObject,
            #     CompletionRoute, CompletionResponse, CompletionObject,
            #     EmbeddingRoute, EmbeddingResponse, EmbeddingObject,
            #     # TODO - Add the rest of the routes
            # )
            if self.chat is None:
                self.chat = ProviderRoute(
                    name = "chat",
                    route_class = ChatRoute,
                    object_class = ChatObject,
                    response_class = ChatResponse,
                )
            if not self.chat.name:
                self.chat.name = "chat"
            if self.chat.route_class is None:
                self.chat.route_class = ChatRoute
            if self.chat.object_class is None:
                self.chat.object_class = ChatObject
            if self.chat.response_class is None:
                self.chat.response_class = ChatResponse

            if self.completions is None:
                self.completions = ProviderRoute(
                    name = "completions",
                    route_class = CompletionRoute,
                    object_class = CompletionObject,
                    response_class = CompletionResponse,
                )
            if not self.completions.name:
                self.completions.name = "completions"
            if self.completions.route_class is None:
                self.completions.route_class = CompletionRoute
            if self.completions.object_class is None:
                self.completions.object_class = CompletionObject
            if self.completions.response_class is None:
                self.completions.response_class = CompletionResponse

            if self.embeddings is None:
                self.embeddings = ProviderRoute(
                    name = "embeddings",
                    route_class = EmbeddingRoute,
                    object_class = EmbeddingObject,
                    response_class = EmbeddingResponse,
                )
            
            if not self.embeddings.name:
                self.embeddings.name = "embeddings"
            if self.embeddings.route_class is None:
                self.embeddings.route_class = EmbeddingRoute
            if self.embeddings.object_class is None:
                self.embeddings.object_class = EmbeddingObject
            if self.embeddings.response_class is None:
                self.embeddings.response_class = EmbeddingResponse
            return self

    else:
        @root_validator()
        def validate_routes(cls, values: Dict[str, Any]) -> Dict[str, Any]:
            """
            Validates the Routes
            """
            from lzl.api.openai.schemas import (
                ChatRoute, ChatResponse, ChatObject,
                CompletionRoute, CompletionResponse, CompletionObject,
                EmbeddingRoute, EmbeddingResponse, EmbeddingObject,
                # TODO - Add the rest of the routes
            )
            # from async_openai.schemas import (
            #     ChatRoute, ChatResponse, ChatObject,
            #     CompletionRoute, CompletionResponse, CompletionObject,
            #     EmbeddingRoute, EmbeddingResponse, EmbeddingObject,
            #     # TODO - Add the rest of the routes
            # )
            if values.get('chat') is None:
                values['chat'] = ProviderRoute(
                    name = "chat",
                    route_class = ChatRoute,
                    object_class = ChatObject,
                    response_class = ChatResponse,
                )
            else:
                values['chat'] = ProviderRoute.parse_obj(values['chat'])
            if not values['chat'].name:
                values['chat'].name = "chat"
            if values['chat'].route_class is None:
                values['chat'].route_class = ChatRoute
            if values['chat'].object_class is None:
                values['chat'].object_class = ChatObject
            if values['chat'].response_class is None:
                values['chat'].response_class = ChatResponse
            
            if values.get('completions') is None:
                values['completions'] = ProviderRoute(
                    name = "completions",
                    route_class = CompletionRoute,
                    object_class = CompletionObject,
                    response_class = CompletionResponse,
                )
            else:
                values['completions'] = ProviderRoute.parse_obj(values['completions'])
            if not values['completions'].name:
                values['completions'].name = "completions"
            if values['completions'].route_class is None:
                values['completions'].route_class = CompletionRoute
            if values['completions'].object_class is None:
                values['completions'].object_class = CompletionObject
            if values['completions'].response_class is None:
                values['completions'].response_class = CompletionResponse
            
            if values.get('embeddings') is None:
                values['embeddings'] = ProviderRoute(
                    name = "embeddings",
                    route_class = EmbeddingRoute,
                    object_class = EmbeddingObject,
                    response_class = EmbeddingResponse,
                )
            else:
                values['embeddings'] = ProviderRoute.parse_obj(values['embeddings'])
            if not values['embeddings'].name:
                values['embeddings'].name = "embeddings"
            if values['embeddings'].route_class is None:
                values['embeddings'].route_class = EmbeddingRoute
            if values['embeddings'].object_class is None:
                values['embeddings'].object_class = EmbeddingObject
            if values['embeddings'].response_class is None:
                values['embeddings'].response_class = EmbeddingResponse
            return values
        
    @property
    def api_route_classes(self) -> Dict[str, Type['BaseRoute']]:
        """
        Returns the Route Classes
        """
        return {
            "chat": self.chat.route_class,
            "completions": self.completions.route_class,
            "embeddings": self.embeddings.route_class,
        }
    
    # def configure_retry(self, max_retries: Optional[int] = None):
    #     """
    #     Configures the retry logic
    #     """
    #     if max_retries is None: return
    #     if hasattr(self.chat.route_class, 'max_retries'): self.chat.route_class.max_retries = max_retries
    #     if hasattr(self.completions.route_class, 'max_retries'): self.completions.route_class.max_retries = max_retries
    #     if hasattr(self.embeddings.route_class, 'max_retries'): self.embeddings.route_class.max_retries = max_retries

            

class ExternalProviderSettings(BaseModel):
    """
    External Provider Configuration
    """
    name: str = Field(..., description="The Provider Name")
    config: ExternalProviderConfig = Field(default_factory = ExternalProviderConfig, description="The Provider Configuration")
    models: List[ProviderModel] = Field(default_factory=list, description="The Provider Models")
    routes: Optional[ExternalProviderRoutes] = Field(default_factory=ExternalProviderRoutes, description="The Provider Routes")

    @classmethod
    def from_preset(
        cls, 
        name: Optional[str] = None,
        path: Optional[Union[str, pathlib.Path]] = None,
        **overrides
    ) -> 'ExternalProviderSettings':
        """
        Loads the Provider Settings from a Preset
        """
        # assert name or path, "You must provide either a name or a path to the preset"
        # if path:
        #     preset_file = pathlib.Path(path)
        #     assert preset_file.exists(), f"Could not find the preset path: {preset_file}"
        # else:
            
        #     preset_file = preset_path.joinpath(f"{name}.yaml")
        #     if not preset_file.exists():
        #         raise FileNotFoundError(f"Could not find the preset file: {preset_file} for {name}")
        
        # assert preset_file.suffix in {
        #     ".yaml", ".yml", ".json"
        # }, f"The preset file must be a YAML or JSON file: {preset_file}"
        # from lzo.utils import parse_envvars_from_text
        
        # text = preset_file.read_text()
        # text, _ = parse_envvars_from_text(text)
        # if preset_file.suffix == ".json":
        #     data = json.loads(text)
        # else:
        #     import yaml
        #     data = yaml.safe_load(text)
        # data = load_preset_config(name, path, **overrides)
        # if overrides: 
        #     from lzo.utils import update_dict
        #     data = update_dict(data, overrides)
        # from lazyops.utils import logger
        data = load_preset_config(name, path, **overrides)
        # logger.info(data)
        provider_settings = cls.model_validate(data)
        ModelContextHandler.add_provider(provider_settings)
        return provider_settings
    
    @property
    def model_list(self) -> List[str]:
        """
        Returns the Model List (excludes the provider name)
        """
        names = [m.name for m in self.models]
        # Add aliases
        for m in self.models:
            if m.aliases:
                names.extend(m.aliases)
        return names
    

    # if PYD_VERSION == 2:
    #     @model_validator(mode = 'after')
    #     def validate_provider_settings(self):
    #         """
    #         Validate the provider settings
    #         """
    #         if self.config.max_retries is not None:
    #             # from lazyops.utils.logs import logger
    #             # logger.info(f'Configuring max retries: {self.config.max_retries}')
    #             self.routes.configure_retry(max_retries = self.config.max_retries)
    #         return self


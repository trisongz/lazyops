from __future__ import annotations

"""
OpenAI Functions Base Class
"""

import json
import inspect
import random
import jinja2

from abc import ABC
from pydantic import Field, BaseModel
from lzl.ext import jinja
from lzl.types import get_schema_extra, ConfigDict
from lzl.types.base import PYDANTIC_VERSION
from lzo.types import Literal
from lzl.api.openai.types.base import Usage
from lzl.api.openai.types import errors
from lzl.api.openai.utils.helpers import weighted_choice
from lzl.api.openai.utils.fixjson import resolve_json
from lzl.api.openai.version import DEFAULT_FUNCTION_MODEL

from typing import Optional, Any, Set, Dict, List, Union, Type, Tuple, TypeVar, Iterable, TYPE_CHECKING


if TYPE_CHECKING:
    from lzl.api.openai.schemas.chat import ChatResponse, ChatRoute, JSONSchema
    from lzl.api.openai.clients import OpenAIManager as OpenAISessionManager
    from lzl.logging import Logger

if PYDANTIC_VERSION == 2:
    from pydantic.json_schema import SkipJsonSchema


FT = TypeVar('FT', bound = BaseModel)
SchemaT = TypeVar('SchemaT', bound = BaseModel)
j2env = jinja.Environment(include_autofilters = True, default_mode='sync')

class BaseFunctionModel(BaseModel):

    if TYPE_CHECKING:
        function_usage: Optional[Usage]

    if PYDANTIC_VERSION == 2:
        function_name: SkipJsonSchema[Union[str, None]] = Field(None, hidden = True)
        function_model: SkipJsonSchema[Union[str, None]] = Field(None, hidden = True)
        function_duration: SkipJsonSchema[Union[float, None]] = Field(None, hidden = True)
        function_client_name: SkipJsonSchema[Union[str, None]] = Field(None, hidden = True)
        function_usage: SkipJsonSchema[Union[Usage, None]] = Field(None, hidden = True)

    else:
        function_name: Optional[str] = Field(None, hidden = True)
        function_model: Optional[str] = Field(None, hidden = True)
        function_duration: Optional[float] = Field(None, hidden = True)
        function_client_name: Optional[str] = Field(None, hidden = True)
        function_usage: Optional[Any] = Field(None, hidden = True)

    def update(
        self,
        values: 'BaseFunctionModel',
    ):
        """
        Updates the values
        """
        pass

    def _setup_item(
        self,
        item: 'SchemaT',
        **kwargs
    ) -> 'SchemaT':
        """
        Updates the Reference Item
        """
        return item
    

    def update_values(
        self,
        item: 'SchemaT',
        **kwargs
    ) -> 'SchemaT':
        """
        Updates the Reference Item with the values
        """
        return item
    

    def update_data(
        self,
        item: 'SchemaT',
        **kwargs
    ) -> 'SchemaT':
        """
        Updates the Reference Item with the values
        """
        item = self._setup_item(item = item, **kwargs)
        item = self.update_values(item = item, **kwargs)
        return item
    

    def is_valid(self) -> bool:
        """
        Returns whether the function data is valid
        """
        return True
    
    def _set_values_from_response(
        self,
        response: 'ChatResponse',
        name: Optional[str] = None,
        client_name: Optional[str] = None,
        **kwargs
    ) -> 'BaseFunctionModel':
        """
        Sets the values from the response
        """
        if name: self.function_name = name
        usage = response.usage
        if isinstance(usage, dict): 
            usage = Usage(**usage)
            
        self.function_usage = usage
        if response.response_ms: self.function_duration = response.response_ms / 1000
        self.function_model = response.model
        if client_name: self.function_client_name = client_name

    @property
    def function_cost(self) -> Optional[float]:
        """
        Returns the function consumption
        """
        if not self.function_model: return None
        if not self.function_usage: return None
        from lzl.api.openai.types.handlers import ModelContextHandler
        return ModelContextHandler.get_consumption_cost(self.function_model, self.function_usage)
    
    @property
    def function_cost_string(self) -> Optional[str]:
        """
        Returns the function consumption as a pretty string
        """
        return f"${self.function_cost:.2f}" if self.function_cost else None


    model_config = ConfigDict(json_schema_extra = get_schema_extra, arbitrary_types_allowed = True)



FunctionSchemaT = TypeVar('FunctionSchemaT', bound = BaseFunctionModel)
FunctionResultT = TypeVar('FunctionResultT', bound = BaseFunctionModel)

class BaseFunction(ABC):
    """
    Base Class for OpenAI Functions
    """
    
    name: Optional[str] = None
    function_name: Optional[str] = None
    description: Optional[str] = None
    schema: Optional[Type[FunctionSchemaT]] = None
    schemas: Optional[Dict[str, Dict[str, Union[str, Type[FunctionSchemaT]]]]] = None

    mode: Optional[Literal['function_call', 'json_schema', 'tool_call', 'compat']] = 'function_call'
    default_schema: Optional[str] = None

    prompt_template: Optional[str] = None
    system_template: Optional[str] = None

    default_model: Optional[Union[str, List[str]]] = DEFAULT_FUNCTION_MODEL
    default_larger_model: Optional[bool] = None
    default_model_weights: Optional[Dict[str, float]] = None
    cachable: Optional[bool] = True
    result_buffer: Optional[int] = 1000
    retry_limit: Optional[int] = 5
    max_attempts: Optional[int] = 2
    version: Optional[str] = None # Can be used as a cache buster
    supports_tokenization: Optional[bool] = True

    default_model_local: Optional[str] = None
    default_model_develop: Optional[str] = None
    default_model_production: Optional[str] = None

    auto_register_function: Optional[bool] = True

    @classmethod
    def configure_subclass(cls, **kwargs):
        """
        Configures the subclass
        """
        pass

    def __init_subclass__(cls, **kwargs):
        """
        Subclass Hook
        """
        cls.configure_subclass(**kwargs)
        if cls.auto_register_function and cls.name and cls.function_name:
            from lzl.api.openai.clients.functions import OpenAIFunctions
            OpenAIFunctions.register_function(cls, initialize = False)
        return super().__init_subclass__(**kwargs)


    def __init__(
        self, 
        api: Optional['OpenAISessionManager'] = None,
        debug_enabled: Optional[bool] = None,
        **kwargs
    ):
        """
        This gets initialized from the Enrichment Handler
        """
        from ..utils.logs import logger, null_logger
        from lzl.api.openai.types.handlers import ModelContextHandler
        self.ctx = ModelContextHandler
        self._setup_api_(api = api)
        self.pool = self.api.pooler
        self.kwargs = kwargs
        self.logger = logger
        self.null_logger = null_logger
        self.settings = self.api.settings
        if debug_enabled is not None:
            self.debug_enabled = debug_enabled
        else:
            self.debug_enabled = self.settings.debug_enabled
        if self.default_model_weights and not isinstance(self.default_model, list):
            self.default_model = list(self.default_model_weights.keys())
        self.build_funcs(**kwargs)
        self.build_templates(**kwargs)
        self.post_init(**kwargs)

    @property
    def default_model_func(self) -> str:
        """
        Returns the default model
        """
        if self.default_model_weights:
            default_model = weighted_choice(self.default_model_weights)
        else:
            default_model = self.default_model if isinstance(self.default_model, str) else random.choice(self.default_model)
        if self.settings.is_local_env:
            return self.default_model_local or default_model
        if self.settings.is_development_env:
            return self.default_model_develop or default_model
        return self.default_model_production or default_model

    @property
    def autologger(self) -> 'Logger':
        """
        Returns the logger
        """
        return self.logger if \
            (self.debug_enabled or self.settings.is_development_env) else self.null_logger


    @property
    def has_diff_model_than_default(self) -> bool:
        """
        Returns True if the default model is different than the default model
        """
        if isinstance(self.default_model, list):
            return self.default_model_func not in self.default_model
        return self.default_model_func != self.default_model

    def _setup_api_(self, api: Optional['OpenAISessionManager'] = None):
        """
        Setup the API
        """
        if api is None:
            from lzl.api.openai.clients import OpenAI
            api = OpenAI
        self.api: 'OpenAISessionManager' = api

    def build_templates(self, **kwargs):
        """
        Construct the templates
        """
        self.template = self.create_template(self.prompt_template)
        # Only create the system template if it's a jinja template
        if self.system_template and '{%' in self.system_template:
            self.system_template = self.create_template(self.system_template)

    def build_funcs(self, **kwargs):
        """
        Builds the functions
        """
        # Handles multi functions
        self.tools = []
        self.functions = []
        self.json_schemas = {}
        self.compat_schemas = {}
        from lzl.api.openai.utils.schemas import generate_json_schema
        if self.schemas:
            for name, data in self.schemas.items():
                self.functions.append({
                    "name": name,
                    "description": data.get('description', self.description),
                    "parameters": data.get('schema', self.schema),
                })
                self.tools.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": data.get('description', self.description),
                        "parameters": data.get('schema', self.schema),
                    },
                })
                self.json_schemas[name] = {
                    "name": name,
                    "description": data.get('description', self.description),
                    "schema": data.get('schema', self.schema),
                    "strict": True,
                    "from_function": True,
                }
                self.compat_schemas[name] = {
                    "description": data.get('description', self.description),
                    "parameters": generate_json_schema(data.get('schema', self.schema)), # .model_json_schema(),
                }
        else:
            self.functions.append({
                "name": self.function_name or self.name,
                "description": self.description,
                "parameters": self.schema,
            })
            self.tools.append({
                "type": "function",
                "function": {
                    "name": self.function_name or self.name,
                    "description": self.description,
                    "parameters": self.schema,
                }
            })
            self.json_schemas[self.function_name or self.name] = {
                "name": self.function_name or self.name,
                "description": self.description,
                "schema": self.schema,
                "strict": True,
                "from_function": True,
            }
            self.compat_schemas[self.function_name or self.name] = {
                "description": self.description,
                "parameters": generate_json_schema(self.schema), # .model_json_schema(),
                # "schema": self.schema.model_json_schema(),
            }
        if not self.default_schema: self.default_schema = list(self.json_schemas.keys())[0]


    def post_init(self, **kwargs):
        """
        Post Init Hook
        """
        pass
    
    def pre_call_hook(self, *args, **kwargs):
        """
        Pre Call Hook
        """
        pass

    async def apre_call_hook(self, *args, **kwargs):
        """
        Pre Call Hook
        """
        self.pre_call_hook(*args, **kwargs)

    def pre_validate(self, *args, **kwargs) -> bool:
        """
        Validate the input before running
        """
        return True

    async def apre_validate(self, *args, **kwargs) -> bool:
        """
        Validate the input before running
        """
        return self.pre_validate(*args, **kwargs)
    

    def pre_validate_model(self, prompt: str, model: str, *args, **kwargs) -> str:
        """
        Validates the model before running
        """
        return model

    async def apre_validate_model(self, prompt: str, model: str, *args, **kwargs) -> str:
        """
        Validates the model before running
        """
        return self.pre_validate_model(prompt = prompt, model = model, *args, **kwargs)


    def call(
        self,
        *args,
        model: Optional[str] = None, 
        **kwargs
    ) -> Optional[FunctionSchemaT]:
        """
        Call the function
        """
        if not self.pre_validate(*args, **kwargs):
            return None
        self.pre_call_hook(*args, **kwargs)
        return self.run_function(*args, model = model, **kwargs)
    
    async def acall(
        self,
        *args,
        model: Optional[str] = None, 
        **kwargs
    ) -> Optional[FunctionSchemaT]:
        """
        Call the function
        """
        if not await self.apre_validate(*args, **kwargs):
            return None
        await self.apre_call_hook(*args, **kwargs)
        return await self.arun_function(*args, model = model, **kwargs)

    def __call__(
        self,
        *args,
        model: Optional[str] = None, 
        is_async: Optional[bool] = True,
        **kwargs
    ) -> Optional[FunctionSchemaT]:
        """
        Call the function
        """
        if is_async: return self.acall(*args, model = model, **kwargs)
        return self.call(*args, model = model, **kwargs)
    
    def raise_max_tries_exhausted(
        self,
        model: str,
        attempts: int,
        max_attempts: int,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        json_schema: Optional[Union['JSONSchema', Dict[str, Any]]] = None,
        schema_name: Optional[str] = None,
        last_chat_name: Optional[str] = None,
        mode: Optional[Literal['function_call', 'json_schema', 'tool_call']] = None,
        **kwargs,
    ):
        """
        Raises the max tries exhausted error
        """
        mode = mode or self.mode
        if mode == 'json_schema':
            func_name = schema_name or (
                json_schema.get('name', self.default_schema) if \
                json_schema else self.default_schema
            )
        elif mode == 'tool_call':
            func_name = tool_name or (
                tools[0]['function']['name']
            ) if tools else self.default_schema
        else:
            func_name = function_name or self.name
        
        func_name = f'[{mode}] {func_name}'
        raise errors.MaxRetriesExhausted(
            name = last_chat_name,
            func_name = func_name,
            model = model,
            attempts = attempts,
            max_attempts = max_attempts,
        )

    def get_chat_client(self, model: str, **kwargs) -> 'ChatRoute':
        """
        Gets the chat client
        """
        return self.api.get_chat_client(model = model, **kwargs)
    
    def get_completion_client(self, model: str, **kwargs) -> 'ChatRoute':
        """
        Gets the chat client
        """
        return self.api.get_chat_client(model = model, **kwargs)
    

    def get_create_func_kwargs_for_function_call(
        self,
        messages: List[Dict[str, Any]],
        chat: 'ChatRoute', 
        disable_cache: Optional[bool] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        property_meta: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the kwargs for the create function
        """
        function_call = "auto" if function_name and function_name == 'auto' else {'name': function_name or self.function_name or self.name}
        if chat.proxy_enabled:
            property_meta = property_meta or {}
            headers = self.settings.proxy.configure_proxy_headers_for_function(
                headers = headers,
                provider = chat.proxy_provider,
                function_name = function_name or self.name,
                disable_cache = disable_cache,
                **property_meta,
            )
        return {
            'messages': messages,
            'functions': functions or self.functions,
            'function_call': function_call,
            'headers': headers,
            **kwargs,
        }
    


    def get_create_func_kwargs_for_compat_function_call(
        self,
        messages: List[Dict[str, Any]],
        chat: 'ChatRoute', 
        disable_cache: Optional[bool] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        property_meta: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        [Compat] Returns the kwargs for the create function

        This is to support models that don't natively support function calls
        """
        function_call = "auto" if function_name and function_name == 'auto' else function_name or self.function_name or self.name
        if chat.proxy_enabled:
            property_meta = property_meta or {}
            headers = self.settings.proxy.configure_proxy_headers_for_function(
                headers = headers,
                provider = chat.proxy_provider,
                function_name = function_name or self.name,
                disable_cache = disable_cache,
                **property_meta,
            )

        if '```json' not in messages[0]['content']:
            schema = self.compat_schemas[function_call]
            # Insert the prompt for the json schema
            schema_msg = f'\nUse the following OpenAPI JSON Schema as your Guide and only respond with the valid JSON that conforms:\n```json\n{json.dumps(schema, indent = 2)}\n```'
            messages[0]['content'] += schema_msg 
        return {
            'messages': messages,
            'headers': headers,
            **kwargs,
        }
    


    def get_create_func_kwargs_for_tool_call(
        self,
        messages: List[Dict[str, Any]],
        chat: 'ChatRoute', 
        disable_cache: Optional[bool] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_name: Optional[str] = None,
        property_meta: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the kwargs for the create function
        """
        tool_choice = "auto" if tool_name and tool_name == 'auto' else {'name': tool_name or self.function_name or self.name}
        if chat.proxy_enabled:
            property_meta = property_meta or {}
            headers = self.settings.proxy.configure_proxy_headers_for_function(
                headers = headers,
                provider = chat.proxy_provider,
                function_name = tool_choice or self.name,
                disable_cache = disable_cache,
                **property_meta,
            )
        return {
            'messages': messages,
            'tools': tools or self.tools,
            'tool_choice': tool_choice,
            'headers': headers,
            **kwargs,
        }

    def get_create_func_kwargs_for_json_schema(
        self,
        messages: List[Dict[str, Any]],
        chat: 'ChatRoute', 
        disable_cache: Optional[bool] = None,
        json_schema: Optional[Union['JSONSchema', Dict[str, Any]]] = None,
        schema_name: Optional[str] = None,
        property_meta: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the kwargs for the create function
        """
        # schema_name = schema_name or self.default_schema
        if not schema_name:
            if json_schema:
                schema_name = json_schema.get('name', self.default_schema)
            else:
                schema_name = self.default_schema
                
        if chat.proxy_enabled:
            property_meta = property_meta or {}
            headers = self.settings.proxy.configure_proxy_headers_for_json_schema(
                headers = headers,
                provider = chat.proxy_provider,
                schema_name = schema_name,
                disable_cache = disable_cache,
                **property_meta,
            )
        return {
            'messages': messages,
            'json_schema': json_schema or self.json_schemas[schema_name],
            'headers': headers,
            **kwargs,
        }

    def get_create_func_kwargs(
        self,
        messages: List[Dict[str, Any]],
        chat: 'ChatRoute', 
        cachable: Optional[bool] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        json_schema: Optional[Union['JSONSchema', Dict[str, Any]]] = None,
        tool_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        schema_name: Optional[str] = None,
        property_meta: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        mode: Optional[Literal['function_call', 'json_schema', 'tool_call']] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the kwargs for the create function
        """
        if mode is None: mode = self.mode
        disable_cache = not cachable if cachable is not None else not self.cachable
        if mode == 'json_schema':
            return self.get_create_func_kwargs_for_json_schema(
                messages = messages,
                chat = chat,
                disable_cache = disable_cache,
                json_schema = json_schema,
                schema_name = schema_name,
                property_meta = property_meta,
                headers = headers,
                **kwargs,
            )
        elif mode == 'tool_call':
            return self.get_create_func_kwargs_for_tool_call(
                messages = messages,
                chat = chat,
                disable_cache = disable_cache,
                tools = tools,
                tool_name = tool_name,
                property_meta = property_meta,
                headers = headers,
                **kwargs,
            )
        elif mode == 'compat':
            return self.get_create_func_kwargs_for_compat_function_call(
                messages = messages,
                chat = chat,
                disable_cache = disable_cache,
                functions = functions,
                function_name = function_name,
                property_meta = property_meta,
                headers = headers,
                **kwargs,
            )
        return self.get_create_func_kwargs_for_function_call(
            messages = messages,
            chat = chat,
            disable_cache = disable_cache,
            functions = functions,
            function_name = function_name,
            property_meta = property_meta,
            headers = headers,
            **kwargs,
        )
    

    def run_chat_function(
        self, 
        messages: List[Dict[str, Any]],
        chat: Optional['ChatRoute'] = None, 
        cachable: Optional[bool] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        json_schema: Optional[Union['JSONSchema', Dict[str, Any]]] = None,
        schema_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        property_meta: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        excluded_clients: Optional[List[str]] = None,
        mode: Optional[Literal['function_call', 'json_schema', 'tool_call']] = None,
        **kwargs,
    ) -> ChatResponse:  # sourcery skip: low-code-quality
        """
        Runs the chat function
        """
        current_attempt = kwargs.pop('_current_attempt', 0)
        last_chat_name = kwargs.pop('_last_chat_name', None)
        if current_attempt and current_attempt > self.retry_limit:
            self.raise_max_tries_exhausted(
                model = model,
                attempts = current_attempt,
                max_attempts = self.retry_limit,
                mode = mode,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                schema_name = schema_name,
                last_chat_name = last_chat_name,
                **kwargs,
            )
        if not chat: 
            if last_chat_name:
                if not excluded_clients: excluded_clients = []
                excluded_clients.append(last_chat_name)
            chat = self.get_chat_client(model = model, excluded_clients = excluded_clients, **kwargs)

        create_kwargs = self.get_create_func_kwargs(
            messages = messages,
            chat = chat,
            cachable = cachable,
            functions = functions,
            function_name = function_name,
            json_schema = json_schema,
            tool_name = tool_name,
            tools = tools,
            schema_name = schema_name,
            property_meta = property_meta,
            headers = headers,
            mode = mode,
            **kwargs,
        )
        try:
            if create_kwargs.get('headers'):
                chat.client.headers.update(create_kwargs.get('headers'))
            return chat.create(
                model = model,
                auto_retry = True,
                auto_retry_limit = 2,
                **create_kwargs,
            )
        except errors.InvalidRequestError as e:
            self.logger.info(f"[{current_attempt}/{self.retry_limit}] [{self.name} - {chat.name}:{model}] Invalid Request Error. |r|{e}|e|", colored=True)
            raise e
        except errors.MaxRetriesExceeded as e:
            self.autologger.info(f"[{current_attempt}/{self.retry_limit}] [{self.name} - {chat.name}:{model}] Retrying...", colored=True)
            return self.run_chat_function(
                messages = messages,
                cachable = cachable,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                schema_name = schema_name,
                tool_name = tool_name,
                tools = tools,
                property_meta = property_meta,
                model = model,
                headers = headers,
                excluded_clients = excluded_clients,
                mode = mode,
                _current_attempt = current_attempt + 1,
                _last_chat_name = chat.name,
                **kwargs,
            )
        except Exception as e:
            self.autologger.info(f"[{current_attempt}/{self.retry_limit}] [{self.name} - {chat.name}:{model}] Unknown Error Trying to run chat function: |r|{e}|e|", colored=True)
            return self.run_chat_function(
                messages = messages,
                cachable = cachable,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                tool_name = tool_name,
                tools = tools,
                schema_name = schema_name,
                property_meta = property_meta,
                model = model,
                headers = headers,
                mode = mode,
                excluded_clients = excluded_clients,
                _current_attempt = current_attempt + 1,
                _last_chat_name = chat.name,
                **kwargs,
            )
    

    async def arun_chat_function(
        self, 
        messages: List[Dict[str, Any]],
        chat: Optional['ChatRoute'] = None, 
        cachable: Optional[bool] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        json_schema: Optional[Union['JSONSchema', Dict[str, Any]]] = None,
        tool_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        schema_name: Optional[str] = None,
        property_meta: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        excluded_clients: Optional[List[str]] = None,
        mode: Optional[Literal['function_call', 'json_schema', 'tool_call']] = None,
        **kwargs,
    ) -> ChatResponse:  # sourcery skip: low-code-quality
        """
        Runs the chat function
        """
        current_attempt = kwargs.pop('_current_attempt', 0)
        last_chat_name = kwargs.pop('_last_chat_name', None)
        if current_attempt and current_attempt > self.retry_limit:
            self.raise_max_tries_exhausted(
                model = model,
                attempts = current_attempt,
                max_attempts = self.retry_limit,
                mode = mode,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                tool_name = tool_name,
                tools = tools,
                schema_name = schema_name,
                last_chat_name = last_chat_name,
                **kwargs,
            )

        if not chat: 
            if last_chat_name:
                if not excluded_clients: excluded_clients = []
                excluded_clients.append(last_chat_name)
            chat = self.get_chat_client(model = model, excluded_clients = excluded_clients, **kwargs)

        create_kwargs = self.get_create_func_kwargs(
            messages = messages,
            chat = chat,
            cachable = cachable,
            functions = functions,
            function_name = function_name,
            json_schema = json_schema,
            tool_name = tool_name,
            tools = tools,
            schema_name = schema_name,
            property_meta = property_meta,
            headers = headers,
            mode = mode,
            **kwargs,
        )
        try:
            if create_kwargs.get('headers'):
                chat.client.headers.update(create_kwargs.get('headers'))
            return await chat.async_create(
                model = model,
                auto_retry = True,
                auto_retry_limit = 2,
                **create_kwargs,
            )
        except errors.InvalidRequestError as e:
            self.logger.info(f"[{current_attempt}/{self.retry_limit}] [{self.name} - {chat.name}:{model}] Invalid Request Error. |r|{e}|e|", colored=True)
            raise e
        except errors.MaxRetriesExceeded as e:
            self.autologger.info(f"[{current_attempt}/{self.retry_limit}] [{self.name} - {chat.name}:{model}] Retrying...", colored=True)
            return await self.arun_chat_function(
                messages = messages,
                cachable = cachable,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                schema_name = schema_name,
                tool_name = tool_name,
                tools = tools,
                property_meta = property_meta,
                model = model,
                headers = headers,
                excluded_clients = excluded_clients,
                mode = mode,
                _current_attempt = current_attempt + 1,
                _last_chat_name = chat.name,
                **kwargs,
            )
        except Exception as e:
            if current_attempt == self.retry_limit:
                self.autologger.trace(f"[{current_attempt}/{self.retry_limit}] [{self.name} - {chat.name}:{model}] Unknown Error Trying to run chat function", e)
            else:
                self.autologger.info(f"[{current_attempt}/{self.retry_limit}] [{self.name} - {chat.name}:{model}] Unknown Error Trying to run chat function: {type(e).__name__} |r|{e}|e|", colored=True)
            return await self.arun_chat_function(
                messages = messages,
                cachable = cachable,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                tool_name = tool_name,
                tools = tools,
                schema_name = schema_name,
                property_meta = property_meta,
                model = model,
                headers = headers,
                mode = mode,
                excluded_clients = excluded_clients,
                _current_attempt = current_attempt + 1,
                _last_chat_name = chat.name,
                **kwargs,
            )
    
    def get_schema_for_response(
        self,
        response: 'ChatResponse',
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        json_schema: Optional[Union['JSONSchema', Dict[str, Any]]] = None,
        tool_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        schema_name: Optional[str] = None,
    ) -> Type[FunctionSchemaT]:
        """
        Gets the schema for the response
        """
        if response.has_json_schema:
            if json_schema: return json_schema
            if response.input_object.json_schema and response.input_object.json_schema.source_object:
                return response.input_object.json_schema.source_object
            schema_name = schema_name or self.default_schema
            return self.json_schemas[schema_name]['schema']
        
        elif response.has_tools:
            tool_choice = tool_name or self.name
            if tools:
                for tool in tools:
                    if tool.get('function', {}).get('name') == tool_choice:
                        return tool.get('function', {}).get('parameters')
            
            return self.schema or self.schemas[tool_choice]

        # else:
        function_name = function_name or self.name
        if functions: 
            for func in functions:
                if func.get('parameters') == function_name:
                    return func.get('parameters')
        return self.schema or self.schemas[function_name]
    
    def parse_response(
        self,
        response: 'ChatResponse',
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        json_schema: Optional[Union['JSONSchema', Dict[str, Any]]] = None,
        tool_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        schema_name: Optional[str] = None,
        include_name: Optional[bool] = True,
        client_name: Optional[str] = None,
    ) -> Optional[FunctionSchemaT]:  # sourcery skip: extract-duplicate-method, merge-else-if-into-elif
        """
        Parses the response
        """
        schema: 'FunctionSchemaT' = self.get_schema_for_response(
            response,
            functions = functions,
            function_name = function_name,
            json_schema = json_schema,
            tool_name = tool_name,
            tools = tools,
            schema_name = schema_name,
        )
        # schema = schema or self.schema
        try:
            if response.has_json_schema:
                result = schema.model_validate_json(
                    response.messages[0].content, 
                    context = {'source': 'function'}
                )
            elif response.has_tools:
                result = schema.model_validate(
                    response.messages[0].tool_calls[0].function.arguments, 
                    context = {'source': 'function'}
                )
            elif response.has_functions or response.function_results:
                result = schema.model_validate(
                    response.function_results[0].arguments, 
                    from_attributes = True, 
                    context = {'source': 'function'}
                )
            else:
                # This is a compat model
                if '```json' in response.messages[0].content:
                    json_body = response.messages[0].content.split('```json', 1)[1].split('```', 1)[0]
                    result = schema.model_validate_json(json_body, context = {'source': 'function'})
                else:
                    result = schema.model_validate(
                        response.messages[0].content, 
                        context = {'source': 'function'}
                    )
            
            result._set_values_from_response(response, name = self.name if include_name else None, client_name = client_name)
            return result
        except IndexError as e:
            self.autologger.error(f"[{self.name} - {response.model} - {response.usage}] No function results found: {e}\n{response.text}")
            return None
        except Exception as e:
            if response.has_json_schema:
                self.autologger.error(f"[{self.name} - {response.model} - {response.usage}] Failed to parse json schema: {e}\n{response.text}\n{response.messages[0].content}")
            else:
                self.autologger.error(f"[{self.name} - {response.model} - {response.usage}] Failed to parse object: {e}\n{response.text}\n{response.function_results[0].arguments}")
            try:
                if response.has_json_schema:
                    result = schema.model_validate(resolve_json(response.messages[0].content), from_attributes = True, context = {'source': 'function'})
                else:
                    result = schema.model_validate(resolve_json(response.function_results[0].arguments), from_attributes = True, context = {'source': 'function'})
                result._set_values_from_response(response, name = self.name if include_name else None)
                return result
            except Exception as e:
                self.autologger.error(f"[{self.name} - {response.model} - {response.usage}] Failed to parse object after fixing: {type(e).__name__} {e}")
                return None
    

    def is_valid_response(self, response: FT) -> bool:
        """
        Returns True if the response is valid
        """
        return True
    
    def apply_text_cleaning(self, text: str) -> str:
        """
        Applies text cleaning
        """
        from lazyops.utils.format_utils import clean_html, clean_text, cleanup_dots
        if "..." in text: text = cleanup_dots(text)
        return clean_html(clean_text(text))
    
    @staticmethod
    def create_template(template: str, enable_async: Optional[bool] = False, **kwargs) -> jinja2.Template:
        """
        Creates the template
        """
        mode = 'async' if enable_async else 'sync'
        return j2env.get_template(template, mode = mode, is_raw = True, **kwargs)
        # return jinja2.Template(template, enable_async = enable_async, **kwargs)
    
    def truncate_documents(
        self, 
        documents: Dict[str, str],
        max_length: Optional[int] = None,
        buffer_size: Optional[int] = None,
        model: Optional[str] = None,
        truncation_length: Optional[int] = None,
    ) -> Dict[str, str]:
        """
        Helper Function to truncate supporting docs
        """
        current_length = 0
        if max_length is None:
            model = model or self.default_model_func
            max_length = self.ctx.get(model).context_length
        if buffer_size is None: buffer_size = self.result_buffer
        max_length -= buffer_size

        truncation_length = truncation_length or (max_length // len(documents))
        new_documents = {}
        for file_name, file_text in documents.items():
            if not file_text: continue
            file_text = self.apply_text_cleaning(file_text)[:truncation_length]
            current_length += len(file_text)
            new_documents[file_name] = file_text
            if current_length > max_length: break
        return new_documents
    
    """
    Function Handlers
    """

    def prepare_function_inputs(
        self,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Prepare the Function Inputs for the function
        """
        model = model or self.default_model_func
        prompt = self.template.render(**kwargs)
        if self.supports_tokenization:
            prompt = self.api.truncate_to_max_length(prompt, model = model, buffer_length = self.result_buffer)
        messages = []
        if self.system_template:
            if isinstance(self.system_template, jinja2.Template):
                system_template = self.system_template.render(**kwargs)
            else:
                system_template = self.system_template
            system_role = "system" if "o1" not in model else "user"
            if self.mode == 'compat' and '```json' not in system_template:
                system_template += f'\nUse the following OpenAPI JSON Schema as your Guide and only respond with the valid JSON that conforms:\n```json\n{json.dumps(self.compat_schemas[self.function_name], indent = 2)}\n```'
            messages.append({
                # "role": "system",
                "role": system_role,
                "content": system_template,
            })
        messages.append({
            "role": "user", 
            "content": prompt,
        })
        return messages, model
    
    async def aprepare_function_inputs(
        self,
        model: Optional[str] = None,
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Prepare the Function Inputs for the function
        """
        model = model or self.default_model_func
        # self.autologger.info(kwargs)
        try:
            prompt = self.template.render(**kwargs)
        except Exception as e:
            self.autologger.error(f'Error Rendering Prompt: {e}: {kwargs}')
            raise e
        if self.supports_tokenization:
            prompt = await self.api.atruncate_to_max_length(prompt, model = model, buffer_length = self.result_buffer)
        messages = []
        if self.system_template:
            if isinstance(self.system_template, jinja2.Template):
                system_template = self.system_template.render(**kwargs)
            else:
                system_template = self.system_template
            system_role = "system" if "o1" not in model else "user"
            if self.mode == 'compat' and '```json' not in system_template:
                system_template += f'\nUse the following OpenAPI JSON Schema as your Guide and only respond with the valid JSON that conforms:\n```json\n{json.dumps(self.compat_schemas[self.function_name], indent = 2)}\n```'
            messages.append({
                # "role": "system",
                "role": system_role,
                "content": system_template,
            })
        messages.append({
            "role": "user", 
            "content": prompt,
        })
        return messages, model

    def run_function(
        self,
        *args,
        model: Optional[str] = None, 
        **kwargs
    ) -> Optional[FunctionSchemaT]:
        """
        Returns the Function Result
        """
        messages, model = self.prepare_function_inputs(model = model, **kwargs)
        return self.run_function_loop(messages = messages, model = model, **kwargs)

    async def arun_function(
        self,
        *args,
        model: Optional[str] = None, 
        **kwargs
    ) -> Optional[FunctionSchemaT]:
        """
        Returns the Function Result
        """
        messages, model = await self.aprepare_function_inputs(model = model, **kwargs)
        return await self.arun_function_loop(messages = messages, model = model, **kwargs)
    
    def get_function_kwargs(self) -> Dict[str, Any]:
        """
        Returns the function kwargs
        """
        sig = inspect.signature(self.arun_function)
        return [p.name for p in sig.parameters.values() if p.kind in {p.KEYWORD_ONLY, p.VAR_KEYWORD, p.POSITIONAL_OR_KEYWORD} and p.name not in {'kwargs', 'args', 'model'}]

    """
    Batch Handler
    """
    def _get_batch_params(
        self,
        *args,
        batch: Optional[Iterable[Dict[str, Any]]] = None,
        model: Optional[str] = None, 
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Returns the batch params to run this as a batch
        """
        if not self.pre_validate(*args, **kwargs):
            return None
        self.pre_call_hook(*args, **kwargs)
        batch_params = []
        batch = batch or [kwargs]
        for batch_item in batch:
            messages, model = self.prepare_function_inputs(model = model, **batch_item)
            batch_params.append({"model": model, "messages": messages})
        return batch_params

    async def _aget_batch_params(
        self,
        *args,
        batch: Optional[Iterable[Dict[str, Any]]] = None,
        model: Optional[str] = None, 
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Returns the batch params to run this as a batch
        """
        if not await self.apre_validate(*args, **kwargs):
            return None
        await self.apre_call_hook(*args, **kwargs)
        batch_params = []
        batch = batch or [kwargs]
        for batch_item in batch:
            messages, model = await self.aprepare_function_inputs(model = model, **batch_item)
            batch_params.append({"model": model, "messages": messages})
        return batch_params

    def get_batch_params(
        self,
        *args,
        batch: Optional[Iterable[Dict[str, Any]]] = None,
        model: Optional[str] = None, 
        is_async: Optional[bool] = None,
        **kwargs
    ):
        """
        Gets the batch params to run this as a batch
        """
        func = self._aget_batch_params if is_async else self._get_batch_params
        return func(*args, batch = batch, model = model, **kwargs)

    """
    Handle a Loop
    """

    def run_function_loop(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        json_schema: Optional[Union['JSONSchema', Dict[str, Any]]] = None,
        tool_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        schema_name: Optional[str] = None,
        mode: Optional[Literal['function_call', 'json_schema', 'tool_call']] = None,
        raise_errors: Optional[bool] = True,
        **kwargs,
    ) -> Optional[FunctionSchemaT]:
        """
        Runs the function loop
        """
        chat = self.get_chat_client(model = model, **kwargs)
        response = self.run_chat_function(
            messages = messages,
            chat = chat,
            functions = functions,
            function_name = function_name,
            json_schema = json_schema,
            tool_name = tool_name,
            tools = tools,
            schema_name = schema_name,
            model = model,
            mode = mode,
            **kwargs,
        )

        result = self.parse_response(
            response, 
            functions = functions,
            function_name = function_name,
            json_schema = json_schema,
            tool_name = tool_name,
            tools = tools,
            schema_name = schema_name,
            include_name = True, 
            client_name = chat.name
        )
        if result is not None: return result

        # Try Again
        attempts = 1
        _ = kwargs.pop('cachable', None)
        while attempts < self.max_attempts:
            chat = self.get_chat_client(model = model, **kwargs)
            response = self.run_chat_function(
                messages = messages,
                chat = chat,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                tool_name = tool_name,
                tools = tools,
                schema_name = schema_name,
                model = model,
                mode = mode,
                cachable = False,
                **kwargs,
            )
            result = self.parse_response(
                response, 
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                tool_name = tool_name,
                tools = tools,
                schema_name = schema_name,
                include_name = True, 
                client_name = chat.name
            )
            if result is not None: return result
            attempts += 1
        self.autologger.error(f"[{chat.name}:{model}] Unable to parse the response for {self.name} after {self.max_attempts} attempts.")
        if raise_errors: self.raise_max_tries_exhausted(
                model = model,
                attempts = attempts,
                max_attempts = self.max_attempts,
                mode = mode,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                tool_name = tool_name,
                tools = tools,
                schema_name = schema_name,
                last_chat_name = chat.name,
                **kwargs,
            )
        return None

    async def arun_function_loop(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_name: Optional[str] = None,
        json_schema: Optional[Union['JSONSchema', Dict[str, Any]]] = None,
        tool_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        schema_name: Optional[str] = None,
        mode: Optional[Literal['function_call', 'json_schema', 'tool_call']] = None,
        raise_errors: Optional[bool] = True,
        **kwargs,
    ) -> Optional[FunctionSchemaT]:
        """
        Runs the function loop
        """
        chat = self.get_chat_client(model = model, **kwargs)
        # self.logger.info(f'Running Chat Function: {function_name} with {chat.name}:{model}')
        response = await self.arun_chat_function(
            messages = messages,
            chat = chat,
            functions = functions,
            function_name = function_name,
            json_schema = json_schema,
            tool_name = tool_name,
            tools = tools,
            schema_name = schema_name,
            model = model,
            mode = mode,
            **kwargs,
        )
        result = self.parse_response(
            response, 
            functions = functions,
            function_name = function_name,
            json_schema = json_schema,
            schema_name = schema_name,
            tool_name = tool_name,
            tools = tools,
            include_name = True, 
            client_name = chat.name
        )
        if result is not None: return result

        # Try Again
        attempts = 1
        _ = kwargs.pop('cachable', None)
        while attempts < self.max_attempts:
            chat = self.get_chat_client(model = model, **kwargs)
            response = await self.arun_chat_function(
                messages = messages,
                chat = chat,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                tool_name = tool_name,
                tools = tools,
                schema_name = schema_name,
                model = model,
                mode = mode,
                cachable = False,
                **kwargs,
            )
            result = self.parse_response(
                response, 
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                tool_name = tool_name,
                tools = tools,
                schema_name = schema_name,
                include_name = True, 
                client_name = chat.name
            )
            if result is not None: return result
            attempts += 1
        self.autologger.error(f"[{chat.name}:{model}] Unable to parse the response for {self.name} after {self.max_attempts} attempts.")
        if raise_errors: self.raise_max_tries_exhausted(
                model = model,
                attempts = attempts,
                max_attempts = self.max_attempts,
                mode = mode,
                functions = functions,
                function_name = function_name,
                json_schema = json_schema,
                tool_name = tool_name,
                tools = tools,
                schema_name = schema_name,
                last_chat_name = chat.name,
                **kwargs,
            )
        return None

    

FunctionT = TypeVar('FunctionT', bound = BaseFunction)


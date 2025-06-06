
from __future__ import annotations

import json
import enum
import time
import asyncio
import functools
import contextlib
from lzl.api import aiohttpx
from typing import Optional, Type, Any, Union, List, Dict, Iterator, TypeVar, AsyncIterator, Generator, AsyncGenerator, overload, TYPE_CHECKING

from lzo.types import (
    Literal, 
    eproperty, 
    BaseModel,
    validator, 
    root_validator, 
    Field,
    PYDANTIC_VERSION, 
)
from lzl.types.base import get_pydantic_schema, field_validator
from lzl.api.openai.version import DEFAULT_CHAT_MODEL
from lzl.api.openai.types.handlers import ModelContextHandler
from lzl.api.openai.types.base import BaseResource, Usage
from lzl.api.openai.types.responses import BaseResponse
from lzl.api.openai.types.routes import BaseRoute
from lzl.api.openai.utils import logger, parse_stream, aparse_stream, resolve_json
from lzl.api.openai.utils.schemas import generate_json_schema, function_generate_json_schema

__all__ = [
    'ChatMessage',
    'ChatChoice',
    'Function',
    'ChatObject',
    'CompletionResponse',
    'CompletionRoute',
]

SchemaObj = TypeVar("SchemaObj", bound=BaseModel)
SchemaType = TypeVar("SchemaType", bound=Type[BaseModel])




class MessageKind(str, enum.Enum):
    CONTENT = 'content'
    ROLE = 'role'
    FUNCTION_CALL = 'function_call'

    @classmethod
    def from_choice(cls, choice: Dict[str, Any]) -> 'MessageKind':
        """
        Returns the message kind from the choice
        """
        if 'role' in choice['delta']:
            return cls.ROLE
        elif 'content' in choice['delta']:
            return cls.CONTENT
        elif 'function_call' in choice['delta']:
            return cls.FUNCTION_CALL
        raise ValueError(f'Invalid choice: {choice}')



class StreamedChatMessage(BaseResource):
    kind: MessageKind
    value: Union[Dict[str, Any], str]

class FunctionCall(BaseResource):
    name: str
    arguments: Optional[Union[str, Dict[str, Any]]] = None

    @field_validator('arguments')
    def validate_arguments(cls, v) -> Dict[str, Any]:
        """
        Try to load the arguments as json
        """
        if isinstance(v, dict):
            return v
        elif isinstance(v, str):
            with contextlib.suppress(Exception):
                return json.loads(v)
        return v

class ToolCall(BaseResource):
    id: Optional[str] = None
    type: Optional[str] = None
    function: Optional[FunctionCall] = None


# TODO Add support for name
class ChatMessage(BaseResource):
    content: Optional[str] = None
    role: Optional[str] = "user"
    function_call: Optional[FunctionCall] = None
    tool_calls: Optional[List[ToolCall]] = None
    name: Optional[str] = None

    def dict(self, *args, exclude_none: bool = True, **kwargs):
        return self.model_dump(*args, exclude_none = exclude_none, **kwargs)


class ChatChoice(BaseResource):
    message: ChatMessage
    index: int
    logprobs: Optional[Any] = None
    finish_reason: Optional[str] = None

    def __getitem__(self, key: str) -> Any:
        """
        Mimic dict
        """
        return getattr(self, key)

class Function(BaseResource):
    """
    Represents a function
    """
    # Must be a-z, A-Z, 0-9, or contain underscores and dashes
    if PYDANTIC_VERSION == 2:
        name: str = Field(..., max_length = 64, pattern = r'^[a-zA-Z0-9_]+$')
    else:
        name: str = Field(..., max_length = 64, regex = r'^[a-zA-Z0-9_]+$')
    
    parameters: Union[Dict[str, Any], SchemaType, str]
    description: Optional[str] = None
    # Add optional enforcement of structured outputs
    # strict: Optional[bool] = None

    source_object: Optional[Union[SchemaType, Any]] = Field(default = None, exclude = True)

    @root_validator(pre = True)
    def validate_parameters(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the parameters
        """
        if params := values.get('parameters'):
            if isinstance(params, dict):
                pass
            elif issubclass(params, BaseModel) or isinstance(params, type(BaseModel)):
                values['parameters'] = get_pydantic_schema(params)
                # params.schema()
                values['source_object'] = params
            elif isinstance(params, str):
                try:
                    values['parameters'] = json.loads(params)
                except Exception as e:
                    raise ValueError(f'Invalid JSON: {params}, {e}. Must be a dict or pydantic BaseModel.') from e
            else:
                # logger.warning(f'Invalid parameters: {params}. Must be a dict or pydantic BaseModel.')
                raise ValueError(f'Parameters must be a dict or pydantic BaseModel. Provided: {type(params)}')
        return values

class JSONSchema(BaseResource):
    """
    Represents a JSON Schema
    """
    if PYDANTIC_VERSION == 2:
        name: str = Field(..., max_length = 64, pattern = r'^[a-zA-Z0-9_]+$')
    else:
        name: str = Field(..., max_length = 64, regex = r'^[a-zA-Z0-9_]+$')
    
    # This raises a warning Field name "schema" in "JSONSchema" shadows an attribute in parent "BaseModel"
    # So we alias it to jschema
    jschema: Union[Dict[str, Any], SchemaType, str] = Field(..., alias = 'schema')
    description: Optional[str] = None
    strict: Optional[bool] = True
    from_function: Optional[bool] = Field(None, exclude = True)
    source_object: Optional[Union[SchemaType, Any]] = Field(default = None, exclude = True)

    @root_validator(pre = True)
    def validate_json_schema(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the schema
        """
        from_func = values.get('from_function', False)
        if schema := values.get('schema'):
            if isinstance(schema, dict):
                pass
            elif issubclass(schema, BaseModel) or isinstance(schema, type(BaseModel)):
                values['schema'] = function_generate_json_schema(schema) if from_func else generate_json_schema(schema)
                values['source_object'] = schema
            elif isinstance(schema, str):
                try:
                    values['schema'] = json.loads(schema)
                except Exception as e:
                    raise ValueError(f'Invalid JSON: {schema}, {e}. Must be a dict or pydantic BaseModel.') from e
            else:
                # logger.warning(f'Invalid parameters: {params}. Must be a dict or pydantic BaseModel.')
                raise ValueError(f'Schema must be a dict or pydantic BaseModel. Provided: {type(schema)}')
        return values


class Tool(BaseResource):
    """
    Represents a tool 
    """
    type: Optional[str] = 'function'
    function: Optional[Function] = None


class ChatObject(BaseResource):
    messages: Union[List[ChatMessage], str]
    model: Optional[str] = DEFAULT_CHAT_MODEL

    max_tokens: Optional[int] = None
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    logprobs: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

    functions: Optional[List[Function]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None

    # v2 Params
    # response_format: Optional[Dict[str, Literal['json_object', 'text']]] = None
    # Don't enforce response_format
    json_schema: Optional[Union[JSONSchema, Dict[str, Any]]] = None # Field(default = None, exclude = True)
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None

    # tools: Optional[Union[List[Function], List[Dict[str, Union[str, Function]]]]] = None
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, Union[str, Dict[str, str]]]] = None

    # Extra Params
    validate_max_tokens: Optional[bool] = Field(default = False, exclude = True)
    validate_model_aliases: Optional[bool] = Field(default = False, exclude = True)
    # api_version: Optional[str] = None

    # @validator('messages', pre = True, always = True)
    @field_validator('messages', mode = 'before')
    def validate_messages(cls, v) -> List[ChatMessage]:
        """
        Validate the Input Messages
        """
        vals = []
        if not isinstance(v, list):
            v = [v]
        for i in v:
            if isinstance(i, dict):
                vals.append(ChatMessage.model_validate(i))
            elif isinstance(i, str):
                vals.append(ChatMessage(content = i))
            else:
                vals.append(i)
        return vals

    # @validator('model', pre=True, always=True)
    @field_validator('model', mode = 'before')
    def validate_model(cls, v, values: Dict[str, Any]) -> str:
        """
        Validate the model
        """
        if not v:
            if values.get('engine'):
                v = values.get('engine')
            elif values.get('deployment'):
                v = values.get('deployment')
        with contextlib.suppress(KeyError):
            v = ModelContextHandler.resolve_model_name(v)
        # if values.get('validate_model_aliases', False):
        #     v = ModelContextHandler[v].name
        return v
        
    
    @validator('temperature')
    def validate_temperature(cls, v: float) -> float:
        """
        Min Temperature is 0.0
        https://beta.openai.com/docs/api-reference/completions/create#completions/create-temperature
        """
        return None if v is None else max(0.0, v)
    
    @validator('top_p')
    def validate_top_p(cls, v: float) -> float:
        """
        Min Top Probability is 0.0
        https://beta.openai.com/docs/api-reference/completions/create#completions/create-top-probability
        """
        return None if v is None else max(0.0, v)

    @validator('logprobs')
    def validate_logprobs(cls, v: int) -> int:
        """
        Max logprobs is 5
        https://beta.openai.com/docs/api-reference/completions/create#completions/create-logprobs
        """
        return None if v is None else max(0, min(v, 5))
    
    @validator('presence_penalty')
    def validate_presence_penalty(cls, v: float) -> float:
        """
        Min Presence Penalty is -2.0, Max is 2.0
        https://beta.openai.com/docs/api-reference/completions/create#completions/create-presence-penalty
        """
        return None if v is None else max(0.0, min(v, 2.0))
    
    @validator('frequency_penalty')
    def validate_frequency_penalty(cls, v: float) -> float:
        """
        Min Frequency Penalty is -2.0, Max is 2.0
        https://beta.openai.com/docs/api-reference/completions/create#completions/create-frequency-penalty
        """
        return None if v is None else max(0.0, min(v, 2.0))

    def dict(self, *args, exclude: Any = None, **kwargs):
        """
        Returns the dict representation of the response
        """
        return super().dict(*args, exclude = exclude, **kwargs)

    @root_validator(pre = True)
    def validate_obj(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the object
        """

        is_azure = values.pop('is_azure', False)
        if values.get('functions'):
            if not all(isinstance(f, Function) for f in values['functions']):
                values['functions'] = [Function(**f) for f in values['functions']]
            
            if not values.get('function_call'):
                values['function_call'] = 'auto'
        
        if values.get('json_schema'):
            if not isinstance(values['json_schema'], JSONSchema):
                values['json_schema'] = JSONSchema(**values['json_schema'])
            values['response_format'] = {
                'type': 'json_schema',
                'json_schema': values['json_schema'],
            }

        if values.get('tools'):
            tools = []
            for tool in values['tools']:
                if isinstance(tool, Tool):
                    tools.append(tool)
                elif isinstance(tool, dict):
                    # This should be the correct format
                    if tool.get('function'):
                        tools.append(Tool(**tool))
                    else:
                        # This is previously supported format
                        tools.append(Tool(function = Function(**tool)))
                else:
                    raise ValueError(f'Invalid tool: {tool}')
            values['tools'] = tools
            if not values.get('tool_choice'):
                values['tool_choice'] = 'auto'

            # Auto set to json_object if tools are present
            # if values.get('response_format') is None:
            #     values['response_format'] = {'type': 'json_object'}

        # Validate for Azure
        if is_azure and values.get('tools') and not values.get('functions'):
            # Convert tools to functions
            values['functions'] = [tool.function for tool in values['tools']]
            if not values.get('function_call'):
                values['function_call'] = 'auto'

        return values


class ChatResponse(BaseResponse):
    choices: Optional[List[ChatChoice]] = None
    choice_model: Optional[Type[BaseResource]] = ChatChoice
    input_object: Optional[ChatObject] = None

    @eproperty
    def messages(self) -> List[ChatMessage]:
        """
        Returns the messages for the completions
        """
        if self.choices_results:
            return [choice.message for choice in self.choices]
        return self.response.text
    
    @eproperty
    def json_schema(self) -> Optional[Union[SchemaType, Dict[str, Any]]]:
        """
        Returns the JSON Schema for the completions
        """
        if self.choices_results:
            if self.input_object.json_schema:
                message = self.messages[0]
                if self.input_object.json_schema.source_object:
                    return self.input_object.json_schema.source_object.model_validate_json(message.content)
                if not isinstance(message.content, dict):
                    message.content = json.loads(message.content)
                return message.content
        return None
    

    @eproperty
    def has_json_schema(self) -> bool:
        """
        Returns whether the response has a JSON Schema
        """
        return bool(self.input_object.json_schema)
    
    @eproperty
    def has_tools(self) -> bool:
        """
        Returns whether the response has tools
        """
        return bool(self.input_object.tools)
    
    @eproperty
    def function_results(self) -> List[FunctionCall]:
        """
        Returns the function results for the completions
        """
        return [msg.function_call for msg in self.messages if msg.function_call]
    
    @eproperty
    def function_result_objects(self) -> List[Union[SchemaObj, Dict[str, Any]]]:
        """
        Returns the function result objects for the completions
        """
        results = []
        source_function: Function = self.input_object.functions[0] if self.input_object.function_call == "auto" else (
            [
                f for f in self.input_object.functions if f.name == self.input_object.function_call['name']
            ]
        )[0]

        for func_result in self.function_results:
            if source_function.source_object:
                if not isinstance(func_result.arguments, dict):
                    try:
                        func_result.arguments = resolve_json(func_result.arguments)
                    except Exception as e:
                        logger.error('Could not resolve function arguments. Skipping.')
                        continue
                try:
                    results.append(source_function.source_object(**func_result.arguments))
                    continue
                except Exception as e:
                    logger.error(e)
            if isinstance(func_result.arguments, dict):
                results.append(func_result.arguments)
            else:
                try:
                    results.append(resolve_json(func_result.arguments))
                except Exception as e:

                    logger.error(e)
                    results.append(func_result.arguments)

        return results
    
    @eproperty
    def has_functions(self) -> bool:
        """
        Returns whether the response has functions
        """
        return bool(self.input_object.functions)
    

    @eproperty
    def tool_results(self) -> List[FunctionCall]:
        """
        Returns the tool results for the completions
        """
        # if self.has_tools:
        #     return [msg.tool_calls[0].function for msg in self.messages if msg.tool_calls]
        return [msg.function_call for msg in self.messages if msg.function_call]
    
    @eproperty
    def tool_result_objects(self) -> List[Union[SchemaObj, Dict[str, Any]]]:
        """
        Returns the tool result objects for the completions
        """
        results = []
        source_function: Function = self.input_object.tools[0].function.source_object if self.input_object.tool_choice == "auto" else (
            [
                t.function for t in self.input_object.tools if t.function.name == self.input_object.tool_choice['function']['name']
            ]
        )[0]

        for tool_result in self.tool_results:
            if source_function.source_object:
                if not isinstance(tool_result.arguments, dict):
                    try:
                        tool_result.arguments = resolve_json(tool_result.arguments)
                    except Exception as e:
                        logger.error('Could not resolve function arguments. Skipping.')
                        continue
                try:
                    results.append(source_function.source_object(**tool_result.arguments))
                    continue
                except Exception as e:
                    logger.error(e)
            if isinstance(tool_result.arguments, dict):
                results.append(tool_result.arguments)
            else:
                try:
                    results.append(resolve_json(tool_result.arguments))
                except Exception as e:

                    logger.error(e)
                    results.append(tool_result.arguments)

        return results

    @eproperty
    def has_tools(self) -> bool:
        """
        Returns whether the response has tools
        """
        return bool(self.input_object.tools)

    @eproperty
    def input_text(self) -> str:
        """
        Returns the input text for the input prompt
        """
        return '\n'.join([f'{msg.role}: {msg.content}' for msg in self.input_object.messages])

    @eproperty
    def input_messages(self) -> List[ChatMessage]:
        """
        Returns the input messages for the input prompt
        """
        return self.input_object.messages

    @eproperty
    def text(self) -> str:
        """
        Returns the text for the chat response
        """
        if self.choices_results:
            return '\n'.join([f'{msg.role}: {msg.content}' for msg in self.messages])
        return self.response.text


    @eproperty
    def only_text(self) -> str:
        """
        Returns the text for the chat response without the role
        """
        if self.has_tools:
            data = []
            for tool_obj in self.tool_result_objects:
                if isinstance(tool_obj, BaseModel):
                    data.append(tool_obj.model_dump())
                else:
                    data.append(tool_obj)
            return json.dumps(data, indent = 2)
        if self.has_functions:
            data = []
            for func_obj in self.function_result_objects:
                if isinstance(func_obj, BaseModel):
                    data.append(func_obj.model_dump())
                else:
                    data.append(func_obj)
            return json.dumps(data, indent = 2)
        if self.choices_results:
            return '\n'.join([msg.content for msg in self.messages])
        return self.response.text

    @eproperty
    def chat_model(self) -> Optional[str]:
        """
        Returns the model for the completions
        """
        return self.input_object.model or None
        # return OpenAIModel(value=self.model, mode='chat') if self.model else None
    
    @eproperty
    def openai_model(self):
        """
        Returns the model for the completions
        """
        return self.headers.get('openai-model', self.chat_model)
    
    def _validate_usage(self):
        """
        Validate usage
        """
        if self.usage and self.usage.total_tokens and self.usage.prompt_tokens: return
        if self.response.status_code == 200:
            self.usage = Usage(
                prompt_tokens = ModelContextHandler.count_chat_tokens(self.input_messages, model_name = self.openai_model),
                completion_tokens = ModelContextHandler.count_chat_tokens(self.messages, model_name = self.openai_model),
            )
            self.usage.total_tokens = self.usage.prompt_tokens + self.usage.completion_tokens


    @eproperty
    def consumption(self) -> int:
        """
        Returns the consumption for the completions
        """ 
        self._validate_usage()
        return ModelContextHandler.get_consumption_cost(
            model_name = self.openai_model,
            usage = self.usage,
        )
    

    def dict(self, *args, exclude: Any = None, **kwargs):
        """
        Returns the dict representation of the response
        """
        return super().dict(*args, exclude = exclude, **kwargs)
    

    def __getitem__(self, key: str) -> Any:
        """
        Mimic dict
        """
        return getattr(self, key)
    

    def parse_stream_item(self, item: Union[Dict, Any], **kwargs) -> Optional[StreamedChatMessage]:
        """
        Parses a single stream item
        """
        # logger.info(f'Item: {item}')
        if not item['choices']: return None
        choice = item['choices'][0]
        if choice['finish_reason'] in ['stop', 'function_call']:
            return None
        kind = MessageKind.from_choice(choice)
        return StreamedChatMessage(
            kind = kind,
            value = choice['delta'].get(kind.value, '')
        )
    
    def handle_stream(
        self,
        response: aiohttpx.Response,
        streaming: Optional[bool] = False,
    ) -> Iterator[Dict]:  # sourcery skip: low-code-quality
        """
        Handle the stream response
        """
        results: Dict[str, Dict[str, Any]] = {}
        for line in parse_stream(response):
            try:
                item = json.loads(line)
                if streaming:
                    yield item
                self.handle_stream_metadata(item)
                for n, choice in enumerate(item['choices']):
                    if not results.get(n):
                        results[n] = {
                            'index': choice['index'],
                            'message': {
                                'role': choice['delta'].get('role', ''),
                                'content': choice['delta'].get('content', ''),
                            }
                        }
                        if 'function_call' in choice['delta']:
                            results[n]['message']['function_call'] = choice['delta']['function_call']
                            self.usage.completion_tokens += 4
                        
                        # every message follows <im_start>{role/name}\n{content}<im_end>\n
                        self.usage.completion_tokens += 4

                    elif choice['finish_reason'] != 'stop':
                        for k,v in choice['delta'].items():
                            if k == 'function_call' and v:
                                for fck, fcv in v.items():
                                    if not results[n]['message'][k].get(fck):
                                        results[n]['message'][k][fck] = fcv
                                    else:
                                        results[n]['message'][k][fck] += fcv

                            elif v: results[n]['message'][k] += v
                            self.usage.completion_tokens += 1

                    else:
                        results[n]['finish_reason'] = choice['finish_reason']
                        self.usage.completion_tokens += 2  # every reply is primed with <im_start>assistant
                        compl = results.pop(n)
                        if streaming:
                            self.handle_resource_item(item = compl)
                        else:
                            yield compl

            except Exception as e:
                logger.error(f'Error: {line}: {e}')
        self._stream_consumed = True
        for remaining_result in results.values():
            if streaming:
                self.handle_resource_item(item = remaining_result)
            else:
                yield remaining_result
        if not self.usage.prompt_tokens:
            self.usage.prompt_tokens = ModelContextHandler.count_chat_tokens(
                messages = self.input_messages,
                model_name = self.openai_model
            )
        self.usage.total_tokens = self.usage.completion_tokens + self.usage.prompt_tokens
        
    
    async def ahandle_stream(
        self,
        response: aiohttpx.Response,
        streaming: Optional[bool] = False,
    ) -> AsyncIterator[Dict]:  # sourcery skip: low-code-quality
        """
        Handles the streaming response
        """
        results: Dict[str, Dict[str, Any]] = {}
        async for line in aparse_stream(response):
            # logger.info(f'line: {line}')
            try:
                item = json.loads(line)
                self.handle_stream_metadata(item)
                if streaming:
                    yield item

                # logger.info(f'item: {item}')
                for n, choice in enumerate(item['choices']):
                    if not results.get(n):
                        results[n] = {
                            'index': choice['index'],
                            'message': {
                                'role': choice['delta'].get('role', ''),
                                'content': choice['delta'].get('content', ''),
                            }
                        }
                        if 'function_call' in choice['delta']:
                            results[n]['message']['function_call'] = choice['delta']['function_call']
                            self.usage.completion_tokens += 4
                        
                        # every message follows <im_start>{role/name}\n{content}<im_end>\n
                        self.usage.completion_tokens += 4

                    elif choice['finish_reason'] != 'stop':
                        for k,v in choice['delta'].items():
                            if k == 'function_call' and v:
                                for fck, fcv in v.items():
                                    if not results[n]['message'][k].get(fck):
                                        results[n]['message'][k][fck] = fcv
                                    else:
                                        results[n]['message'][k][fck] += fcv
                            elif v: results[n]['message'][k] += v
                            self.usage.completion_tokens += 1

                    else:
                        results[n]['finish_reason'] = choice['finish_reason']
                        self.usage.completion_tokens += 2  # every reply is primed with <im_start>assistant
                        compl = results.pop(n)
                        if streaming:
                            self.handle_resource_item(item = compl)
                        else:
                            yield compl


            except Exception as e:
                logger.trace(f'Error: {line}', e)
        # self.ctx.stream_consumed = True
        self._stream_consumed = True
        for remaining_result in results.values():
            if streaming:
                self.handle_resource_item(item = remaining_result)
            else:
                yield remaining_result
        
        if not self.usage.prompt_tokens:
            self.usage.prompt_tokens = ModelContextHandler.count_chat_tokens(
                messages = self.input_messages,
                model_name = self.openai_model
            )
        self.usage.total_tokens = self.usage.completion_tokens + self.usage.prompt_tokens

    if TYPE_CHECKING:
        def stream(self, **kwargs) -> Generator[StreamedChatMessage, None, None]:
            """
            Streams the response
            """
            ...

        async def astream(self, **kwargs) -> AsyncGenerator[StreamedChatMessage, None]:
            """
            Streams the response
            """
            ...
    


class ChatRoute(BaseRoute):
    input_model: Optional[Type[BaseResource]] = ChatObject
    response_model: Optional[Type[BaseResource]] = ChatResponse
    api_resource: Optional[str] = Field(default = 'chat/completions')
    root_name: Optional[str] = Field(default = 'chat')

    def get_serialization_kwargs(
        self,
        data: 'ChatObject',
    ) -> Dict[str, Any]:
        """
        Returns the serialization kwargs
        """
        opts = {
            'exclude_none': self.exclude_null,
        }
        if data.json_schema: 
            opts['by_alias'] = True
            opts['exclude'] = {'json_schema'}
        return opts


    @overload
    def create(
        self,
        messages: Union[List[ChatMessage], List[Dict[str, str]]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = None,
        stream: Optional[bool] = None,
        logprobs: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        user: Optional[str] = None,
    ) -> ChatResponse:
        """
        Creates a chat response for the provided prompt and parameters

        Usage:

        ```python
        >>> result = OpenAI.chat.create(
        >>>    messages = [{'content': 'say this is a test'}],
        >>>    max_tokens = 4,
        >>>    stream = True
        >>> )
        ```

        **Parameters:**

        :model (required): ID of the model to use. You can use the List models API 
        to see all of your available models,  or see our Model overview for descriptions of them.
        Default: `gpt-3.5-turbo`
        
        :messages: The messages to generate chat completions for, in the chat format.

        :max_tokens (optional): The maximum number of tokens to generate in the completion.
        The token count of your prompt plus `max_tokens` cannot exceed the model's context length. 
        Most models have a context length of 2048 tokens (except for the newest models, which 
        support 4096 / 8182 / 32,768). If max_tokens is not provided, the model will use the maximum number of tokens
        Default: None

        :temperature (optional): What sampling temperature to use. Higher values means 
        the model will take more risks. Try 0.9 for more creative applications, and 0 (argmax sampling) 
        for ones with a well-defined answer. We generally recommend altering this or `top_p` but not both.
        Default: `1.0`

        :top_p (optional): An alternative to sampling with `temperature`, called nucleus 
        sampling, where the model considers the results of the tokens with `top_p` probability mass. 
        So `0.1` means only  the tokens comprising the top 10% probability mass are considered.
        We generally recommend altering this or `temperature` but not both
        Default: `1.0`

        :n (optional): How many completions to generate for each prompt.
        Note: Because this parameter generates many completions, it can quickly 
        consume your token quota. Use carefully and ensure that you have reasonable 
        settings for `max_tokens` and stop.
        Default: `1`

        :stream (optional): CURRENTLY NOT SUPPORTED
        Whether to stream back partial progress. 
        If set, tokens will be sent as data-only server-sent events as they become 
        available, with the stream terminated by a `data: [DONE]` message. This is 
        handled automatically by the Client and enables faster response processing.
        Default: `False`

        :logprobs (optional): Include the log probabilities on the `logprobs` 
        most likely tokens, as well the chosen tokens. For example, if `logprobs` is 5, 
        the API will return a list of the 5 most likely tokens. The API will always 
        return the logprob of the sampled token, so there may be up to `logprobs+1` 
        elements in the response. The maximum value for `logprobs` is 5.
        Default: `None`

        :stop (optional): Up to 4 sequences where the API will stop generating 
        further tokens. The returned text will not contain the stop sequence.
        Default: `None`

        :presence_penalty (optional): Number between `-2.0` and `2.0`. Positive values 
        penalize new tokens based on whether they appear in the text so far, increasing the 
        model's likelihood to talk about new topics
        Default: `0.0`

        :frequency_penalty (optional): Number between `-2.0` and `2.0`. Positive 
        values penalize new tokens based on their existing frequency in the text so 
        far, decreasing the model's likelihood to repeat the same line verbatim.
        Default: `0.0`

        :logit_bias (optional): Modify the likelihood of specified tokens appearing in the completion.
        Accepts a json object that maps tokens (specified by their token ID in the GPT tokenizer) to an associated 
        bias value from -100 to 100. You can use this tokenizer tool (which works for both GPT-2 and GPT-3) to 
        convert text to token IDs. Mathematically, the bias is added to the logits generated by the model prior 
        to sampling. The exact effect will vary per model, but values between -1 and 1 should decrease or increase 
        likelihood of selection; values like -100 or 100 should result in a ban or exclusive selection of the 
        relevant token.
        As an example, you can pass `{"50256": -100}` to prevent the `<|endoftext|>` token from being generated.
        Default: `None`
        
        Returns a ChatResponse
        """
        ...
    
    @overload
    def create(
        self,
        messages: Union[List[ChatMessage], List[Dict[str, str]]],
        model: Optional[str] = None,
        functions: Optional[List[Function]] = None,
        function_call: Optional[Union[str, Dict[str, str]]] = None,
        response_format: Optional[Dict[str, Literal['json_object', 'text']]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        header_cache_keys: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Creates a chat response for the provided prompt and parameters

        Usage:

        ```python
        >>> result = OpenAI.chat.create(
        >>>    messages = [{'content': 'say this is a test'}],
        >>>    max_tokens = 4,
        >>>    functions = [{'name': 'test', 'parameters': {'test': 'test'}}],
        >>>    function_call = 'auto'
        >>> )
        ```
        **Parameters:**

        :model (required): ID of the model to use. You can use the List models API
        to see all of your available models,  or see our Model overview for descriptions of them.
        Default: `gpt-3.5-turbo`

        :messages: The messages to generate chat completions for, in the chat format.

        :max_tokens (optional): The maximum number of tokens to generate in the completion.

        :temperature (optional): What sampling temperature to use. Higher values means

        :functions (optional): A list of dictionaries representing the functions to call

        :function_call (optional): The name of the function to call

        :auto_retry (optional): Whether to automatically retry the request if it fails

        :auto_retry_limit (optional): The maximum number of times to retry the request

        :header_cache_keys (optional): A list of keys to use for caching the headers

        Returns a ChatResponse
        """
        ...
        

    def create(
        self, 
        input_object: Optional[ChatObject] = None,
        parse_stream: Optional[bool] = True,
        timeout: Optional[int] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        header_cache_keys: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResponse:  # sourcery skip: low-code-quality
        """
        Creates a chat response for the provided prompt and parameters

        Usage:

        ```python
        >>> result = OpenAI.chat.create(
        >>>    messages = [{'content': 'say this is a test'}],
        >>>    max_tokens = 4,
        >>>    stream = True
        >>> )
        ```

        **Parameters:**

        :model (required): ID of the model to use. You can use the List models API 
        to see all of your available models,  or see our Model overview for descriptions of them.
        Default: `gpt-3.5-turbo`
        
        :messages: The messages to generate chat completions for, in the chat format.

        :max_tokens (optional): The maximum number of tokens to generate in the completion.
        The token count of your prompt plus `max_tokens` cannot exceed the model's context length. 
        Most models have a context length of 2048 tokens (except for the newest models, which 
        support 4096 / 8182 / 32,768). If max_tokens is not provided, the model will use the maximum number of tokens
        Default: None

        :temperature (optional): What sampling temperature to use. Higher values means 
        the model will take more risks. Try 0.9 for more creative applications, and 0 (argmax sampling) 
        for ones with a well-defined answer. We generally recommend altering this or `top_p` but not both.
        Default: `1.0`

        :top_p (optional): An alternative to sampling with `temperature`, called nucleus 
        sampling, where the model considers the results of the tokens with `top_p` probability mass. 
        So `0.1` means only  the tokens comprising the top 10% probability mass are considered.
        We generally recommend altering this or `temperature` but not both
        Default: `1.0`

        :n (optional): How many completions to generate for each prompt.
        Note: Because this parameter generates many completions, it can quickly 
        consume your token quota. Use carefully and ensure that you have reasonable 
        settings for `max_tokens` and stop.
        Default: `1`

        :stream (optional):
        Whether to stream back partial progress. 
        If set, tokens will be sent as data-only server-sent events as they become 
        available, with the stream terminated by a `data: [DONE]` message. This is 
        handled automatically by the Client and enables faster response processing.
        Default: `False`

        :logprobs (optional): Include the log probabilities on the `logprobs` 
        most likely tokens, as well the chosen tokens. For example, if `logprobs` is 5, 
        the API will return a list of the 5 most likely tokens. The API will always 
        return the logprob of the sampled token, so there may be up to `logprobs+1` 
        elements in the response. The maximum value for `logprobs` is 5.
        Default: `None`

        :stop (optional): Up to 4 sequences where the API will stop generating 
        further tokens. The returned text will not contain the stop sequence.
        Default: `None`

        :presence_penalty (optional): Number between `-2.0` and `2.0`. Positive values 
        penalize new tokens based on whether they appear in the text so far, increasing the 
        model's likelihood to talk about new topics
        Default: `0.0`

        :frequency_penalty (optional): Number between `-2.0` and `2.0`. Positive 
        values penalize new tokens based on their existing frequency in the text so 
        far, decreasing the model's likelihood to repeat the same line verbatim.
        Default: `0.0`

        :logit_bias (optional): Modify the likelihood of specified tokens appearing in the completion.
        Accepts a json object that maps tokens (specified by their token ID in the GPT tokenizer) to an associated 
        bias value from -100 to 100. You can use this tokenizer tool (which works for both GPT-2 and GPT-3) to 
        convert text to token IDs. Mathematically, the bias is added to the logits generated by the model prior 
        to sampling. The exact effect will vary per model, but values between -1 and 1 should decrease or increase 
        likelihood of selection; values like -100 or 100 should result in a ban or exclusive selection of the 
        relevant token.
        As an example, you can pass `{"50256": -100}` to prevent the `<|endoftext|>` token from being generated.
        Default: `None`

        :user (optional): A unique identifier representing your end-user, which can help OpenAI to 
        monitor and detect abuse.
        Default: `None`

        :functions (optional): A list of dictionaries representing the functions to call
        
        :function_call (optional): The name of the function to call. Default: `auto` if functions are provided

        :response_format (optional): The format of the response. Default: `text`

        :seed (optional): An integer seed for random sampling. Must be between 0 and 2**32 - 1

        :tools (optional): A list of dictionaries representing the tools to use

        :tool_choice (optional): The name of the tool to use. Default: `auto` if tools are provided

        :auto_retry (optional): Whether to automatically retry the request if it fails due to a rate limit error.

        :auto_retry_limit (optional): The maximum number of times to retry the request if it fails due to a rate limit error.

        Returns: `ChatResponse`
        """
        return super().create(
            input_object = input_object,
            parse_stream = parse_stream,
            timeout = timeout,
            auto_retry = auto_retry,
            auto_retry_limit = auto_retry_limit,
            header_cache_keys = header_cache_keys,
            **kwargs
        )


    @overload
    async def async_create(
        self,
        messages: Union[List[ChatMessage], List[Dict[str, str]]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = None,
        stream: Optional[bool] = None,
        logprobs: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        user: Optional[str] = None,
    ) -> ChatResponse:
        """
        Creates a chat response for the provided prompt and parameters

        Usage:

        ```python
        >>> result = await OpenAI.chat.async_create(
        >>>    messages = [{'content': 'say this is a test'}],
        >>>    max_tokens = 4,
        >>>    stream = True
        >>> )
        ```

        **Parameters:**

        :model (required): ID of the model to use. You can use the List models API 
        to see all of your available models,  or see our Model overview for descriptions of them.
        Default: `gpt-3.5-turbo`
        
        :messages: The messages to generate chat completions for, in the chat format.

        :max_tokens (optional): The maximum number of tokens to generate in the completion.
        The token count of your prompt plus `max_tokens` cannot exceed the model's context length. 
        Most models have a context length of 2048 tokens (except for the newest models, which 
        support 4096 / 8182 / 32,768). If max_tokens is not provided, the model will use the maximum number of tokens
        Default: None

        :temperature (optional): What sampling temperature to use. Higher values means 
        the model will take more risks. Try 0.9 for more creative applications, and 0 (argmax sampling) 
        for ones with a well-defined answer. We generally recommend altering this or `top_p` but not both.
        Default: `1.0`

        :top_p (optional): An alternative to sampling with `temperature`, called nucleus 
        sampling, where the model considers the results of the tokens with `top_p` probability mass. 
        So `0.1` means only  the tokens comprising the top 10% probability mass are considered.
        We generally recommend altering this or `temperature` but not both
        Default: `1.0`

        :n (optional): How many completions to generate for each prompt.
        Note: Because this parameter generates many completions, it can quickly 
        consume your token quota. Use carefully and ensure that you have reasonable 
        settings for `max_tokens` and stop.
        Default: `1`

        :stream (optional):
        Whether to stream back partial progress. 
        If set, tokens will be sent as data-only server-sent events as they become 
        available, with the stream terminated by a `data: [DONE]` message. This is 
        handled automatically by the Client and enables faster response processing.
        Default: `False`

        :logprobs (optional): Include the log probabilities on the `logprobs` 
        most likely tokens, as well the chosen tokens. For example, if `logprobs` is 5, 
        the API will return a list of the 5 most likely tokens. The API will always 
        return the logprob of the sampled token, so there may be up to `logprobs+1` 
        elements in the response. The maximum value for `logprobs` is 5.
        Default: `None`

        :stop (optional): Up to 4 sequences where the API will stop generating 
        further tokens. The returned text will not contain the stop sequence.
        Default: `None`

        :presence_penalty (optional): Number between `-2.0` and `2.0`. Positive values 
        penalize new tokens based on whether they appear in the text so far, increasing the 
        model's likelihood to talk about new topics
        Default: `0.0`

        :frequency_penalty (optional): Number between `-2.0` and `2.0`. Positive 
        values penalize new tokens based on their existing frequency in the text so 
        far, decreasing the model's likelihood to repeat the same line verbatim.
        Default: `0.0`

        :logit_bias (optional): Modify the likelihood of specified tokens appearing in the completion.
        Accepts a json object that maps tokens (specified by their token ID in the GPT tokenizer) to an associated 
        bias value from -100 to 100. You can use this tokenizer tool (which works for both GPT-2 and GPT-3) to 
        convert text to token IDs. Mathematically, the bias is added to the logits generated by the model prior 
        to sampling. The exact effect will vary per model, but values between -1 and 1 should decrease or increase 
        likelihood of selection; values like -100 or 100 should result in a ban or exclusive selection of the 
        relevant token.
        As an example, you can pass `{"50256": -100}` to prevent the `<|endoftext|>` token from being generated.
        Default: `None`
        
        Returns a ChatResponse
        """
        ...
    
    @overload
    async def async_create(
        self,
        messages: Union[List[ChatMessage], List[Dict[str, str]]],
        model: Optional[str] = None,
        functions: Optional[List[Function]] = None,
        function_call: Optional[Union[str, Dict[str, str]]] = None,
        response_format: Optional[Dict[str, Literal['json_object', 'text']]] = None,
        json_schema: Optional[Union[JSONSchema, Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        header_cache_keys: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Creates a chat response for the provided prompt and parameters

        Usage:

        ```python
        >>> result = await OpenAI.chat.async_create(
        >>>    messages = [{'content': 'say this is a test'}],
        >>>    max_tokens = 4,
        >>>    functions = [{'name': 'test', 'parameters': {'test': 'test'}}],
        >>>    function_call = 'auto'
        >>> )
        ```
        **Parameters:**

        :model (required): ID of the model to use. You can use the List models API
        to see all of your available models,  or see our Model overview for descriptions of them.
        Default: `gpt-3.5-turbo`

        :messages: The messages to generate chat completions for, in the chat format.

        :max_tokens (optional): The maximum number of tokens to generate in the completion.

        :temperature (optional): What sampling temperature to use. Higher values means

        :functions (optional): A list of dictionaries representing the functions to call

        :function_call (optional): The name of the function to call

        :auto_retry (optional): Whether to automatically retry the request if it fails

        :auto_retry_limit (optional): The maximum number of times to retry the request

        :header_cache_keys (optional): A list of keys to use for caching the headers

        Returns a ChatResponse
        """
        ...

    async def async_create(
        self, 
        input_object: Optional[ChatObject] = None,
        parse_stream: Optional[bool] = True,
        timeout: Optional[int] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        header_cache_keys: Optional[List[str]] = None,
        **kwargs
    ) -> ChatResponse:  # sourcery skip: low-code-quality
        """
        Creates a chat response for the provided prompt and parameters

        Usage:

        ```python
        >>> result = await OpenAI.chat.async_create(
        >>>    messages = [{'content': 'say this is a test'}],
        >>>    max_tokens = 4,
        >>>    stream = True
        >>> )
        ```

        **Parameters:**

        :model (required): ID of the model to use. You can use the List models API 
        to see all of your available models,  or see our Model overview for descriptions of them.
        Default: `gpt-3.5-turbo`
        
        :messages: The messages to generate chat completions for, in the chat format.

        :max_tokens (optional): The maximum number of tokens to generate in the completion.
        The token count of your prompt plus `max_tokens` cannot exceed the model's context length. 
        Most models have a context length of 2048 tokens (except for the newest models, which 
        support 4096).
        Default: `16`

        :temperature (optional): What sampling temperature to use. Higher values means 
        the model will take more risks. Try 0.9 for more creative applications, and 0 (argmax sampling) 
        for ones with a well-defined answer. We generally recommend altering this or `top_p` but not both.
        Default: `1.0`

        :top_p (optional): An alternative to sampling with `temperature`, called nucleus 
        sampling, where the model considers the results of the tokens with `top_p` probability mass. 
        So `0.1` means only  the tokens comprising the top 10% probability mass are considered.
        We generally recommend altering this or `temperature` but not both
        Default: `1.0`

        :n (optional): How many completions to generate for each prompt.
        Note: Because this parameter generates many completions, it can quickly 
        consume your token quota. Use carefully and ensure that you have reasonable 
        settings for `max_tokens` and stop.
        Default: `1`

        :stream (optional):
        Whether to stream back partial progress. 
        If set, tokens will be sent as data-only server-sent events as they become 
        available, with the stream terminated by a `data: [DONE]` message. This is 
        handled automatically by the Client and enables faster response processing.
        Default: `False`

        :logprobs (optional): Include the log probabilities on the `logprobs` 
        most likely tokens, as well the chosen tokens. For example, if `logprobs` is 5, 
        the API will return a list of the 5 most likely tokens. The API will always 
        return the logprob of the sampled token, so there may be up to `logprobs+1` 
        elements in the response. The maximum value for `logprobs` is 5.
        Default: `None`

        :stop (optional): Up to 4 sequences where the API will stop generating 
        further tokens. The returned text will not contain the stop sequence.
        Default: `None`

        :presence_penalty (optional): Number between `-2.0` and `2.0`. Positive values 
        penalize new tokens based on whether they appear in the text so far, increasing the 
        model's likelihood to talk about new topics
        Default: `0.0`

        :frequency_penalty (optional): Number between `-2.0` and `2.0`. Positive 
        values penalize new tokens based on their existing frequency in the text so 
        far, decreasing the model's likelihood to repeat the same line verbatim.
        Default: `0.0`

        :logit_bias (optional): Modify the likelihood of specified tokens appearing in the completion.
        Accepts a json object that maps tokens (specified by their token ID in the GPT tokenizer) to an associated 
        bias value from -100 to 100. You can use this tokenizer tool (which works for both GPT-2 and GPT-3) to 
        convert text to token IDs. Mathematically, the bias is added to the logits generated by the model prior 
        to sampling. The exact effect will vary per model, but values between -1 and 1 should decrease or increase 
        likelihood of selection; values like -100 or 100 should result in a ban or exclusive selection of the 
        relevant token.
        As an example, you can pass `{"50256": -100}` to prevent the `<|endoftext|>` token from being generated.
        Default: `None`

        :user (optional): A unique identifier representing your end-user, which can help OpenAI to 
        monitor and detect abuse.

        :functions (optional): A list of dictionaries representing the functions to call
        
        :function_call (optional): The name of the function to call. Default: `auto` if functions are provided

        :response_format (optional): The format of the response. Default: `text`

        :seed (optional): An integer seed for random sampling. Must be between 0 and 2**32 - 1

        :tools (optional): A list of dictionaries representing the tools to use

        :tool_choice (optional): The name of the tool to use. Default: `auto` if tools are provided

        :auto_retry (optional): Whether to automatically retry the request if it fails due to a rate limit error.

        :auto_retry_limit (optional): The maximum number of times to retry the request if it fails due to a rate limit error.

        Default: `None`

        Returns: `ChatResponse`
        """
        return await super().async_create(
            input_object = input_object,
            parse_stream = parse_stream,
            timeout = timeout,
            auto_retry = auto_retry,
            auto_retry_limit = auto_retry_limit,
            header_cache_keys = header_cache_keys,
            **kwargs
        )

    

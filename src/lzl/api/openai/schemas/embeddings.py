from __future__ import annotations

import time
import asyncio
import contextlib
from typing import Optional, Type, Any, Union, List, Dict, overload
from lzo.types import (
    eproperty, 
    validator, 
    root_validator, 
    field_validator,
    Field,
    PYDANTIC_VERSION, 
)
from lzl.api.openai.version import DEFAULT_EMBEDDING_MODEL
from lzl.api.openai.types.handlers import ModelContextHandler
from lzl.api.openai.types.base import BaseResource
from lzl.api.openai.types.responses import BaseResponse
from lzl.api.openai.types.routes import BaseRoute
from lzl.api.openai.utils import logger

__all__ = [
    'EmbeddingData',
    'EmbeddingObject',
    'EmbeddingResponse',
    'EmbeddingRoute',
]



class EmbeddingData(BaseResource):
    object: Optional[str] = 'embedding'
    embedding: Optional[List[float]] = []
    index: Optional[int] = 0

class EmbeddingObject(BaseResource):
    model: Optional[str] = DEFAULT_EMBEDDING_MODEL
    input: Optional[Union[List[Any], Any]] = None
    user: Optional[str] = None
    dimensions: Optional[int] = None
    encoding_format: Optional[str] = None


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
    

    def dict(self, *args, exclude: Any = None, exclude_unset: bool = True, **kwargs):
        """
        Returns the dict representation of the response
        """
        return super().dict(*args, exclude = exclude, exclude_unset = exclude_unset, **kwargs)
    


class EmbeddingResponse(BaseResponse):
    data: Optional[List[EmbeddingData]] = None
    data_model: Optional[Type[BaseResource]] = EmbeddingData
    input_object: Optional[EmbeddingObject] = None

    @eproperty
    def embeddings(self) -> List[List[float]]:
        """
        Returns the text for the response
        object
        """
        if self.data:
            return [data.embedding for data in self.data] if self.data else []
        return None

    @eproperty
    def openai_model(self):
        """
        Returns the model for the completions
        """
        return self.headers.get('openai-model', self.input_object.model)

    @eproperty
    def consumption(self) -> int:
        """
        Returns the consumption for the completions
        """ 
        return ModelContextHandler.get_consumption_cost(
            model_name = self.openai_model,
            usage = self.usage,
        )



class EmbeddingRoute(BaseRoute):
    input_model: Optional[Type[BaseResource]] = EmbeddingObject
    response_model: Optional[Type[BaseResource]] = EmbeddingResponse
    api_resource: Optional[str] = Field(default = 'embeddings')
    root_name: Optional[str] = Field(default = 'embedding')

    @overload
    def create(
        self, 
        input: Optional[Union[str, List[str], List[List]]] = None,
        model: Optional[str] = DEFAULT_EMBEDDING_MODEL,
        dimensions: Optional[int] = None,
        encoding_format: Optional[str] = 'float',
        user: Optional[str] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        **kwargs
    ) -> EmbeddingResponse:
        """
        Creates a embedding response for the provided prompt and parameters

        Usage:

        ```python
        >>> result = OpenAI.embedding.create(
        >>>    input = 'say this is a test',
        >>> )
        ```

        **Parameters:**

        :input (string, array, required): Input text to embed, encoded as a string or array of tokens. To embed multiple inputs in a single request, pass an array of strings or array of token arrays. Each input must not exceed the max input tokens for the model (8191 tokens for text-embedding-ada-002). Example Python code for counting tokens.

        :model (string, required): ID of the model to use. You can use the List models API to see all of your available models, or see our Model overview for descriptions of them.
        Default: `text-embedding-ada-002`

        :dimensions (optional): Number of dimensions to use for the embedding. If not specified, the model will use the default number of dimensions for the model. This is only supported in `text-embedding-3` and later models
        Default: `None`

        :encoding_format (optional): The format of the encoding. If not specified, the model will use the default encoding format for the model. Defaults to `float`
        Default: `float`

        :user (optional): A unique identifier representing your end-user, which can help OpenAI to 
        monitor and detect abuse.
        Default: `None`

        Returns: `EmbeddingResponse`
        """
        ...


    def create(
        self, 
        input_object: Optional[EmbeddingObject] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        **kwargs
    ) -> EmbeddingResponse:
        """
        Creates a embedding response for the provided prompt and parameters

        Usage:

        ```python
        >>> result = OpenAI.embedding.create(
        >>>    input = 'say this is a test',
        >>> )
        ```

        **Parameters:**

        :input (string, array, required): Input text to embed, encoded as a string or array of tokens. To embed multiple inputs in a single request, pass an array of strings or array of token arrays. Each input must not exceed the max input tokens for the model (8191 tokens for text-embedding-ada-002). Example Python code for counting tokens.

        :model (string, required): ID of the model to use. You can use the List models API to see all of your available models, or see our Model overview for descriptions of them.
        Default: `text-embedding-ada-002`

        :dimensions (optional): Number of dimensions to use for the embedding. If not specified, the model will use the default number of dimensions for the model. This is only supported in `text-embedding-3` and later models
        Default: `None`

        :encoding_format (optional): The format of the encoding. If not specified, the model will use the default encoding format for the model. Defaults to `float`
        Default: `float`

        :user (optional): A unique identifier representing your end-user, which can help OpenAI to 
        monitor and detect abuse.
        Default: `None`

        Returns: `EmbeddingResponse`
        """
        return super().create(
            input_object = input_object,
            auto_retry = auto_retry,
            auto_retry_limit = auto_retry_limit,
            **kwargs
        )

    @overload
    async def async_create(
        self, 
        input: Optional[Union[str, List[str], List[List]]] = None,
        model: Optional[str] = DEFAULT_EMBEDDING_MODEL,
        dimensions: Optional[int] = None,
        encoding_format: Optional[str] = 'float',
        user: Optional[str] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        **kwargs
    ) -> EmbeddingResponse:
        """
        Creates a embedding response for the provided prompt and parameters

        Usage:

        ```python
        >>> result = await OpenAI.embedding.async_create(
        >>>    input = 'say this is a test',
        >>> )
        ```

        **Parameters:**

        :input (string, array, required): Input text to embed, encoded as a string or array of tokens. To embed multiple inputs in a single request, pass an array of strings or array of token arrays. Each input must not exceed the max input tokens for the model (8191 tokens for text-embedding-ada-002). Example Python code for counting tokens.

        :model (string, required): ID of the model to use. You can use the List models API to see all of your available models, or see our Model overview for descriptions of them.
        Default: `text-embedding-ada-002`

        :dimensions (optional): Number of dimensions to use for the embedding. If not specified, the model will use the default number of dimensions for the model. This is only supported in `text-embedding-3` and later models
        Default: `None`

        :encoding_format (optional): The format of the encoding. If not specified, the model will use the default encoding format for the model. Defaults to `float`
        Default: `float`

        :user (optional): A unique identifier representing your end-user, which can help OpenAI to 
        monitor and detect abuse.
        Default: `None`

        Returns: `EmbeddingResponse`
        """
        ...


    async def async_create(
        self, 
        input_object: Optional[EmbeddingObject] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        **kwargs
    ) -> EmbeddingResponse:  # sourcery skip: low-code-quality
        """
        Usage:

        ```python
        >>> result = OpenAI.embedding.create(
        >>>    input = 'say this is a test',
        >>> )
        ```

        **Parameters:**

        :input (string, array, required): Input text to embed, encoded as a string or array of tokens. To embed multiple inputs in a single request, pass an array of strings or array of token arrays. Each input must not exceed the max input tokens for the model (8191 tokens for text-embedding-ada-002). Example Python code for counting tokens.

        :model (string): ID of the model to use. You can use the List models API to see all of your available models, or see our Model overview for descriptions of them.
        Default: `text-embedding-ada-002`

        :dimensions (optional): Number of dimensions to use for the embedding. If not specified, the model will use the default number of dimensions for the model. This is only supported in `text-embedding-3` and later models
        Default: `None`

        :encoding_format (optional): The format of the encoding. If not specified, the model will use the default encoding format for the model. Defaults to `float`
        Default: `float`

        :user (optional): A unique identifier representing your end-user, which can help OpenAI to 
        monitor and detect abuse.
        Default: `None`

        Returns: `EmbeddingResponse`
        """
        return await super().async_create(
            input_object = input_object,
            auto_retry = auto_retry,
            auto_retry_limit = auto_retry_limit,
            **kwargs
        )
        

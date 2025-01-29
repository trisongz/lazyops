from __future__ import annotations

"""
Reranking Router
"""

from typing import Optional, Type, Any, Union, List, Dict, overload
from lzo.types import (
    eproperty, 
    validator, 
    root_validator, 
    field_validator,
    Field,
    PYDANTIC_VERSION, 
)

from lzl.api.openai.types.handlers import ModelContextHandler
from lzl.api.openai.types.base import BaseResource
from lzl.api.openai.types.responses import BaseResponse
from lzl.api.openai.types.routes import BaseRoute
from lzl.api.openai.utils import logger

__all__ = [
    'RerankingData',
    'RerankingObject',
    'RerankingResponse',
    'RerankingRoute',
]

# Currently only voyager supports this.

class RerankingData(BaseResource):
    relevance_score: Optional[float] = None
    document: Optional[str] = None
    index: Optional[int] = 0

class RerankingObject(BaseResource):
    model: Optional[str] = None
    query: Optional[str] = None
    documents: Optional[List[Any]] = None
    top_k: Optional[int] = None
    # return_documents: Optional[bool] = Field(False, description = 'If false, the API will return a list of {"index", "relevance_score"} where "index" refers to the index of a document within the input list., If true, the API will return a list of {"index", "document", "relevance_score"} where "document" is the corresponding document from the input list.') 
    # truncation: Optional[bool] = Field(True, description = 'Whether to truncate the input text to the maximum context length')

    @field_validator('model', mode = 'before')
    def validate_model(cls, v, values: Dict[str, Any]) -> str:
        """
        Validate the model
        """
        if not v:
            if values.get('engine'): v = values.get('engine')
            elif values.get('deployment'): v = values.get('deployment')
        
        model = ModelContextHandler.get(v)
        if not model.data.get('supports_reranking') and 'rerankings' not in model.endpoints:
            raise ValueError(f"Model {model.name} does not support reranking")
        return model.name


    def dict(self, *args, exclude: Any = None, exclude_unset: bool = True, **kwargs):
        """
        Returns the dict representation of the response
        """
        return super().dict(*args, exclude = exclude, exclude_unset = exclude_unset, **kwargs)
    


class RerankingResponse(BaseResponse):
    data: Optional[List[RerankingData]] = None
    data_model: Optional[Type[BaseResource]] = RerankingData
    input_object: Optional[RerankingObject] = None

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



class RerankingRoute(BaseRoute):
    input_model: Optional[Type[BaseResource]] = RerankingObject
    response_model: Optional[Type[BaseResource]] = RerankingResponse
    api_resource: Optional[str] = Field(default = 'rerank')
    root_name: Optional[str] = Field(default = 'rerank')

    @eproperty
    def create_enabled(self):
        """
        Returns whether the Create Route is Enabled
        """
        # This is disabled by default
        return False

    @overload
    def create(
        self, 
        query: Optional[str] = None,
        documents: Optional[List[Any]] = None,
        top_k: Optional[int] = None,
        return_documents: Optional[bool] = False,
        truncation: Optional[bool] = True,
        model: Optional[str] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        **kwargs
    ) -> RerankingResponse:
        """
        Creates a reranking response for the provided query and documents

        Usage:

        ```python
        >>> result = OpenAI.reranking.create(
        >>>    query = 'say this is a test',
        >>>    documents = ['say this is a test', 'say this is another test'],
        >>> )
        ```

        **Parameters:**

        :query (string, required): The query to rerank
        :documents (list[string], required): The documents to rerank
        :top_k (int, optional): The number of documents to return
        :return_documents (bool, optional): If false, the API will return a list of {"index", "relevance_score"} where "index" refers to the index of a document within the input list., If true, the API will return a list of {"index", "document", "relevance_score"} where "document" is the corresponding document from the input list.
        :truncation (bool, optional): Whether to truncate the input text to the maximum context length
        :model (string, optional): ID of the model to use. You can use the List models API to see all of your available models, or see our Model overview for descriptions of them.

        Returns: `RerankingResponse`
        """
        ...


    def create(
        self, 
        input_object: Optional[RerankingObject] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        **kwargs
    ) -> RerankingResponse:
        """
        Creates a reranking response for the provided query and documents

        Usage:

        ```python
        >>> result = OpenAI.reranking.create(
        >>>    query = 'say this is a test',
        >>>    documents = ['say this is a test', 'say this is another test'],
        >>> )
        ```

        **Parameters:**

        :query (string, required): The query to rerank
        
        :documents (list[string], required): The documents to rerank
        
        :top_k (int, optional): The number of documents to return
        
        :return_documents (bool, optional): If false, the API will return a list of {"index", "relevance_score"} where "index" refers to the index of a document within the input list., If true, the API will return a list of {"index", "document", "relevance_score"} where "document" is the corresponding document from the input list.
        
        :truncation (bool, optional): Whether to truncate the input text to the maximum context length
        
        :model (string, optional): ID of the model to use. You can use the List models API to see all of your available models, or see our Model overview for descriptions of them.

        Returns: `RerankingResponse`
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
        query: Optional[str] = None,
        documents: Optional[List[Any]] = None,
        top_k: Optional[int] = None,
        return_documents: Optional[bool] = False,
        truncation: Optional[bool] = True,
        model: Optional[str] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        **kwargs
    ) -> RerankingResponse:
        """
        Creates a reranking response for the provided query and documents

        Usage:

        ```python
        >>> result = await OpenAI.reranking.async_create(
        >>>    query = 'say this is a test',
        >>>    documents = ['say this is a test', 'say this is another test'],
        >>> )
        ```

        **Parameters:**

        :query (string, required): The query to rerank
        
        :documents (list[string], required): The documents to rerank
        
        :top_k (int, optional): The number of documents to return
        
        :return_documents (bool, optional): If false, the API will return a list of {"index", "relevance_score"} where "index" refers to the index of a document within the input list., If true, the API will return a list of {"index", "document", "relevance_score"} where "document" is the corresponding document from the input list.
        
        :truncation (bool, optional): Whether to truncate the input text to the maximum context length
        
        :model (string, optional): ID of the model to use. You can use the List models API to see all of your available models, or see our Model overview for descriptions of them.

        Returns: `RerankingResponse`
        """
        ...


    async def async_create(
        self, 
        input_object: Optional[RerankingObject] = None,
        auto_retry: Optional[bool] = False,
        auto_retry_limit: Optional[int] = None,
        **kwargs
    ) -> RerankingResponse:  # sourcery skip: low-code-quality
        """
        Creates a reranking response for the provided query and documents

        Usage:

        ```python
        >>> result = await OpenAI.reranking.async_create(
        >>>    query = 'say this is a test',
        >>>    documents = ['say this is a test', 'say this is another test'],
        >>> )
        ```

        **Parameters:**

        :query (string, required): The query to rerank
        
        :documents (list[string], required): The documents to rerank
        
        :top_k (int, optional): The number of documents to return
        
        :return_documents (bool, optional): If false, the API will return a list of {"index", "relevance_score"} where "index" refers to the index of a document within the input list., If true, the API will return a list of {"index", "document", "relevance_score"} where "document" is the corresponding document from the input list.
        
        :truncation (bool, optional): Whether to truncate the input text to the maximum context length
        
        :model (string, optional): ID of the model to use. You can use the List models API to see all of your available models, or see our Model overview for descriptions of them.

        Returns: `RerankingResponse`
        """
        return await super().async_create(
            input_object = input_object,
            auto_retry = auto_retry,
            auto_retry_limit = auto_retry_limit,
            **kwargs
        )
        

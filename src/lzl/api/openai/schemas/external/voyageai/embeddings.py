from __future__ import annotations

"""
voyage.ai Embedding Route
"""


from ...embeddings import (
    EmbeddingRoute as BaseEmbeddingRoute,
    EmbeddingObject as BaseEmbeddingObject,
    EmbeddingResponse as BaseEmbeddingResponse,
    logger
)
from lzo.types import (
    validator, 
    model_validator,
    Field,
    eproperty
)
from lzl.api.openai.types.handlers import ModelContextHandler
from lzl.api.openai.types.base import Usage
from typing import Any, Dict, List, Optional, Union, Set, Type, TYPE_CHECKING

_allowed_dtypes = [
    'float', 'int8', 'uint8', 'binary', 'ubinary'
]

class EmbeddingObject(BaseEmbeddingObject):
    
    model: Optional[str] = "voyage-3-lite"
    truncation: Optional[bool] = Field(True, description = "Whether to truncate the input text to the maximum context length")
    output_dimension: Optional[int] = Field(None, description = "The output dimension of the embedding")
    output_dtype: Optional[str] = Field(None, description = "The output data type of the embedding")

    # Discarded Properties
    user: Optional[str] = Field(None, exclude = True, hidden = True)
    dimensions: Optional[int] = Field(None, exclude = True, hidden = True)

    @validator('model', pre=True, always=True)
    def validate_model(cls, v, values: Dict[str, Any]) -> str:
        """
        Validate the model
        """
        if not v:
            if values.get('engine'):
                v = values.get('engine')
            elif values.get('deployment'):
                v = values.get('deployment')
        v = ModelContextHandler.resolve_external_model_name(v)
        return v
    
    @model_validator(mode = 'after')
    def validate_embedding_object(self):
        """
        Validate the embedding object
        """
        if self.output_dimension is not None:
            c = ModelContextHandler.get_external_model(self.model)
            if c.data.get('dims') and self.output_dimension not in c.data['dims']:
                raise ValueError(f"Invalid Output Dimension: {self.output_dimension}. Must be one of {c.data['dims']}")
        if self.output_dtype is not None:
            if self.output_dtype not in _allowed_dtypes:
                raise ValueError(f"Invalid Output Data Type: {self.output_dtype}. Must be one of {_allowed_dtypes}")
        return self


class EmbeddingResponse(BaseEmbeddingResponse):

    usage: Optional[Usage] = Field(default_factory = Usage)


    @eproperty
    def consumption(self) -> int:
        """
        Returns the consumption for the completions
        """
        try:
            if not self.usage.prompt_tokens:
                self.usage.prompt_tokens = ModelContextHandler.count_tokens(self.input_object.input, model_name=self.input_object.model)
            return ModelContextHandler.get_consumption_cost(
                model_name = self.input_object.model,
                usage = self.usage,
            )
        except Exception as e:
            logger.error(f"Error getting consumption: {e}")
            return 0


class EmbeddingRoute(BaseEmbeddingRoute):
    input_model: Optional[Type[EmbeddingObject]] = EmbeddingObject
    response_model: Optional[Type[EmbeddingResponse]] = EmbeddingResponse
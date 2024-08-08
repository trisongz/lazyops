"""
Fork of `async_openai` to continue extending the library
"""

from typing import TYPE_CHECKING

from .assets import (
    load_provider_prices,
    load_preset_config,
)
from .configs import (
    OpenAISettings, 
    AzureOpenAISettings,
)

from .types import (
    Usage,
    OpenAIError,
    RateLimitError,
    MaxRetriesExhausted,
    MaxRetriesExceeded,
)

from .clients import (
    OpenAI,
    OpenAIClient,
    OpenAIManager,
    OpenAIFunctions,
    FunctionManager as OpenAIFunctionsManager,
)

if TYPE_CHECKING:
    from .schemas import (
        ChatMessage,
        ChatChoice,
        ChatResponse,
        ChatObject,

        CompletionChoice,
        CompletionObject,
        CompletionResponse,

        EmbeddingData,
        EmbeddingObject,
        EmbeddingResponse,

        BaseFunctionModel, 
        BaseFunction,
    )
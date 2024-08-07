from typing import Union, TypeVar, Any, TYPE_CHECKING


if TYPE_CHECKING:
    from .base import BaseGlobalClient
    from .http import BaseAPIClient, HTTPPoolClient
    from .browser import BrowserClient

    from ..sql.database.base import DatabaseClientBase

    from async_openai.manager import OpenAIManager
    from kvdb.tasks.base import BaseTaskWorker

    GlobalClientT = TypeVar('GlobalClientT', bound = BaseGlobalClient)
    APIClientT = TypeVar('APIClientT', bound = BaseAPIClient)

    GlobalClientType = Union[
        GlobalClientT,
        APIClientT,
        BrowserClient,
        OpenAIManager,
        HTTPPoolClient,
        DatabaseClientBase,
        Any
    ]
    
    LocalClientType = Union[
        BaseTaskWorker,
        Any
    ]
    ClientTypes = Union[
        GlobalClientType,
        LocalClientType,
    ]

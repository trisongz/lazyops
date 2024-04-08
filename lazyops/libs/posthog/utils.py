from __future__ import annotations

"""
Utilities
"""
import functools
from lazyops.libs.pooler import ThreadPooler
from lazyops.libs.logging import logger
from typing import Any, Dict, Optional, TypeVar, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import PostHogClient
    from .config import PostHogSettings


_ph_settings: Optional['PostHogSettings'] = None
_ph_client: Optional['PostHogClient'] = None

RT = TypeVar('RT')

def get_posthog_settings() -> 'PostHogSettings':
    """
    Returns the PostHog Settings
    """
    global _ph_settings
    if _ph_settings is None:
        from .config import PostHogSettings
        _ph_settings = PostHogSettings()
    return _ph_settings


def get_posthog_client(**kwargs) -> 'PostHogClient':
    """
    Returns the PostHog Client
    """
    global _ph_client
    if _ph_client is None:
        from .client import PostHogClient
        _ph_client = PostHogClient(**kwargs)
    elif kwargs: _ph_client.configure(**kwargs)
    return _ph_client

def register_posthog_client(client: 'PostHogClient', **kwargs):
    """
    Registers the PostHog Client
    """
    global _ph_client
    if _ph_client is None: _ph_client = client


def has_existing_posthog_client() -> bool:
    """
    Checks if there is an existing PostHog Client
    """
    global _ph_client
    return _ph_client is not None

"""
Basic Idea

@capture(event = 'test_event')
async def my_test_event(*args, ph_ctx: Dict[str, Any], **kwargs):

    # This will be passed to the function itself, which can be mutated
    # and will be sent to the Client after the function is called

    # ph_ctx = {'event': 'test_event', 'distinct_id': None, 'properties': {}}
    
    # Mutate the ph_ctx
    # ph_ctx['properties']['test'] = 'test'
    # ph_ctx['distinct_id'] = 'xxx'
    
    return 'test'

"""


def capture(
    event: Optional[str] = None,
    distinct_id: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
    **_kwargs: Any, 
) -> Callable[..., RT]:
    """
    Creates a decorator that can be used to capture events
    """
    def decorator(func: Callable[..., RT]) -> Callable[..., RT]:
        nonlocal event, distinct_id, properties

        client = _ph_client
        if client is None:
            ph_settings = get_posthog_settings()
            if ph_settings.is_enabled: client = get_posthog_client()
        if client is not None: 
            logger.info('Using Client for Capture')
            return client.capture(event = event, distinct_id = distinct_id, properties = properties, **_kwargs)(func)
        
        # Here we implement a deferred decorator
        if event is None: event = func.__name__
        properties = properties or {}
        ph_ctx = {'event': event, 'distinct_id': distinct_id, 'properties': properties, **_kwargs}
        logger.info('Using Deferred Capture')

        def _get_ph():
            """
            Gets the PostHog Client
            """
            nonlocal client
            if client is None: client = get_posthog_client()
            return client

        if ThreadPooler.is_coro(func):
            @functools.wraps(func)
            async def capture_decorator(*args, **kwargs):
                result = await func(*args, ph_ctx = ph_ctx, **kwargs)
                _get_ph().add_event(**ph_ctx)
                return result
        else:
            @functools.wraps(func)
            def capture_decorator(*args, **kwargs):
                result = func(*args, ph_ctx = ph_ctx, **kwargs)
                _get_ph().add_event(**ph_ctx)
                return result
        return capture_decorator
    return decorator
        
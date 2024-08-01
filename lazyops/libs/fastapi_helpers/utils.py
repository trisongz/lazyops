from __future__ import annotations

"""
FastAPI Helpers
"""

from typing import Optional, List, Dict, Any, Union, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request


def get_app_endpoint(
    request: 'Request',
    valid_domains: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Returns the app endpoint
    """
    if valid_domains and not any(
        domain in request.url.hostname for 
        domain in valid_domains
    ): 
        return None
    scheme = 'https' if request.url.port == 443 else request.url.scheme
    endpoint = f'{scheme}://{request.url.hostname}'
    if request.url.port and request.url.port not in {80, 443}:
        endpoint += f':{request.url.port}'
    return endpoint


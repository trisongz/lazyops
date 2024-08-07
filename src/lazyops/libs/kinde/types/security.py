from __future__ import annotations

"""
Kinde Security Types
"""

from fastapi import Security
from fastapi.security.http import HTTPBase
from fastapi.openapi.models import APIKey as _APIKey, APIKeyIn
from fastapi.security.api_key import APIKeyHeader as BaseAPIKeyHeader
from fastapi.security.http import HTTPAuthorizationCredentials
from typing import Optional, Annotated
from ..utils import get_kinde_settings


class APIKeyHeader(BaseAPIKeyHeader):
    """
    API Key Header
    """
    # We defer the fetching of the `name` attribute until the first time it is accessed.
    def __init__(
        self,
        *,
        scheme_name: Optional[str] = None,
        description: Optional[str] = None,
        auto_error: bool = True,
    ):
        self._model: Optional['_APIKey'] = None
        self.description = description
        self.scheme_name = scheme_name or self.__class__.__name__
        self.auto_error = auto_error

    @property
    def model(self) -> '_APIKey':
        """
        Returns the API Key Model
        """
        if self._model is None:
            self._model = _APIKey(
                **{"in": APIKeyIn.header},  # type: ignore[arg-type]
                name = get_kinde_settings().api_key_header,
                description = self.description,
            )
        return self._model

APIKeyScheme = APIKeyHeader(
    scheme_name = "API Key",
    description = "API Key Authentication",
    auto_error = False,
)

AuthorizationScheme = HTTPBase(
    scheme = "bearer",
    scheme_name = "Authorization",
    description = "Bearer Token Authentication",
    auto_error = False,
)

APIKey = Annotated[Optional[str], Security(APIKeyScheme)]
Authorization = Annotated[Optional[HTTPAuthorizationCredentials], Security(AuthorizationScheme)] 

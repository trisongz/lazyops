from __future__ import annotations

from fastapi import Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.security.http import HTTPBase, HTTPAuthorizationCredentials
from typing import Optional, Annotated


AuthorizationScheme = HTTPBase(
    scheme = "bearer",
    scheme_name = "Authorization",
    description = "Bearer Token Authentication",
    auto_error = False,
)

APIKeyScheme = APIKeyHeader(
    name = "x-api-key",
    scheme_name = "APIKey",
    description = "API Key Authentication",
    auto_error = False,
)
APIKey = Annotated[Optional[str], Security(APIKeyScheme)]
Authorization = Annotated[Optional[HTTPAuthorizationCredentials], Security(AuthorizationScheme)] 
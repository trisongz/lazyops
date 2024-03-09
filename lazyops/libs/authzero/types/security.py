from __future__ import annotations

"""
FastAPI Security Types for Auth0
"""

from typing import Optional, Annotated
from fastapi import Request, Security
from fastapi.security.api_key import  APIKeyQuery, APIKeyBase, APIKeyIn, APIKeyHeader
from fastapi.security.api_key import APIKey as BaseAPIKey
from fastapi.security.http import HTTPBase, HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPBearerModel, HTTPAuthorizationCredentials
from . import errors

APIKeyScheme = APIKeyHeader(
    name = "x-api-key",
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

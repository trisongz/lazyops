from __future__ import annotations

"""
Token Decoding Utilities
"""

from pydantic import ValidationError
from lazyops.libs import lazyload
from lazyops.libs.pooler import ThreadPooler
from .lazy import get_az_settings, get_az_resource
from typing import Any, Optional, List

if lazyload.TYPE_CHECKING:
    from fastapi import Request
    from fastapi.datastructures import Headers
    from ..configs import AuthZeroSettings
    from ..types.claims import UserJWTClaims


def decode_token(
    request: Optional['Request'] = None, 
    token: Optional[str] = None, 
    settings: Optional['AuthZeroSettings'] = None
) -> 'UserJWTClaims':
    """
    Attempts to decode the token from the request
    and allow for multi-audiences
    """
    from jose import jwt, JWTError
    assert request or token, 'Either a request or token must be provided'
    settings = settings or get_az_settings()
    token = token or get_auth_token(request.headers)
    err, jwt_claim = None, None
    audiences = settings.get_jwt_audiences()
    for aud in audiences:
        try:
            jwt_claim = jwt.decode(
                token = token,
                key = settings.jwks,
                algorithms = ['RS256'],
                audience = aud,
                issuer = settings.issuer,
            )
            # logger.info(f'Validated JWT Claim: {jwt_claim} against audience: {aud}')
            break
        except (JWTError, ValidationError) as e:
            err = e
    if jwt_claim is None:
        from ..types.errors import InvalidTokenException
        raise InvalidTokenException(error = e) from err
    return get_az_resource('user_jwt_claims', **jwt_claim)
    # return UserJWTClaims(**jwt_claim)

def decode_token_v1(
    request: Optional['Request'] = None, 
    token: Optional[str] = None, 
    settings: Optional['AuthZeroSettings'] = None
) -> 'UserJWTClaims':
    """
    Attempts to decode the token from the request
    """
    from jose import jwt, JWTError
    try:
        assert request or token, 'Either a request or token must be provided'
        settings = settings or get_az_settings()
        token = token or get_auth_token(request.headers)
        claims = UserJWTClaims(
            **jwt.decode(
                token = token,
                key=settings.jwks,
                algorithms = ['RS256'],
                audience = settings.audience,
                issuer = settings.issuer,
            )
        )
    except (JWTError, ValidationError) as e:
        from ..types.errors import InvalidTokenException
        raise InvalidTokenException(error = e) from e
    return claims



def get_auth_token(headers: 'Headers') -> str:
    """
    Gets the Auth Token from the Headers
    """
    settings = get_az_settings()
    authorization_header_value = headers.get(settings.authorization_header, headers.get(settings.authorization_header.capitalize()))
    if authorization_header_value:
        scheme, _, param = authorization_header_value.partition(" ")
        if scheme.lower() == settings.authorization_scheme:
            return param
    from ..types.errors import NoTokenException
    raise NoTokenException(detail = f'No Valid Authorization found on `{settings.authorization_header}')


def get_auth_token_v1(headers: 'Headers'):
    """
    Gets the Auth Token from the Headers
    """
    authorization_header_value = headers.get("Authorization")
    if authorization_header_value:
        scheme, _, param = authorization_header_value.partition(" ")
        if scheme.lower() == "bearer":
            return param
    from ..types.errors import NoTokenException
    raise NoTokenException(detail = 'Invalid Authorization Header')

"""
Google OAuth2 Provider
"""
from __future__ import annotations

from .config import GoogleOAuth2Config
from .client import GoogleOAuth2Client
from .token import (
    IDToken as GoogleIDToken,
    AccessToken as GoogleAccessToken,
    OAuth2Token as GoogleOAuth2Token,
)


from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    
    TokenT = Union[GoogleAccessToken, GoogleIDToken, GoogleOAuth2Token]
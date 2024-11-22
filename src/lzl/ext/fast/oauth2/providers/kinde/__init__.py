"""
Kinde OAuth2 Provider
"""
from __future__ import annotations

from .config import KindeOAuth2Config
from .client import KindeOAuth2Client
from .token import (
    IDToken as KindeIDToken,
    AccessToken as KindeAccessToken,
    OAuth2Token as KindeOAuth2Token,
)
from .types import UserInfo as KindeUserInfo

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    
    TokenT = Union[KindeAccessToken, KindeIDToken, KindeOAuth2Token]
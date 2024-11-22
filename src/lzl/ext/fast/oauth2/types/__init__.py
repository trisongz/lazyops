from __future__ import annotations

from typing import Union, Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request as BaseRequest
    from .user import OAuth2User
    from .token import OAuth2Token, AccessToken, IDToken


    class Request(BaseRequest):

        @property
        def auth(self) -> OAuth2Token:
            """
            Returns the OAuth2 Token
            """
            ...


        @property
        def user(self) -> OAuth2User:
            """
            Returns the OAuth2 User
            """
            ...




from __future__ import annotations

"""
OAuth2 Middleware

Unlike the OAuth Module, this has a few differences based on assumptions:

- If a user authenticates with the backend itself, it will generate an API Key 
  and store it in the session.

- Authenticating with the API Key assumes that the user has already authenticated via the backend.

- If Authentication is paseed as a header, it will assume that the user has already authenticated 
  via a 3rd party and will simply do a validation check of the Token.
"""


from .config import OAuth2Config
from .manager import OAuth2Manager
from .types.user import OAuth2User, UnauthenticatedUser, APIKeyUser
from .types.token import AccessToken, IDToken, OAuth2Token
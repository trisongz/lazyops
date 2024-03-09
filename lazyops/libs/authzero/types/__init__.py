from typing import TYPE_CHECKING, Union, Type

if TYPE_CHECKING:
    from .current_user import CurrentUser
    from .user_roles import UserRole
    from .user_data import AZUserData
    from .claims import UserJWTClaims, APIKeyJWTClaims
    from .auth import AuthObject, AuthZeroTokenAuth

    AZResource = Union[
        CurrentUser,
        UserRole,
        AZUserData,
        AuthObject,
        UserJWTClaims,
        APIKeyJWTClaims,
        AuthZeroTokenAuth,
    ]

    AZResourceSchema = Type[
        Union[
            CurrentUser,
            UserRole,
            AZUserData,
            AuthObject,
        ]
    ]

# from .auth import AuthObject
# from .access_tokens import AccessToken
# from .persistence import StatefulProperty
# from .tokens import Token, TokenPayload, UserJWTClaims
# from .user_data import UserExt

# from .errors import (
#     InvalidJWTException,
#     InvalidOperationException,
# )

# from .security import APIKey, Authorization
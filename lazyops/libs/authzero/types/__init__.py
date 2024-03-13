
from typing import TYPE_CHECKING, Union, Type

if TYPE_CHECKING:
    from .auth import AuthObject, AuthZeroTokenAuth, APIKeyData
    from .claims import UserJWTClaims, APIKeyJWTClaims
    from .current_user import CurrentUser
    from .user_data import AZUserData
    from .user_roles import UserRole
    from .user_session import UserSession
    
    AZResource = Union[
        APIKeyData,
        APIKeyJWTClaims,
        AuthObject,
        AuthZeroTokenAuth,
        AZUserData,
        CurrentUser,
        UserJWTClaims,
        UserSession,
    ]

    AZResourceSchema = Type[
        Union[
            APIKeyData,
            APIKeyJWTClaims,
            AuthObject,
            AuthZeroTokenAuth,
            AZUserData,
            CurrentUser,
            UserJWTClaims,
            UserSession,
        ]
    ]

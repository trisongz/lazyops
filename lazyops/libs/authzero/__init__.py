"""
AuthZero FastAPI Integration
"""

from .utils.lazy import (
    get_az_settings,
    get_az_flow_schema,
    get_az_resource_schema,
    get_az_resource,
    get_az_mtg_api,
)

from .configs import AuthZeroSettings, settings as az_settings
from .types.auth import AuthZeroTokenAuth
from .types.user_roles import UserRole
from .types.security import (
    Authorization,
    APIKey,
)
from .types import errors
from .clients import (
    AuthZeroOAuthClient,
    AuthZeroAPIClient,
    CurrentUser,
    OptionalUser, 
    ValidUser, 
    get_current_user, 
    require_auth_role,
    require_roles,
    require_api_key,
    require_api_key_or_user_role,

    auth_role_dependency,
    api_key_or_user_role_dependency,
)
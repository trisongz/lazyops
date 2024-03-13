from __future__ import annotations

"""
Auth Zero User Dependencies
"""

from fastapi import Depends, Request
from fastapi.background import BackgroundTasks
from lazyops.libs.fastapi_utils.utils import create_function_wrapper
from ..types import errors
from ..types.current_user import CurrentUser, UserRole
from ..types.security import Authorization, APIKey
from ..utils.lazy import logger

from typing import Optional, List, Annotated, Type, Union


def extract_current_user(
    *args,
    _is_optional: Optional[bool] = False,
    **kwargs,
) -> CurrentUser:
    """
    Extract The Current User from the Endpoint Function
    """
    user_kw = 'user' if 'user' in kwargs else 'current_user'
    current_user: CurrentUser = kwargs.get(user_kw, None)
    if current_user is None and not _is_optional:
        raise errors.NoUserException()
    return current_user


def require_auth_role(
    role: Union[UserRole, str, int],
    enabled: Optional[bool] = True,
    dry_run: Optional[bool] = False,
    is_optional: Optional[bool] = False,
    verbose: Optional[bool] = True,
):
    """
    Creates an auth role validator wrapper

    Usage:

    >>> @app.get('/admin')
    >>> @require_auth_role(UserRole.ADMIN)
    >>> async def admin(current_user: CurrentUser):
            return {'admin': True}

    """

    if isinstance(role, (str, int)): role = UserRole.parse_role(role)
    def validation_func(*args, **kwargs):
        """
        Validation Function
        """
        if not enabled: return
        current_user = extract_current_user(*args, _is_optional = is_optional, **kwargs)
        if current_user.role < role:
            if verbose: logger.info(f'User {current_user.user_id} has role {current_user.role} which is less than {role}')
            if dry_run: return
            raise errors.InvalidAuthRoleException(detail = f'User {current_user.user_id} has role {current_user.role} which is less than or equal to {role}')
        return
    return create_function_wrapper(validation_func)

def get_current_user(
    required: Optional[bool] = True,
    roles_enabled: Optional[bool] = False,
    required_roles: Optional[List[str]] = None,
    require_all_roles: Optional[bool] = False,
    # api_keys: Optional[List[str]] = None,
    user_class: Optional[Type[CurrentUser]] = None,
    **kwargs,
):
    """
    Returns the current user
    """
    user_class = user_class or CurrentUser

    async def inner(
        request: Request, 
        background_tasks: BackgroundTasks, 
        api_key: APIKey = None, 
        authorization: Authorization = None
    ) -> Optional[CurrentUser]:
        """
        The inner method
        """
        current_user = user_class(
            required = required,
            **kwargs
        )
        await current_user(request, background_tasks, api_key = api_key, authorization = authorization)
        if current_user.is_valid:
            if roles_enabled and required_roles:
                if not current_user.has_user_roles(required_roles, require_all = require_all_roles):
                    logger.warning(f'User {current_user.user_id} does not have required roles: {required_roles}')
                    raise errors.InvalidRolesException(required_roles, require_all = require_all_roles)
            return current_user
        return None
    return inner



OptionalUser = Annotated[Optional[CurrentUser], Depends(get_current_user(required = False))]
ValidUser = Annotated[CurrentUser, Depends(get_current_user())]

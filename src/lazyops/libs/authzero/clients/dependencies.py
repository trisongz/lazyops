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

def require_roles(
    roles: Union[str, List[str]],
    require_all: Optional[bool] = False,
    dry_run: Optional[bool] = False,
    verbose: Optional[bool] = True,
):
    """
    Creates a role validator wrapper
    """
    if not isinstance(roles, list): roles = [roles]
    def validation_func(*args, **kwargs):
        """
        Validation Function
        """        
        current_user = extract_current_user(*args, **kwargs)
        if not current_user.has_user_roles(roles, require_all = require_all):
            if verbose: logger.info(f'User {current_user.user_id} does not have required roles: {roles} / {current_user.role}')
            if dry_run:  return
            raise errors.InvalidRolesException(detail = f'User {current_user.user_id} does not have required roles: {roles}')

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

ValidUserDependency = Depends(get_current_user())
OptionalUserDependency = Depends(get_current_user(required = False))

OptionalUser = Annotated[Optional[CurrentUser], Depends(get_current_user(required = False))]
ValidUser = Annotated[CurrentUser, Depends(get_current_user())]


"""
These are able to be used as injections

@app.get('/')
@require_auth_role('admin')
async def index(current_user: ValidUser):
    ...


"""
def require_api_key(
    api_keys: Union[str, List[str]],
    dry_run: Optional[bool] = False,
    verbose: Optional[bool] = False,
    allow_authorized_user: Optional[bool] = False,
):
    """
    Creates an api key validator wrapper
    """
    if not isinstance(api_keys, list): api_keys = [api_keys]
    def has_api_key(*args, api_key: APIKey, current_user: OptionalUser, **kwargs):
        """
        Checks if the api key is valid
        """
        if api_key not in api_keys: 
            if allow_authorized_user and current_user and current_user.is_valid:
                return
            if verbose: logger.info(f'`{api_key}` is not a valid api key')
            if dry_run: return
            raise errors.InvalidAPIKeyException(detail = f'`{api_key}` is not a valid api key')
    
    return create_function_wrapper(has_api_key)


def require_api_key_or_user_role(
    api_keys: Union[str, List[str]],
    role: Optional[Union[str, UserRole]] = None,
    dry_run: Optional[bool] = False,
    verbose: Optional[bool] = False,
):
    """
    Creates an api key validator wrapper
    """
    if not isinstance(api_keys, list): api_keys = [api_keys]
    user_role = UserRole.parse_role(role) if role else None

    async def has_api_key_or_role(*args, current_user: OptionalUser, api_key: Optional[APIKey] = None, **kwargs):
        """
        Checks if the api key is valid
        """
        if not api_key and not current_user:
            if verbose: logger.info('No api key or user found')
            raise errors.NoAPIKeyException()
        if api_key and api_key in api_keys: return
        if current_user and current_user.is_valid:
            if user_role and current_user.role < user_role:
                if verbose: logger.info(f'User {current_user.user_id} does not have required role: {user_role}')
                if dry_run: return
                raise errors.InvalidAuthRoleException(detail = f'User {current_user.user_id} does not have required role: {user_role}')
            return
        if verbose: logger.info(f'`{api_key}` is not a valid api key')
        if dry_run: return
        raise errors.InvalidAPIKeyException(detail = f'`{api_key}` is not a valid api key')
    
    return create_function_wrapper(has_api_key_or_role)


"""
These require to be set as dependencies
"""

def auth_role_dependency(
    role: Union[str, UserRole],
    disabled: Optional[bool] = None,
    dry_run: Optional[bool] = False,
    verbose: Optional[bool] = False,
):
    """
    Creates an auth role validator wrapper
    """
    user_role = UserRole.parse_role(role) if isinstance(role, str) else role

    async def has_auth_role(current_user: ValidUser):
        """
        Checks if the auth role is valid
        """
        if disabled: return
        if current_user.role < user_role:
            if verbose: logger.info(f'User {current_user.user_id} does not have required role: {user_role}')
            if dry_run: return
            raise errors.InvalidAuthRoleException(detail = f'User {current_user.user_id} does not have required role: {user_role}')

    return Depends(has_auth_role)



def api_key_or_user_role_dependency(
    api_keys: Union[str, List[str]],
    role: Optional[Union[str, UserRole]] = None,
    dry_run: Optional[bool] = False,
    verbose: Optional[bool] = False,
):
    """
    Creates an api key validator wrapper
    """
    if not isinstance(api_keys, list): api_keys = [api_keys]
    user_role = UserRole.parse_role(role) if role else None

    async def has_api_key_or_role(
        current_user: OptionalUser,
        api_key: Optional[APIKey] = None,
    ):
        """
        Checks if the api key is valid
        """
        if not api_key and not current_user:
            if verbose: logger.info('No api key or user found')
            raise errors.NoAPIKeyException()
        if api_key and api_key in api_keys: return
        if current_user and current_user.is_valid:
            if user_role and current_user.role < user_role:
                if verbose: logger.info(f'User {current_user.user_id} does not have required role: {user_role}')
                if dry_run: return
                raise errors.InvalidAuthRoleException(detail = f'User {current_user.user_id} does not have required role: {user_role}')
            return
        if verbose: logger.info(f'`{api_key}` is not a valid api key')
        if dry_run: return
        raise errors.InvalidAPIKeyException(detail = f'`{api_key}` is not a valid api key')

    return Depends(has_api_key_or_role)
    
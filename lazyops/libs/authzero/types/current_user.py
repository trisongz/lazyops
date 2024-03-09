from __future__ import annotations

"""
The Session User Object
"""

from pydantic import Field, model_validator, PrivateAttr
from lazyops.types.models import ConfigDict, schema_extra

from .base import BaseModel
from .common import UserType, ValidationMethod
from .user_roles import UserRole
from .user_session import UserSession
from .user_data import AZUserData
from .claims import UserJWTClaims, APIKeyJWTClaims
from .auth import AuthObject

from .errors import (
    InvalidTokenException, 
    NoTokenException, 
    InvalidAPIKeyException, 
    InsufficientPermissionsException,
    InvalidAuthorizationException,
    InvalidAPIKeyPrefixException,
    InvalidAPIKeySecretException,
    HTTPException
)

from ..utils.lazy import logger, ThreadPooler
from ..utils.helpers import parse_scopes


from typing import Optional, List, Dict, Any, Union, Callable, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request
    from ..flows.user_session import UserSessionFlow


class CurrentUser(BaseModel):
    """
    The Current User Object
    """

    scope: Optional[str] = None # allow setting the scope at the class level
    attributes: Optional[Dict[str, Any]] = Field(default_factory = dict) # Persistent Data through Session, if enabled
    data: Optional[Dict[str, Any]] = Field(default_factory = dict) # Non-Persistent Data
    session: Optional[UserSession] = None # Session Data
    role: Optional[UserRole] = None # User Role
    auth_obj: Optional[AuthObject] = None
    
    # Configuration Options
    required: Optional[bool] = True # If True, will raise an exception if the user does not pass validation
    verbose: Optional[bool] = True # If True, will log the validation errors

    # Previous init args
    # allow_maintenance: Optional[bool] = False
    # silent: Optional[bool] = None
    # is_system_user: Optional[bool] = False

    # Set From Validation
    user_type: Optional[UserType] = None # User Type
    validation_method: Optional[ValidationMethod] = None
    claims: Optional[Union[UserJWTClaims, APIKeyJWTClaims]] = None
    user_data: Optional[AZUserData] = None
    api_key: Optional[str] = None

    # Sesssion Attributes
    _pre_validate_hooks: Optional[List[Callable]] = PrivateAttr(None)
    _post_validate_hooks: Optional[List[Callable]] = PrivateAttr(None)

    def __init__(self, **data):
        """
        Validates the current user
        """
        self.pre_init(**data)
        super().__init__(**data)
        self._pre_validate_hooks, self._post_validate_hooks = self.settings.ctx.get_validation_hooks()
        self.post_init(**data)

    def pre_init(self, **kwargs):
        """
        Pre Init
        - This behavior can be overridden
        """
        pass

    def post_init(self, **kwargs):
        """
        Post Init
        - This behavior can be overridden
        """
        pass

    def validate_permissions(self):
        """
        Validates the Permissions
        """
        if self.scope is not None and self.scope not in self.claims.scopes:
            raise InsufficientPermissionsException( detail = f'Insufficient Permissions for Scope: {self.scope}')
    
    def validate_scopes(self, scopes: List[str]):
        """
        Validates the Scopes
        """
        
        for scope in scopes:
            if scope not in self.claims.scopes:
                if self.verbose: logger.warning(f'Failed to Validate Scope: {scope} against {self.claims.scopes}. Present Scopes: {scopes}')
                raise InsufficientPermissionsException(detail = f'Insufficient Permissions for Scope: {scope}')
        
    @property
    def session_flow(self) -> 'UserSessionFlow':
        """
        Gets the User Session Flow
        """
        return self.get_flow('user_session', user_id = self.user_id)
    

    @property
    def user_id(self) -> Optional[str]:
        """
        Returns the User ID or API Client ID
        """
        if self.claims: return self.claims.sub

    @property
    def user_email(self) -> Optional[str]:
        """
        Returns the User Email
        """
        if self.user_data: return self.user_data.email
    

    @property
    def user_email_domain(self) -> Optional[str]:
        """
        Gets the User Email Domain
        """
        if self.user_email is None: return None
        return self.user_email.split('@')[-1].lower()
    
    """
    Extra Properties that can be persisted in the attributes
    """

    """
    User Roles
    """
    @property
    def user_roles(self) -> Optional[List[str]]:
        """
        Gets the User Roles
        """
        return self.attributes.get('user_roles', [])
    
    @user_roles.setter
    def user_roles(self, value: Optional[Union[str, List[str]]]):
        """
        Sets the User Roles
        """
        if isinstance(value, str): value = [value]
        if not self.attributes.get('user_roles'): self.attributes['user_roles'] = []        
        for role in value:
            role = role.lower()
            if role not in self.attributes['user_roles']:
                self.attributes['user_roles'].append(role)
    
    @user_roles.deleter
    def user_roles(self):
        """
        Deletes the User Roles
        """
        if self.attributes.get('user_roles'):
            _ = self.attributes.pop('user_roles')
    
    

    """
    API Client 
    """

    @property
    def api_client_id(self) -> Optional[str]:
        """
        Gets the API Client ID
        """
        return self.attributes.get('api_client_id')
    
    @api_client_id.setter
    def api_client_id(self, value: Optional[str]):
        """
        Sets the API Client ID
        """
        self.attributes['api_client_id'] = value
    
    @api_client_id.deleter
    def api_client_id(self):
        """
        Deletes the API Client ID
        """
        if self.attributes.get('api_client_id'):
            _ = self.attributes.pop('api_client_id')
    
    @property
    def api_client_identity(self) -> Optional[str]:
        """
        Gets the API Client Identity
        """
        return self.attributes.get('api_client_identity')

    """
    Validators
    """

    def has_user_roles(self, roles: Union[Union[str, int, 'UserRole'], List[Union[str, int, 'UserRole']]]) -> bool:
        """
        Checks against multiple roles
        """
        if not isinstance(roles, list): roles = [roles]
        valid_roles = [UserRole.parse_role(role) for role in roles]
        return any(self.role >= role for role in valid_roles)
    
    def has_user_role(self, role: Union[str, int, 'UserRole']) -> bool:
        """
        Checks against a single role
        """
        role = UserRole.parse_role(role)
        return self.role >= role
    
    def has_permission(self, permission: Union[str, int, UserRole]) -> bool:
        """
        Checks if the user has a permission
        """
        permission = UserRole.parse_role(permission)
        return self.role >= permission

    def has_valid_emails(self, emails: List[str]) -> bool:
        """
        Checks if the user has a valid email
        """
        return any(email in self.user_data.email for email in emails)
    
    def has_valid_email_domains(self, domains: List[str]) -> bool:
        """
        Checks if the user has a valid email domain
        """
        return any(domain in self.user_email_domain for domain in domains)
    
    """
    Main Validation Methods
    """



    """
    Hooks
    """

    async def run_pre_validate_hooks(self, request: 'Request'):
        """
        Runs the Pre-Validate Hooks
        """
        if self._pre_validate_hooks is None: return
        for hook in self._pre_validate_hooks:
            await ThreadPooler.asyncish(hook, self, request)
    
    async def run_post_validate_hooks(self, request: 'Request'):
        """
        Runs the Post-Validate Hooks
        """
        if self._post_validate_hooks is None: return
        for hook in self._post_validate_hooks:
            await ThreadPooler.asyncish(hook, self, request)


    def __getitem__(self, key: str) -> Optional[Any]:
        """
        Returns the user attributes or dict key
        """
        return self.attributes.get(key, getattr(self, key, None))
    
    def __setitem__(self, key: str, value: Any):
        """
        Sets the user attributes or dict key
        """
        if hasattr(self, key): setattr(self, key, value)
        else: self.attributes[key] = value


    def update_attributes(self, attributes: Dict[str, Any]):
        """
        Updates the attributes
        """
        for key, value in attributes.items():
            if isinstance(value, dict):
                self.attributes[key] = self.attributes.get(key, {})
                self.attributes[key].update(value)
            elif isinstance(value, list):
                self.attributes[key] = self.attributes.get(key, [])
                self.attributes[key].extend(value)
                self.attributes[key] = list(set(self.attributes[key]))
            else:
                self.attributes[key] = value
    

    def get_session_cookie_kwargs(self, is_delete: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        """
        Gets the Session Cookie Value
        """
        cookie_kws = {
            "key": self.settings.session_cookie_key,
            "httponly": True,
            "secure": self.settings.is_secure_ingress,
        }
        if not is_delete:
            cookie_kws['value'] = self.session_flow.cache_key
            cookie_kws['expires'] = self.session.expiration_ts
        return cookie_kws
    


    @classmethod
    def add_post_validate_hook(cls, hook: Callable):
        """
        Adds a post validate hook
        """
        from ..configs.base import AuthZeroContext
        AuthZeroContext.add_post_validate_hook(hook)
    
    @classmethod
    def add_pre_validate_hook(cls, hook: Callable):
        """
        Adds a pre validate hook
        """
        from ..configs.base import AuthZeroContext
        AuthZeroContext.add_pre_validate_hook(hook)
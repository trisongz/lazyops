from __future__ import annotations

"""
The Session User Object
"""

from pydantic import Field, model_validator, PrivateAttr
from lazyops.types.models import ConfigDict, schema_extra
from lazyops.libs import lazyload
from .base import BaseModel
from .common import UserType, ValidationMethod
from .user_roles import UserRole
from .user_session import UserSession
from .user_data import AZUserData
from .claims import UserJWTClaims, APIKeyJWTClaims
from .auth import AuthObject
from .security import Authorization, APIKey
from .errors import (
    AuthZeroException,
    InvalidTokenException, 
    NoTokenException, 
    InvalidAPIKeyException, 
    InsufficientPermissionsException,
    InvalidAuthorizationException,
    InvalidAPIKeyPrefixException,
    ExpiredAPIKeyData,
    InvalidAPIKeySecretException,
)

from ..utils.lazy import logger, ThreadPooler
from ..utils.helpers import parse_scopes, get_hashed_key
from ..utils.decoders import decode_token

from typing import Optional, List, Dict, Any, Union, Callable, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    
    from fastapi import Request
    from fastapi.background import BackgroundTasks
    from fastapi.datastructures import Headers
    from ..types.auth import APIKeyData
    from ..flows.user_session import UserSessionFlow
    from ..flows.user_data import UserDataFlow

if lazyload.TYPE_CHECKING:
    import tldextract
else:
    tldextract = lazyload.LazyLoad('tldextract')



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
    verbose: Optional[bool] = None # If True, will log the validation errors

    # Passthrough Configurations for the Auth Flow
    session_enabled: Optional[bool] = None
    request_id_enabled: Optional[bool] = None
    domain_source_enabled: Optional[bool] = None
    role_configure_enabled: Optional[bool] = None


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

    from_session: Optional[bool] = None

    # Sesssion Attributes
    _pre_validate_hooks: Optional[List[Callable]] = PrivateAttr(None)
    _post_validate_hooks: Optional[List[Callable]] = PrivateAttr(None)

    def __init__(self, **data):
        """
        Validates the current user
        """
        self.pre_init(**data)
        super().__init__(**data)
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

    async def precall_hook(self, request: 'Request', **kwargs):
        """
        Runs the precall hook
        """
        # Defer these until they are called to prevent loading the settings prior to full initialization
        self._pre_validate_hooks, self._post_validate_hooks = self.settings.ctx.get_validation_hooks()
        if self.session_enabled is None: self.session_enabled = self.settings.user_session_enabled
        if self.domain_source_enabled is None: self.domain_source_enabled = self.settings.user_domain_source_enabled
        if self.request_id_enabled is None: self.request_id_enabled = self.settings.user_request_id_enabled
        if self.role_configure_enabled is None: self.role_configure_enabled = self.settings.user_role_configure_enabled
        if self.verbose is None: 
            self.verbose = self.required or self.settings.is_development_env

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
                # if not self.required: 
                if self.verbose: logger.warning(f'Failed to Validate Scope: {scope} against {self.claims.scopes}. Present Scopes: {scopes}')
                raise InsufficientPermissionsException(detail = f'Insufficient Permissions for Scope: {scope}')
        
    @property
    def session_flow(self) -> 'UserSessionFlow':
        """
        Gets the User Session Flow
        """
        return self.get_flow('user_session', user_id = self.user_id)
    
    @property
    def user_data_flow(self) -> 'UserDataFlow':
        """
        Gets the User Data Flow
        """
        return self.get_flow('user_data', user_id = self.user_id)
    

    @property
    def user_id(self) -> Optional[str]:
        """
        Returns the User ID or API Client ID
        """
        return self.claims.sub if self.claims else self.api_client_id

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
    
    @property
    def is_system_user(self) -> bool:
        """
        Returns whether the user is a system/api user
        """
        return self.user_type and self.user_type in {
            'api_client', 'service', 'system'
        }

    
    @property
    def is_valid(self) -> bool:
        """
        Returns whether the user is valid
        """
        return self.validation_method is not None


    """
    Extra Properties that can be persisted in the attributes
    """

    @property
    def service_account_name(self) -> Optional[str]:
        """
        Returns the Service Account Name
        """
        if 'service_account_name' not in self.attributes:
            service_account_name = None
            if self.role == UserRole.SYSTEM:
                client_id = self.user_id.replace('@clients', '')
                if service_account_name := self.get_management_api().get_service_client_name(client_id):
                    self.attributes['service_account_name'] = service_account_name.replace('(', '').replace(')', '').replace(' ', '-').lower()
                else:
                    self.attributes['service_account_name'] = client_id
            self.attributes['service_account_name'] = service_account_name
        return self.attributes['service_account_name']

    @property
    def domain_source(self) -> Optional[str]:
        """
        Returns the Domain Source
        """
        if 'domain_source' not in self.attributes:
            self.attributes['domain_source'] = None
        return self.attributes['domain_source']
    
    @property
    def is_local_request(self) -> bool:
        """
        Returns if the request is local
        """
        return self.domain_source and any(
            source in self.domain_source
            for source in {'localhost', '0.0.0.0', '127.0.0.1'}
        )

    @property
    def request_id(self) -> Optional[str]:
        """
        Returns the request id
        """
        return self.data.get('request_id')

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

    def has_user_roles(self, roles: Union[Union[str, int, 'UserRole'], List[Union[str, int, 'UserRole']]], require_all: Optional[bool] = False) -> bool:
        """
        Checks against multiple roles
        """
        if not isinstance(roles, list): roles = [roles]
        valid_roles = [UserRole.parse_role(role) for role in roles]
        if require_all: return all(self.role >= role for role in valid_roles)
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
    Session Methods
    """
    async def retrieve_and_set_user_session(
        self,
        request: 'Request',
        **kwargs
    ):
        """
        Retrieves the user session and sets it
        """
        session = await self.get_flow_schema('user_session').aget(self, request)
        if session is None: return
        self.session = session
        self.auth_obj.x_api_key = session.api_key
        self.from_session = True
        # logger.info(f'Retrieved User Session: {self.session}')

    async def save_user_session(
        self,
        **kwargs
    ):
        """
        Saves the current session
        """
        if self.session is None: return
        # if self.verbose: logger.info(f'Saving Session: {self.user_id}')
        await self.session_flow.asave(self.session)
        await self.session_flow.asave_data(self.attributes)

    async def delete_user_session(
        self,
        include_data: Optional[bool] = False,
        **kwargs
    ):
        """
        Deletes the current session
        """
        if self.session is None: return
        # if self.verbose: logger.info(f'Deleting Session: {self.user_id}')
        await self.session_flow.adelete()
        if include_data: await self.session_flow.adelete_data()

    async def set_user_session(
        self,
        request: 'Request',
        **kwargs
    ):
        """
        Sets the user session
        """
        if self.session is not None: return
        self.session = self.get_resource('user_session', user_id = self.user_id, api_key = self.api_key)
        await self.save_user_session()


    async def create_or_load_user_session(
        self,
        request: 'Request',
        background_tasks: 'BackgroundTasks' = None, 
        **kwargs
    ):
        """
        Creates or loads the user session
        """
        if self.session is None: 
            self.session = self.get_resource('user_session', user_id = self.user_id, api_key = self.api_key)
            # await self.save_user_session()
        attributes = await self.session_flow.aload_data()
        if attributes: self.update_attributes(attributes)
        if background_tasks: background_tasks.add_task(self.save_user_session)

    
    """
    API Key Data Methods
    """

    async def save_api_key_data(
        self,
        client_id: str,
        user_data: 'AZUserData',
        claims: 'UserJWTClaims',
        **kwargs
    ):
        """
        Persists the API Key Data
        """
        await self.get_flow('api_key', client_id).aset(user_data, claims)

    async def load_api_key_data(
        self,
        client_id: str,
        **kwargs
    ) -> Optional['APIKeyData']:
        """
        Loads the API Key Data
        """
        api_key_data = await self.get_flow('api_key', client_id).afetch()
        if api_key_data is None: return
        self.user_data = api_key_data.user_data
        self.claims = api_key_data.claims


    """
    API Client Methods
    """

    async def configure_api_client_post_authorization(self, request: Optional[Request]):
        """
        Configures the API Client
        """
        api_client_identity = request.headers.get(self.settings.api_client_id_header_key)
        if api_client_identity is None:
            raise InvalidAPIKeyException(detail = f"Invalid API Client Identity: {api_client_identity}")
        if api_client_env := request.headers.get(self.settings.api_client_env_header_key):
            self.attributes['api_client_env'] = api_client_env
        self.attributes['api_client_identity'] = api_client_identity
        if self.role is None: self.role = UserRole.API_CLIENT
        self.api_client_id = f'{self.claims.sub}:{api_client_identity}'
        self.user_type = 'api_client'
        await self.save_api_key_data(client_id = self.api_client_id, user_data = self.user_data, claims = self.claims)
        # await self.save_api_key_data(client_id = api_client_identity, user_data = self.user_data, claims = self.claims)
        self.api_key = self.settings.create_api_key(self.api_client_id, prefix = self.settings.api_client_api_key_prefix)


    """
    Main Auth Methods
    """


    """
    Token Authorizations
    """
    async def validate_authorization(
        self, 
        request: 'Request', 
        token: Optional[str] = None, 
        scopes: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Verifies the Authorization
        """
        self.claims = decode_token(request = request, token = token or self.auth_obj.auth_token, settings = self.settings)
        self.validate_permissions() if scopes is None else self.validate_scopes(scopes)
        try:
            self.user_data = await self.user_data_flow.afetch()
        except Exception as e:
            if '@clients' not in self.claims.sub: 
                self.settings.logger.trace(f'Invalid User Data: {self.claims.sub}', e)
            self.user_data = AZUserData(
                user_id = self.claims.sub, user_metadata = {}, app_metadata = {},
            )
        if self.validation_method is None: self.validation_method = 'auth_token'
        if self.claims.sub.endswith('@clients'):
            if request.headers.get(self.settings.api_client_id_header_key) is not None:
                return await self.configure_api_client_post_authorization(request)
            if self.role is None: self.role = UserRole.SERVICE
            self.user_type = 'service'
        if self.role is None: 
            if self.user_data and self.user_data.user_metadata and self.user_data.user_metadata.get('role'):
                self.role = UserRole.parse_role(self.user_data.user_metadata['role'])
            elif self.user_data and self.user_data.app_metadata and self.user_data.app_metadata.get('role'):
                self.role = UserRole.parse_role(self.user_data.app_metadata['role'])
            else:
                self.role = UserRole.USER
        # Set the api-key
        await self.save_api_key_data(client_id = self.user_id, user_data = self.user_data, claims = self.claims)
        self.api_key = self.settings.create_api_key(self.user_id)


    """
    API Key Authorizations
    """

    async def get_or_create_api_key_data_for_allowed(
        self,
        api_client_id: str,
        **kwargs,
    ):
        """
        Creates an api key data for the allowed client
        """
        api_key_data = await self.get_flow('api_key', api_client_id).afetch()
        if api_key_data is not None:
            self.user_data = api_key_data.user_data
            self.claims = api_key_data.claims
            return
        self.settings.autologger.info(f'Creating API Key Data for {api_client_id}')
        self.user_data = AZUserData(
            user_id = self.api_client_id, 
            user_metadata = {}, 
            app_metadata = {},
        )
        self.claims = self.get_resource(
            'api_key_jwt_claims',
            aud = self.settings.audience,
            azp = self.settings.client_id,
            iss = self.settings.domain,
            sub = self.api_client_id,
            user_roles = [self.role.value],
        )
        await self.save_api_key_data(client_id = api_client_id, user_data = self.user_data, claims = self.claims)
        

    async def validate_allowed_api_key(self, request: Optional[Request], **kwargs):
        """
        Verifies the Allowed API Key
        """
        self.user_type = 'allowed'
        self.api_key = self.auth_obj.x_api_key
        if self.validation_method is None: self.validation_method = 'api_key'
        
        client_config = self.settings.allowed_api_keys.get(self.auth_obj.x_api_key, {})
        if self.role is None: self.role = UserRole.parse_role(client_config.get('role', 'API_CLIENT'))
        
        # Handle setting the other variables / properties
        api_client_identity = request.headers.get(self.settings.api_client_id_header_key, client_config.get('client_name', 'default'))
        self.attributes['api_client_identity'] = api_client_identity
        self.api_client_id = f'allowed.{api_client_identity}'
        await self.get_or_create_api_key_data_for_allowed(self.api_client_id)
        

    async def validate_service_client_api_key(self, request: Optional[Request], **kwargs):
        """
        Verifies the Service Client API Key
        """
        key_hash = get_hashed_key(self.auth_obj.x_api_key)
        if key_hash not in self.settings.api_key_hashes:
            raise InvalidAPIKeyException(detail=f'Invalid Service Client API Key: {self.auth_obj.x_api_key}')
        self.user_type = 'service'
        if self.validation_method is None: self.validation_method = 'api_key'
        if self.role is None: self.role = UserRole.SERVICE
        self.api_key = self.auth_obj.x_api_key
    
    async def refresh_api_client_api_key_data(
        self,
        api_client_id: str,
        request: Optional[Request],
        **kwargs
    ):
        """
        Refreshes the API Client API Key Data
        """
        self.claims = decode_token(request = request, token = self.auth_obj.auth_token)
        self.user_data = AZUserData(
            user_id = self.claims.sub, user_metadata = {}, app_metadata = {},
        )
        await self.save_api_key_data(client_id = api_client_id, user_data = self.user_data, claims = self.claims)
        self.settings.autologger.info(f'Refreshed API Client API Key Data for {api_client_id}')

    async def validate_api_client_api_key(self, request: Optional[Request], scopes: Optional[List[str]] = None, **kwargs):
        """
        Verifies the API Client API Key
        """
        try:
            # xxxxx@clients:client_id
            api_client_id = await self.settings.adecrypt_api_key(self.auth_obj.x_api_key, prefix = self.settings.api_client_api_key_prefix)
            await self.load_api_key_data(client_id = api_client_id)
            # Refresh it if the token is available
            if self.claims is None and self.auth_obj.auth_token:
                await self.refresh_api_client_api_key_data(api_client_id = api_client_id, request = request)
            if self.claims is None:
                raise ExpiredAPIKeyData(f'[API Client] {api_client_id} is expired. Please refresh by providing a valid token.')

            self.validate_permissions() if scopes is None else self.validate_scopes(scopes)
            if self.validation_method is None: self.validation_method = 'api_key'
            if self.role is None: self.role = UserRole.API_CLIENT
            self.user_type = 'api_client'
            self.api_key = self.auth_obj.x_api_key
        except ExpiredAPIKeyData as e:
            raise e
        except Exception as e:
            if self.verbose: logger.trace(f'Invalid API Client API Key: {self.auth_obj.x_api_key}', e)
            else: logger.warning(f'Invalid API Client API Key: {self.auth_obj.x_api_key}: {e}')
            if hasattr(e, 'status_code'): raise e
            raise InvalidAPIKeyException(detail = f'Invalid API Client API Key: {self.auth_obj.x_api_key}') from e

    async def refresh_user_api_key_data(
        self,
        request: Optional[Request],
        **kwargs
    ):
        """
        Refreshes the User API Key Data
        """
        self.claims = decode_token(request = request, token = self.auth_obj.auth_token)
        self.user_data = await self.user_data_flow.afetch()
        await self.save_api_key_data(client_id = self.user_id, user_data = self.user_data, claims = self.claims)
        self.settings.autologger.info(f'Refreshed User API Key Data for {self.user_id}')


    async def validate_user_api_key(self, request: Optional[Request], scopes: Optional[List[str]] = None, **kwargs):
        """
        Verifies the User API Key
        """
        try:
            user_id = await self.settings.adecrypt_api_key(self.auth_obj.x_api_key, prefix = self.settings.api_key_prefix)
            await self.load_api_key_data(client_id = user_id)
            if not self.claims and self.auth_obj.auth_token:
                await self.refresh_user_api_key_data(request = request)
            # if self.claims is None or '@clients' in self.claims.sub:
            if self.claims is None:
                raise ExpiredAPIKeyData(f'[User] {user_id} is expired. Please refresh by reauthenticating.')
            self.validate_permissions() if scopes is None else self.validate_scopes(scopes)
            if self.validation_method is None: self.validation_method = 'api_key'
            if self.role is None: 
                if self.user_data and self.user_data.user_metadata and self.user_data.user_metadata.get('role'):
                    self.role = UserRole.parse_role(self.user_data.user_metadata['role'])
                elif self.user_data and self.user_data.app_metadata and self.user_data.app_metadata.get('role'):
                    self.role = UserRole.parse_role(self.user_data.app_metadata['role'])
                elif '@clients' in self.claims.sub:
                    self.role = UserRole.SERVICE
                else:
                    self.role = UserRole.USER
                # self.role = UserRole.USER
            self.user_type = 'service' if '@clients' in self.claims.sub else 'user'
            self.api_key = self.auth_obj.x_api_key
        except ExpiredAPIKeyData as e:
            raise e
        except Exception as e:
            if self.verbose: logger.trace(f'Invalid User API Key: {self.auth_obj.x_api_key}', e)
            else: logger.warning(f'Invalid User API Key: {self.auth_obj.x_api_key}: {e}')
            if hasattr(e, 'status_code'): raise e
            raise InvalidAPIKeyException(detail = f'Invalid User API Key: {self.auth_obj.x_api_key}') from e
    

    async def validate_api_key(
        self,
        request: 'Request',
        scopes: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Validates the API Key
        """

        # Handle Allowed API Keys
        if self.settings.allowed_api_keys and self.auth_obj.x_api_key in self.settings.allowed_api_keys:
            return await self.validate_allowed_api_key(request = request, scopes = scopes, **kwargs)
        
        # Handle Service Client API Keys
        if not self.auth_obj.x_api_key.startswith(self.settings.api_key_prefix) and (
            self.settings.api_key_suffix and not self.auth_obj.x_api_key.endswith(self.settings.api_key_suffix)
        ):
            return await self.validate_service_client_api_key(request, scopes = scopes, **kwargs)
        
        # Handle API Client API Keys
        if self.auth_obj.x_api_key.startswith(self.settings.api_client_api_key_prefix):
            return await self.validate_api_client_api_key(request, scopes = scopes, **kwargs)

        if not self.auth_obj.x_api_key.startswith(self.settings.api_key_prefix):
            raise InvalidAPIKeyPrefixException(detail = 'Invalid API Key Prefix. Your API Key may be deprecated. Please regenerate your API Key by logging in again.')
        
        # Handle User API Keys
        return await self.validate_user_api_key(request, scopes = scopes, **kwargs)



    """
    Main Validation Methods
    """

    async def run_validation_methods(
        self,
        request: 'Request',
        background_tasks: 'BackgroundTasks' = None,
        **kwargs
    ):
        """
        Runs the validation methods
        """
        # Attempt to validate the API Key first
        # Fallback to the Authorization
        if self.auth_obj.has_x_api_key:
            try:
                return await self.validate_api_key(request = request, **kwargs)
            except Exception as e:
                if not self.auth_obj.has_auth_token: raise e
        return await self.validate_authorization(request = request, **kwargs)
    
    async def run_post_validation_methods(
        self,
        request: 'Request',
        background_tasks: 'BackgroundTasks' = None,
        **kwargs
    ):
        """
        Runs the post validation methods
        """
        await self.run_post_validate_hooks(request)
        if self.is_valid and self.session_enabled: 
            await self.create_or_load_user_session(request, background_tasks = background_tasks, **kwargs)
        
    async def run_validate(
        self, 
        request: 'Request', 
        background_tasks: 'BackgroundTasks' = None, 
        **kwargs
    ):
        """
        This can be subclassed to run the validation
        """
        self.auth_obj = AuthObject.from_request(request, settings = self.settings)
        await self.run_pre_validate_hooks(request)
        if not self.auth_obj.has_auth_token and not self.auth_obj.has_x_api_key:
            raise InvalidAuthorizationException(detail = 'No API Key or Token found')
        
        await self.run_validation_methods(request = request, background_tasks = background_tasks, **kwargs)
        await self.run_post_validation_methods(request, background_tasks = background_tasks, **kwargs)
        
    async def __call__(
        self, 
        request: Request, 
        background_tasks: BackgroundTasks, 
        api_key: APIKey = None, 
        authorization: Authorization = None
    ) -> 'CurrentUser':
        """
        The Middleware Entry Point
        """
        # We use the authorization / api_key params to allow for the 
        # auth to be displayed in the docs
        await self.precall_hook(request)
        try:
            await self.run_validate(request, background_tasks = background_tasks, api_key = api_key, authorization = authorization)
        except AuthZeroException as e:
            if (
                self.verbose
                and 'No API Key or Token found' not in e.detail
                and 'Invalid API Key Prefix' not in e.detail
                and not e.log_error
                and not e.log_devel
            ):
                if self.required:
                    logger.trace('Error Validating User', e)
                else:
                    logger.error(f'Error Validating User: {e}')
            if self.required: raise e
        except Exception as e:
            if self.verbose: 
                if self.required:
                    logger.trace('Error validating user', e)
                    logger.info(self, prefix = self.user_id)
                else:
                    logger.error(f'Error validating user: {e}')
            if self.required: raise e
        return self
    
    async def from_access_token(
        self, 
        access_token: str, 
        request: Optional[Request] = None,
        scope: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        background_tasks: Optional[BackgroundTasks] = None,
        **kwargs,
    ):
        """
        Returns the Current User from the Access Token
        """
        await self.precall_hook(request)
        self.auth_obj = AuthObject(auth_token = access_token)
        await self.run_pre_validate_hooks(request)
        scopes = parse_scopes(scope = scope, scopes = scopes)
        try:
            await self.run_validation_methods(request = request, token = self.auth_obj.auth_token, scopes = scopes, background_tasks = background_tasks, **kwargs)
            await self.run_post_validation_methods(request, background_tasks = background_tasks, **kwargs)
        except Exception as e:
            if self.verbose: 
                if self.required:
                    logger.trace('Error validating user', e)
                    logger.info(self, prefix = self.user_id)
                else:
                    logger.error(f'Error validating user: {e}')
            if self.required: raise e
        return self
    
    async def from_data_sources(
        self, 
        *data: Iterable[Union['Headers', Dict[str, str]]],
        request: Optional[Request] = None,
        scope: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        background_tasks: Optional[BackgroundTasks] = None,
        **kwargs,
    ):
        """
        Returns the Current User from Iterable Data Sources
        """
        await self.precall_hook(request)
        self.auth_obj = AuthObject.from_items(*data, settings = self.settings)
        await self.run_pre_validate_hooks(request)
        if not self.auth_obj.has_auth_token and not self.auth_obj.has_x_api_key:
            if self.verbose: logger.trace('No Auth Token or X-API-Key found')
            if self.required: raise InvalidAuthorizationException()
            return self
        
        scopes = parse_scopes(scope = scope, scopes = scopes)
        try:
            await self.run_validation_methods(request = request, scopes = scopes, **kwargs)
            await self.run_post_validation_methods(request, background_tasks = background_tasks, **kwargs)
        except Exception as e:
            if self.verbose: 
                if self.required:
                    logger.trace('Error validating user', e)
                    logger.info(self, prefix = self.user_id)
                else:
                    logger.error(f'Error validating user: {e}')
            if self.required: raise e
        return self

    
    """
    Hooks
    """

    async def run_pre_validate_hooks(self, request: 'Request', **kwargs):
        """
        Runs the Pre-Validate Hooks
        """
        if self.session_enabled: await self.retrieve_and_set_user_session(request, **kwargs)
        if self._pre_validate_hooks is None: return
        for hook in self._pre_validate_hooks:
            await ThreadPooler.asyncish(hook, self, request)
    
    async def run_post_validate_hooks(self, request: 'Request'):
        """
        Runs the Post-Validate Hooks
        """
        if self.request_id_enabled: 
            await self.configure_request_id_posthook(request)
        if self.domain_source_enabled:
            await self.configure_domain_source_posthook(request)
        if self.role_configure_enabled:
            await self.configure_roles_posthook(request)
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

    def __bool__(self) -> bool:
        """
        Returns True if the user is valid
        """
        return self.is_valid


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
        # Maybe set to expiration now
        return cookie_kws
    

    def get_whoami_data(self, include_data: Optional[bool] = None, **kwargs) -> Dict[str, Any]:
        """
        Returns the Whoami Data
        """
        include_data = include_data if include_data is not None else self.settings.is_development_env
        data = {
            'user': self.user_id, 
            'api_key': self.api_key,
            'request_id': self.request_id,
        }
        if include_data: 
            data['data'] = self.model_dump(mode = 'json', **kwargs)
            if self.session:
                data['session_ttl'] = self.session.ttl
            data['domain_source'] = self.domain_source
        if self.settings.is_development_env and self.session:
            data['session'] = self.session.model_dump(mode = 'json')
        return data

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

    @classmethod
    def fetch_user_data(cls, user_id: str, **kwargs) -> 'AZUserData':
        """
        Returns the user data
        """
        return cls.get_flow('user_data', user_id = user_id).get(**kwargs)
    
    @classmethod
    async def afetch_user_data(cls, user_id: str, **kwargs) -> 'AZUserData':
        """
        Returns the user data
        """
        return await cls.get_flow('user_data', user_id = user_id).aget(**kwargs)


    """
    Hook Methods
    """

    async def configure_request_id_posthook(self, request: 'Request', **kwargs):
        """
        Configures the request id
        """
        if hasattr(request.state, 'request_id'):
            self.data['request_id'] = request.state.request_id
    
        
    async def configure_domain_source_posthook(
        self,
        request: 'Request',
        **kwargs,
    ):
        """
        Extracts the incoming request url
        """
        headers = {k.lower(): v for k, v in request.headers.items()}
        source = str(headers.get('referer', request.url)).split('?', 1)[0] #  or headers.get('host')
        if source:
            try:
                tld_source = tldextract.extract(source)
                source = f'{tld_source.domain}'
                if tld_source.suffix:
                    source += f'.{tld_source.suffix}'
                if tld_source.subdomain:
                    source = f'{tld_source.subdomain}.{source}'
            except Exception as e:
                # extract the API source from the request
                if ":80" in source or ":443" in source:
                    source = source.rsplit(":", 1)[0]
                if "://" in source:
                    source = source.split("://", 1)[-1]
                if "/" in source:
                    source = source.split("/", 1)[0]
        self.attributes['domain_source'] = source

    
    async def configure_roles_posthook(self, request: 'Request', **kwargs):
        """
        Configures the roles
        """
        if self.role is None: return
        if self.role in [UserRole.API_CLIENT, UserRole.SYSTEM]:
            pass
        elif self.settings.admin_emails and self.user_email and self.user_email in self.settings.admin_emails:
            self.role = UserRole.ADMIN
        elif self.settings.staff_email_domains and self.user_email_domain and self.user_email_domain in self.settings.staff_email_domains:
            self.role = UserRole.STAFF
        roles = [self.role.value]
        if self.claims and self.claims.user_roles:
            roles.extend(self.claims.user_roles)
        self.user_roles = roles
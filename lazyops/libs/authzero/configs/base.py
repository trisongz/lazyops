from __future__ import annotations

"""
The AuthZero Configuration
"""

import os
import time
from pathlib import Path
from functools import lru_cache
from lazyops.utils.logs import logger as _logger, null_logger as _null_logger, Logger
from lazyops.imports._pydantic import BaseSettings
from lazyops.libs import lazyload
from lazyops.libs.proxyobj import ProxyObject

from lazyops.libs.abcs.configs.types import AppEnv
from lazyops.libs.fastapi_utils.types.persistence import TemporaryData
from pydantic import model_validator, computed_field, Field

from ..types.user_roles import UserRole
from ..utils.helpers import get_hashed_key, encrypt_key, decrypt_key, aencrypt_key, adecrypt_key, normalize_audience_name

from typing import List, Optional, Dict, Any, Union, overload, Callable, Tuple, TYPE_CHECKING

if lazyload.TYPE_CHECKING:
    import niquests
else:
    niquests = lazyload.LazyLoad("niquests")


lib_path = Path(__file__).parent.parent
_az_temp_data: Optional[TemporaryData] = None


@lru_cache()
def retrieve_jwks(domain: str) -> Dict[str, Any]:
    """
    Retrieves the JWKs from Auth0
    """
    url = f'https://{domain}/.well-known/jwks.json'
    attempts = 0
    e = None
    while attempts < 3:
        try:
            response = niquests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            attempts += 1
            _logger.warning(f"Unable to retrieve JWKS from {url}: {e}")
            time.sleep(3 * attempts)
    raise ValueError(f"Unable to retrieve JWKS from {url}")


def get_az_temp_data() -> TemporaryData:
    """
    Retrieves the temporary data
    """
    global _az_temp_data
    if _az_temp_data is None:
        _az_temp_data = TemporaryData(lib_path.joinpath('data', 'authzero.cache'))
    return _az_temp_data

class AuthZeroContextObject:
    """
    The Auth Zero Context
    """
    pre_validate_hooks: Optional[List[Callable]] = []
    post_validate_hooks: Optional[List[Callable]] = []
    configured_validators: List[str] = []

    validation_order: Optional[List[str]] = [
        'session',
        'api_key',
        'token'
    ]

    def add_post_validate_hook(self, hook: Callable):
        """
        Adds a post validate hook
        """
        if self.post_validate_hooks is None:
            self.post_validate_hooks = []
        self.post_validate_hooks.append(hook)
    
    def add_pre_validate_hook(self, hook: Callable):
        """
        Adds a pre validate hook
        """
        if self.pre_validate_hooks is None:
            self.pre_validate_hooks = []
        self.pre_validate_hooks.append(hook)

    def get_validation_hooks(self) -> Tuple[List[Callable], List[Callable]]:
        """
        Returns the validation hooks
        """
        return self.pre_validate_hooks.copy(), self.post_validate_hooks.copy()


AuthZeroContext: AuthZeroContextObject = ProxyObject(
    AuthZeroContextObject,
)

class AuthZeroSettings(BaseSettings):
    """
    The AuthZero Configuration
    """

    # Auth0 Client ID
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    audience: Optional[str] = None
    audiences: Optional[List[str]] = None

    apikey_header: Optional[str] = "x-api-key"
    authorization_header: Optional[str] = "authorization"
    authorization_scheme: Optional[str] = "bearer"

    domain: Optional[str] = None
    jwks_dict: Optional[Dict[str, Any]] = None

    admin_emails: Optional[List[str]] = None
    staff_email_domains: Optional[List[str]] = None

    # Persistence
    base_cache_key: Optional[str] = 'authzero'
    cache_key_prefix: Optional[str] = None
    data_dir: Optional[Path] = None
    local_persistence_fallback: Optional[bool] = True

    # API Keys
    api_key_prefix: Optional[str] = "xai-"
    api_key_secret_key: Optional[str] = None
    api_key_access_key: Optional[str] = None
    api_key_suffix: Optional[str] = None
    api_key_hashes: Optional[List[str]] = None

    # Can be a list or a dict of {key: role}
    if TYPE_CHECKING:
        allowed_api_keys: Optional[Union[List[str], Dict[str, Dict[str, Union[str, UserRole]]]]] = None
    else:
        allowed_api_keys: Optional[Union[str, List[str], Dict[str, str]]] = None


    # Metadata
    enabled: Optional[bool] = None
    session_enabled: Optional[bool] = None
    session_configure_enabled: Optional[bool] = None
    session_cookie_key: Optional[str] = None
    session_user_id_hashed: Optional[bool] = True
    enable_multi_audiences: Optional[bool] = None # allow for multiple audiences to be used

    # App Metadata - Used to identify the app
    app_name: Optional[str] = None
    app_env: Optional[Union[str, AppEnv]] = None
    app_ingress: Optional[str] = None
    app_client_id: Optional[str] = None

    app_scopes: Optional[List[str]] = None

    # API Clients
    api_client_id_header_key: Optional[str] = 'x-az-client-id'
    api_client_env_header_key: Optional[str] = 'x-az-client-env'
    api_client_api_key_prefix: Optional[str] = 'xaic-'

    # Expirations
    user_data_expiration: Optional[int] = 60 * 60 * 24 * 7 # 7 days
    user_session_expiration: Optional[int] = 60 * 60 * 24 * 30 # 30 days
    
    # Hook Configurations
    user_session_enabled: Optional[bool] = True
    user_request_id_enabled: Optional[bool] = True
    user_domain_source_enabled: Optional[bool] = False
    user_role_configure_enabled: Optional[bool] = True


    debug_enabled: Optional[bool] = False
    has_completed_validation: Optional[bool] = Field(None, exclude = True)
    
    if TYPE_CHECKING:
        ctx: Optional[AuthZeroContextObject] = None
    else:
        ctx: Optional[Any] = AuthZeroContext

    class Config:
        env_prefix = "AUTH_ZERO_"
        case_sensitive = False

    @computed_field
    @property
    def jwks(self) -> Dict[str, Any]:
        """
        Returns the JWKS Dict
        """
        if self.jwks_dict is not None: return self.jwks_dict
        if self.domain is None: raise ValueError("AuthZero Domain must be set")
        return retrieve_jwks(self.domain)

    @property
    def is_enabled(self) -> bool:
        """
        Returns whether the AuthZero is enabled
        """
        return self.enabled and self.client_id is not None and self.client_secret is not None


    @property
    def app_domain(self) -> Optional[str]:
        """
        Returns the App Domain
        """
        return self.app_ingress.replace('http://', '').replace('https://', '').rstrip('/') if self.app_ingress else None

    @property
    def is_secure_ingress(self) -> bool:
        """
        Returns whether the ingress is secure
        """
        return self.app_ingress.startswith("https://")

    @property
    def tenant(self) -> str:
        """
        Returns the Tenant
        """
        return f'https://{self.domain}'
    
    @property
    def issuer(self) -> str:
        """
        Returns the Issuer
        """
        return self.tenant.rstrip('/') + '/'
    
    @property
    def oauth_url(self) -> str:
        """
        Returns the OAuth URL
        """
        return f'{self.tenant}/oauth/token'
    
    @property
    def authorize_url(self) -> str:
        """
        Returns the Authorize URL
        """
        return f'{self.tenant}/authorize'
    
    @property
    def management_api_url(self) -> str:
        """
        Returns the Management API URL
        """
        return f'{self.tenant}/api/v2/'
    
    @property
    def api_key_enabled(self) -> bool:
        """
        Returns True if API Keys are Enabled
        """
        return bool(self.api_key_secret_key and self.api_key_access_key)
    

    def get_cache_key_prefix(self) -> str:
        """
        Returns the Cache Key Prefix
        """
        if self.cache_key_prefix: return self.cache_key_prefix
        if self.app_ingress: return get_hashed_key(self.app_domain)[:8]
        if self.app_name and self.app_env: return get_hashed_key(f'{self.app_name}-{self.app_env.name}')[:8]
        raise ValueError("Unable to determine cache key prefix, please set `app_name` and `app_env` or `app_ingress`")
    
    def get_cache_key(self, audience: str) -> str:
        """
        Returns the Cache Key
        """
        return f'{self.get_cache_key_prefix()}.{self.client_id[-10:]}.{normalize_audience_name(audience)}'


    def create_cache_key(
        self, 
        prefix: Optional[str] = None, 
        suffix: Optional[str] = None, 
        include_client_id: Optional[bool] = True,
        kind: Optional[str] = None
    ) -> str:
        """
        Creates a Cache Key based on the Prefix, Suffix, and Kind
        """
        # assert prefix is not None or kind is not None, "Either prefix or kind must be specified"
        cache_key_prefix = None
        if prefix is not None: cache_key_prefix = prefix
        elif kind is not None: cache_key_prefix = f'{self.get_cache_key_prefix()}.{kind}'
        else: cache_key_prefix = self.get_cache_key_prefix()
        # else: cache_key_prefix = f'{self.get_cache_key_prefix()}.{kind}'
        if include_client_id: cache_key_prefix = f'{cache_key_prefix}.{self.client_id[-10:]}'
        if suffix is not None: cache_key_prefix = f'{cache_key_prefix}.{suffix}'
        return cache_key_prefix

    def create_api_key(
        self,
        user_id: str,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> Optional[str]:
        """
        Creates an API Key
        """
        if not self.api_key_enabled: 
            raise ValueError("API Keys are not enabled. Please set `api_key_secret_key` and `api_key_access_key`")
        key = encrypt_key(user_id, self.api_key_secret_key, self.api_key_access_key)
        if prefix is None: prefix = self.api_key_prefix
        if prefix: key = f'{prefix}{key}'
        if suffix is None: suffix = self.api_key_suffix
        if suffix: key = f'{key}{suffix}'
        return key
    

    def decrypt_api_key(
        self,
        api_key: str,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> Optional[str]:
        """
        Decrypts an API Key
        """
        if not self.api_key_enabled: 
            raise ValueError("API Keys are not enabled. Please set `api_key_secret_key` and `api_key_access_key`")
        if prefix is None: prefix = self.api_key_prefix
        if prefix: api_key = api_key[len(prefix):]
        if suffix is None: suffix = self.api_key_suffix
        if suffix: api_key = api_key[:-len(suffix)]
        return decrypt_key(api_key, self.api_key_secret_key, self.api_key_access_key)
    

    """
    Async Methods
    """

    async def acreate_api_key(
        self,
        user_id: str,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> Optional[str]:
        """
        Creates an API Key
        """
        if not self.api_key_enabled: 
            raise ValueError("API Keys are not enabled. Please set `api_key_secret_key` and `api_key_access_key`")
        key = await aencrypt_key(user_id, self.api_key_secret_key, self.api_key_access_key)
        if prefix is None: prefix = self.api_key_prefix
        if prefix: key = f'{prefix}{key}'
        if suffix is None: suffix = self.api_key_suffix
        if suffix: key = f'{key}{suffix}'
        return key
    
    async def adecrypt_api_key(
        self,
        api_key: str,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> Optional[str]:
        """
        Decrypts an API Key
        """
        if not self.api_key_enabled: 
            raise ValueError("API Keys are not enabled. Please set `api_key_secret_key` and `api_key_access_key`")
        if prefix is None: prefix = self.api_key_prefix
        if prefix: api_key = api_key[len(prefix):]
        if suffix is None: suffix = self.api_key_suffix
        if suffix: api_key = api_key[:-len(suffix)]
        return await adecrypt_key(api_key, self.api_key_secret_key, self.api_key_access_key)


    def get_jwt_audiences(self) -> List[str]:
        """
        Returns the JWT Audiences
        """
        if self.enable_multi_audiences and self.audiences:
            return self.audiences
        return [self.audience]

    def add_allowed_api_key(self, key: str, role: Optional[UserRole] = None):
        """
        Adds an allowed api key
        """
        if self.allowed_api_keys is None: self.allowed_api_keys = {}
        self.allowed_api_keys[key] = UserRole.USER if role is None else UserRole.parse_role(role)

    """
    Misc Properties
    """

    @computed_field
    @property
    def in_k8s(self) -> bool:
        """
        Returns whether the app is running in kubernetes
        """
        from lazyops.utils.system import is_in_kubernetes
        return is_in_kubernetes()


    @property
    def is_local_env(self) -> bool:
        """
        Returns whether the environment is development
        """
        return self.app_env in [AppEnv.DEVELOPMENT, AppEnv.LOCAL] and not self.in_k8s
    
    @property
    def is_production_env(self) -> bool:
        """
        Returns whether the environment is production
        """
        return self.app_env == AppEnv.PRODUCTION and self.in_k8s

    @property
    def is_development_env(self) -> bool:
        """
        Returns whether the environment is development
        """
        return self.app_env in [AppEnv.DEVELOPMENT, AppEnv.LOCAL, AppEnv.CICD]
    
    @property
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        return _logger
    
    @property
    def null_logger(self) -> 'Logger':
        """
        Returns the null logger
        """
        return _null_logger
    

    @property
    def autologger(self) -> 'Logger':
        """
        Returns the autologger
        """
        return self.logger if (self.is_development_env or self.debug_enabled) else self.null_logger


    
    """
    Validate/Configure the AuthZero Settings
    """

    def validate_audiences(self):
        """
        Validates the audience
        """
        if self.audiences:
            if self.enable_multi_audiences is None: self.enable_multi_audiences = True
            elif not self.enable_multi_audiences:
                raise ValueError("Multiple Audiences must be enabled to use multiple audiences")
            if self.audience and self.audience not in self.audiences:
                self.audiences.insert(0, self.audience)
        elif not self.audience:
            self.audience = f'https://{self.domain}/userinfo'

    def validate_app_ingress(self):
        """
        Validates the app ingress
        """
        if self.app_ingress is None: return
        if not self.app_ingress.startswith('http'):
            if 'localhost' in self.app_ingress or '127.0.0.1' in self.app_ingress or '0.0.0.0' in self.app_ingress:
                if not get_az_temp_data().has_logged('app_ingress_validate'):
                    self.logger.warning('`app_ingress` is not using https. This is insecure and is not recommended')
                self.app_ingress = f'http://{self.app_ingress}'
            else:
                self.app_ingress = f'https://{self.app_ingress}'
        self.app_ingress = self.app_ingress.rstrip('/')

    def parse_allowed_api_key(self, api_key: str) -> Tuple[str, str, UserRole]:
        """
        Parses the allowed api key

        Formats: 
        - {api_key}:{client_name}:{role}
        - {api_key}:{client_name}
        - {api_key}
        """
        parts = api_key.split(':')
        if len(parts) == 3:
            return parts[0], parts[1], UserRole.parse_role(parts[2])
        elif len(parts) == 2:
            return parts[0], parts[1], UserRole.API_CLIENT
        else:
            return api_key, 'default', UserRole.API_CLIENT


    def validate_allowed_api_keys(self):
        """
        Validates the allow api keys
        """
        if self.allowed_api_keys is None: return
        if isinstance(self.allowed_api_keys, str): self.allowed_api_keys = [self.allowed_api_keys]
        # Transform it to a dict
        if isinstance(self.allowed_api_keys, list):
            allowed_api_keys = {}
            for allowed_api_key in self.allowed_api_keys:
                key, client_name, role = self.parse_allowed_api_key(allowed_api_key)
                allowed_api_keys[key] = {
                    'client_name': client_name,
                    'role': role,
                }
            # allowed = {key: UserRole.USER for key in self.allowed_api_keys}
            self.allowed_api_keys = allowed_api_keys
        elif isinstance(self.allowed_api_keys, dict):
            # allowed_api_keys = {}
            for key, value in self.allowed_api_keys.items():
                if isinstance(value, str):  
                    self.allowed_api_keys[key] = {
                        'client_name': 'default',
                        'role': UserRole.parse_role(value),
                    }
                elif isinstance(value, dict) and 'role' not in value and 'client_name' not in value:
                    self.allowed_api_keys[key] = {
                        'client_name': value.get('client_name', 'default'),
                        'role': UserRole.parse_role(value.get('role', 'API_CLIENT')),
                    }
                
                # allowed_api_keys[key] = value
            # for key in self.allowed_api_keys:
            #     if self.allowed_api_keys[key] is None:
            #         self.allowed_api_keys[key] = UserRole.USER
            #     elif self.allowed_api_keys[key] not in UserRole:
            #         raise ValueError(f'Invalid User Role: {self.allowed_api_keys[key]}')

    def validate_app_scopes(self):
        """
        Validates the app scopes
        """
        if self.app_scopes is None: 
            self.app_scopes = ['openid', 'profile', 'email']
            return
        if not isinstance(self.app_scopes, list): self.app_scopes = [self.app_scopes]
        else: self.app_scopes = list(set(self.app_scopes))

    def validate_config(self):
        """
        Handles the validation of the configuration after updates / changes
        """
        if self.has_completed_validation: return
        if self.client_id is None: raise ValueError("AuthZero Client ID must be set")
        if self.client_secret is None: raise ValueError("AuthZero Client Secret must be set")
        if self.domain is None: raise ValueError("AuthZero Domain must be set")

        # Check API Keys
        # Validate that the API Key Secret Key is 16 characters
        tmp_data = get_az_temp_data()

        if not self.api_key_secret_key:
            if self.is_production_env: raise ValueError("API Key Secret Key must be set in production")
            if not tmp_data.has_logged('api_key_secret_key'):
                self.logger.warning("Using default `AUTH_ZERO_API_SECRET_KEY` [INSECURE]")
                self.api_key_secret_key = ('abc123' * 10)[:16]
        
        elif len(self.api_key_secret_key) != 16: raise ValueError("API Key Secret Key must be 16 characters")
        
        # Validate that the API Key Access Key is 16 characters
        if not self.api_key_access_key:
            if self.is_production_env: raise ValueError("API Key Access Key must be set in production")
            if not tmp_data.has_logged('api_key_access_key'):
                self.logger.warning("Using default `AUTH_ZERO_API_KEY_ACCESS_KEY` [INSECURE]")
                self.api_key_access_key = ('321bca' * 10)[:16]
        
        elif len(self.api_key_access_key) != 16: raise ValueError("API Key Access Key must be 16 characters")
        self.validate_audiences()
        self.validate_app_ingress()
        self.validate_allowed_api_keys()
        self.validate_app_scopes()
        # Validate Session Cookie Key
        if self.session_cookie_key is None:
            if self.app_name and self.app_env: self.session_cookie_key = f'{self.app_name}-{self.app_env.name}-session'.replace(' ', '-').lower()
            elif self.app_ingress: self.session_cookie_key = f'{self.app_ingress}-session'.split('://', 1)[-1].replace(' ', '-').replace('.', '').lower()

        self.has_completed_validation = True


    @model_validator(mode = 'after')
    def validate_authzero_config(self):
        """
        Validates the AuthZero Configuration
        """
        if self.data_dir is None: self.data_dir = lib_path.joinpath('data')
        if self.app_env is None: self.app_env = AppEnv.from_module_name('authzero')
        if self.ctx is None: self.ctx = AuthZeroContext
        if not self.enabled or not self.is_enabled: return self
        self.validate_config()
        return self


    @overload
    def configure(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        audience: Optional[str] = None,
        audiences: Optional[List[str]] = None,

        apikey_header: Optional[str] = None,
        authorization_header: Optional[str] = None,
        authorization_scheme: Optional[str] = None,

        domain: Optional[str] = None,
        jwks_dict: Optional[Dict[str, Any]] = None,

        # Persistence
        cache_key_prefix: Optional[str] = None,
        data_dir: Optional[Path] = None,

        # API Keys
        api_key_prefix: Optional[str] = None,
        api_key_secret_key: Optional[str] = None,
        api_key_access_key: Optional[str] = None,
        api_key_suffix: Optional[str] = None,
        api_key_hashes: Optional[List[str]] = None,

        # Metadata
        enabled: Optional[bool] = None,
        session_enabled: Optional[bool] = None,
        enable_multi_audiences: Optional[bool] = None, # allow for multiple audiences to be used

        # API Clients
        api_client_id_header_key: Optional[str] = None,
        api_client_env_header_key: Optional[str] = None,
        api_client_api_key_prefix: Optional[str] = None,

        # App Metadata - Used to identify the app
        app_name: Optional[str] = None,
        app_env: Optional[Union[AppEnv, str]] = None,
        app_ingress: Optional[str] = None,
        **kwargs,
    ):
        """
        Configure the AuthZero Settings
        """
        ...


    def configure(
        self,
        **kwargs,
    ):
        """
        Configure the AuthZero Settings
        """
        for k,v in kwargs.items():
            if k == 'app_env':
                if isinstance(v, str): v = AppEnv(v)
            if hasattr(self, k):
                setattr(self, k, v)    
        self.has_completed_validation = False
        self.validate_config()
        return self
    


settings: AuthZeroSettings = ProxyObject(
    obj_getter = 'lazyops.libs.authzero.utils.lazy.get_az_settings',
)
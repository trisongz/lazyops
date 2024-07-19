from __future__ import annotations

import os
import datetime
from pathlib import Path
from urllib.parse import urljoin
from pydantic import PrivateAttr, model_validator, Field, AliasChoices
from lazyops.imports._pydantic import BaseSettings
from lazyops.utils.logs import logger as _logger, null_logger as _null_logger, Logger
from lazyops.libs.proxyobj import ProxyObject
from lazyops.libs.abcs.configs.types import AppEnv
from lazyops.libs.abcs.types.roles import UserRole
from lazyops.utils.helpers import timed_cache
from lazyops.libs.fastapi_utils.types.persistence import TemporaryData
from typing import Optional, List, Dict, Any, Union, Type, Tuple, Callable, overload, TYPE_CHECKING
from .base import get_kinde_temp_data, lib_path, templates_path, staticfile_path, KindeContext, KindeContextObject
from .utils import get_hashed_key, encrypt_key, decrypt_key, aencrypt_key, adecrypt_key, create_random_string, normalize_audience_name

if TYPE_CHECKING:
    import jinja2
    from kvdb import PersistentDict
    from starlette.templating import Jinja2Templates
    from kinde_sdk.kinde_api_client import GrantType
    from lazyops.libs.fastapi_utils.types.persistence import TemporaryData
    from fastapi.security.http import HTTPBase
    from fastapi.security.api_key import APIKeyHeader
    from fastapi.staticfiles import StaticFiles

def get_env_value(*envs: str, default: Optional[str] = None) -> Optional[str]:
    """
    Returns the first environment variable that is not None
    """
    def wraps(*args, **kwargs):
        for env in envs:
            value = os.getenv(env.upper(), os.getenv(env))
            if value is not None: return value
        return default
    return wraps

@timed_cache(60 * 60 * 24 * 30)
def get_current_year() -> int:
    """
    Returns the current year
    """
    return datetime.datetime.now().year


class KindeSettings(BaseSettings):
    """
    Kinde Authentication Settings
    """

    # Provides an alt to using issuer_url
    # for example, kinde-develop.us -> https://kinde-develop.us.kinde.com
    issuer_id: Optional[str] = None 
    issuer_url: Optional[str] = None

    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    mtg_client_id: Optional[str] = None
    mtg_client_secret: Optional[str] = None

    audience: Optional[str] = None
    org_code: Optional[str] = None
    enable_org_signup: Optional[bool] = None

    if TYPE_CHECKING:
        grant_type: Optional[GrantType] = GrantType.AUTHORIZATION_CODE_WITH_PKCE
    else:
        grant_type: Optional[Union[str, Any]] = "authorization_code_with_pkce"

    code_verifier: Optional[str] = Field(None, min_length = 43)
    secret_key: Optional[str] = Field(None)

    login_path: Optional[str] = '/api/auth/login'
    logout_path: Optional[str] = '/api/auth/logout'
    register_path: Optional[str] = '/api/auth/register'
    callback_path: Optional[str] = '/api/auth/callback'
    user_profile_path: Optional[str] = '/api/auth/user'
    user_profile_enabled: Optional[bool] = True
    
    docs_path: Optional[str] = '/docs'
    logout_redirect_path: Optional[str] = '/docs'

    # Rendered Paths
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    company_name: Optional[str] = None

    # Static Files
    templates_path: Optional[Path] = templates_path
    staticfile_path: Optional[Path] = staticfile_path
    staticfile_url_path: Optional[str] = '/kstatic'

    app_scopes: Optional[Union[str, List[str]]] = None

    # Persistence
    base_cache_key: Optional[str] = 'kinde'
    cache_key_prefix: Optional[str] = None
    data_dir: Optional[Path] = None
    data_expiration: Optional[int] = 60 * 60 * 24 * 30 # 30 days
    local_persistence_fallback: Optional[bool] = True


    # API Key Integration
    api_key_header: Optional[str] = "x-api-key"
    api_key_prefix: Optional[str] = "xai-"
    api_key_secret_key: Optional[str] = None
    api_key_access_key: Optional[str] = None
    api_key_suffix: Optional[str] = None
    api_key_hashes: Optional[List[str]] = None

    # API Clients
    api_client_id_header_key: Optional[str] = 'x-kd-client-id'
    api_client_env_header_key: Optional[str] = 'x-kd-client-env'
    api_client_api_key_prefix: Optional[str] = 'xaic-'

    # Expirations
    user_data_expiration: Optional[int] = 60 * 60 * 24 * 7 # 7 days
    user_session_expiration: Optional[int] = 60 * 60 * 24 * 30 # 30 days
    
    # Hook Configurations
    user_session_enabled: Optional[bool] = True
    user_request_id_enabled: Optional[bool] = True
    user_domain_source_enabled: Optional[bool] = False
    user_role_configure_enabled: Optional[bool] = True

    # Alternate Authentication
    admin_emails: Optional[List[str]] = None
    staff_email_domains: Optional[List[str]] = None

    # Metadata
    disabled: Optional[bool] = None
    session_enabled: Optional[bool] = None
    session_configure_enabled: Optional[bool] = None
    session_cookie_key: Optional[str] = None
    session_user_id_hashed: Optional[bool] = True


    # App Metadata - Used to identify the app
    app_name: Optional[str] = Field(default_factory = get_env_value('app_name'))
    app_env: Optional[Union[str, AppEnv]] = Field(default_factory = get_env_value('app_env', default = 'local'))
    app_ingress: Optional[str] = Field(default_factory = get_env_value('app_ingress', 'app_endpoint', 'app_url'))
    app_client_id: Optional[str] = None


    debug_enabled: Optional[bool] = False
    has_completed_validation: Optional[bool] = Field(None, exclude = True)
    _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)

    if TYPE_CHECKING:
        ctx: Optional[KindeContextObject] = None
        allowed_api_keys: Optional[Union[List[str], Dict[str, Dict[str, Union[str, UserRole]]]]] = None
    else:
        ctx: Optional[Any] = KindeContext
        allowed_api_keys: Optional[Union[str, List[str], Dict[str, str]]] = None


    class Config:
        env_prefix = 'KINDE_'
        case_sensitive = False
        extra = 'allow'


    @model_validator(mode = 'after')
    def validate_kinde_config(self):
        """
        Validates the Kinde Configuration
        """
        if self.issuer_id and not self.issuer_url:
            self.issuer_url = f'https://{self.issuer_id}.kinde.com'
        if self.app_env and isinstance(self.app_env, str):
            self.app_env = AppEnv.from_env(self.app_env)
        if self.grant_type and isinstance(self.grant_type, str):
            from kinde_sdk.kinde_api_client import GrantType
            self.grant_type = GrantType(self.grant_type)
        if self.data_dir is None: self.data_dir = lib_path.joinpath('data')
        if self.ctx is None: self.ctx = KindeContext
        if self.disabled or not self.is_enabled: 
            # self.logger.warning(f'Kinde Settings: {self}')
            return self
        self.validate_config()
        return self


    @property
    def is_enabled(self) -> bool:
        """
        Returns True if Kinde is enabled
        """
        if 'is_enabled' not in self._extra:
            self._extra['is_enabled'] = self.client_id is not None and \
                self.client_secret is not None and \
                self.issuer_url is not None
        return self._extra['is_enabled']
    
    @is_enabled.setter
    def is_enabled(self, value: bool):
        """
        Sets the Kinde Enabled
        """
        self._extra['is_enabled'] = value
    

    @property
    def api_key_enabled(self) -> bool:
        """
        Returns True if API Keys are Enabled
        """
        if 'api_key_enabled' not in self._extra:
            self._extra['api_key_enabled'] = self.api_key_secret_key is not None and self.api_key_access_key is not None
        return self._extra['api_key_enabled']
    
    @property
    def is_mtg_enabled(self) -> bool:
        """
        Returns True if MTG is Enabled
        """
        if 'is_mtg_enabled' not in self._extra:
            self._extra['is_mtg_enabled'] = self.mtg_client_id is not None and self.mtg_client_secret is not None
        return self._extra['is_mtg_enabled']
    

    """
    Cache Key Methods
    """

    def get_cache_key_prefix(self) -> str:
        """
        Returns the Cache Key Prefix
        """
        if self.cache_key_prefix: return self.cache_key_prefix
        if self.app_endpoint: return get_hashed_key(self.app_domain)[:8]
        if self.app_name and self.app_env: return get_hashed_key(f'{self.app_name}-{self.app_env.name}')[:8]
        raise ValueError("Unable to determine cache key prefix, please set `app_name` and `app_env` or `app_ingress`")
    
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


    """
    Persistence
    """

    @property
    def data(self) -> 'PersistentDict[str, Dict[str, Any]]':
        """
        Returns the Kinde Data via Persistent Dict
        """
        if 'data' not in self._extra:
            from .utils import get_kinde_pdict
            base_key = f'{self.base_cache_key}.'
            if self.app_name:
                app_name = self.app_name.replace(' ', '-').casefold()
                base_key += f'{app_name}.'
            elif self.app_endpoint:
                base_key += f'{normalize_audience_name(self.app_endpoint)}.'
            else: base_key += 'default.'
            base_key += self.app_env.name
            base_key = base_key.replace(' ', '_').lower().replace('..', '.')
            self._extra['data'] = get_kinde_pdict(
                base_key = base_key,
                expiration = self.data_expiration,
                data_dir = self.data_dir,
                allow_local_fallback = self.local_persistence_fallback,
            )
        return self._extra['data']


    """
    Misc Properties
    """

    @property
    def in_k8s(self) -> bool:
        """
        Returns whether the app is running in kubernetes
        """
        if 'in_k8s' not in self._extra:
            from lazyops.utils.system import is_in_kubernetes
            self._extra['in_k8s'] = is_in_kubernetes()
        return self._extra['in_k8s']
    
    @property
    def temp_data(self) -> 'TemporaryData':
        """
        Returns the temporary data
        """
        if 'temp_data' not in self._extra:
            self._extra['temp_data'] = get_kinde_temp_data()
        return self._extra['temp_data']

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


    @property
    def templates(self) -> 'Jinja2Templates':
        """
        Returns the jinja2 templates
        """
        if 'templates' not in self._extra:
            from starlette.templating import Jinja2Templates
            self._extra['templates'] = Jinja2Templates(
                directory = self.templates_path,
                enable_async = True,
            )
        return self._extra['templates']

    # @property
    # def templates(self) -> 'jinja2.Environment':
    #     """
    #     Returns the jinja2 templates
    #     """
    #     if 'templates' not in self._extra:
    #         import jinja2
    #         self._extra['templates'] = jinja2.Environment(
    #             loader = jinja2.FileSystemLoader(self.templates_path),
    #             autoescape = jinja2.select_autoescape(["html", "xml"]),
    #             enable_async = True,
    #         )
    #     return self._extra['templates']

    @property
    def current_year(self) -> int:
        """
        Returns the current year
        """
        return get_current_year()
    
    @property
    def staticfiles(self) -> 'StaticFiles':
        """
        Returns the static files
        """
        if 'staticfiles' not in self._extra:
            from fastapi.staticfiles import StaticFiles
            self._extra['staticfiles'] = StaticFiles(
                directory = self.staticfile_path,
            )
        return self._extra['staticfiles']


    """
    Endpoint Properties
    """


    @property
    def app_endpoint(self) -> str:
        """
        Returns the app ingress endpoint
        """
        if 'app_endpoint' not in self._extra:
            self._extra['app_endpoint'] = self.validate_app_endpoint(self.app_ingress)
        return self._extra['app_endpoint']
    
    @app_endpoint.setter
    def app_endpoint(self, value: str):
        """
        Sets the app ingress endpoint
        """
        self._extra['app_endpoint'] = self.validate_app_endpoint(value)
        # If this is set, clear it from extra to have it regenerated
        for k in {'login_url', 'logout_url', 'register_url', 'callback_url'}:
            _ = self._extra.pop(k, None)

    
    @property
    def app_domain(self) -> Optional[str]:
        """
        Returns the App Domain
        """
        return self.app_endpoint.replace('http://', '').replace('https://', '').rstrip('/') if self.app_endpoint else None


    @property
    def is_secure_ingress(self) -> bool:
        """
        Returns whether the ingress is secure
        """
        return self.app_endpoint.startswith("https://")

    @property
    def login_url(self) -> str:
        """
        Returns the login url
        """
        if 'login_url' not in self._extra:
            self._extra['login_url'] = urljoin(self.app_endpoint, self.login_path)
        return self._extra['login_url']
    
    @login_url.setter
    def login_url(self, value: str):
        """
        Sets the login url
        """
        self.login_path = value
        self._extra['login_url'] = urljoin(self.app_endpoint, value)

    @property
    def logout_url(self) -> str:
        """
        Returns the logout url
        """
        if 'logout_url' not in self._extra:
            self._extra['logout_url'] = urljoin(self.app_endpoint, self.logout_path)
        return self._extra['logout_url']
    
    @logout_url.setter
    def logout_url(self, value: str):
        """
        Sets the logout url
        """
        self.logout_path = value
        self._extra['logout_url'] = urljoin(self.app_endpoint, value)

    @property
    def register_url(self) -> str:
        """
        Returns the register url
        """
        if 'register_url' not in self._extra:
            self._extra['register_url'] = urljoin(self.app_endpoint, self.register_path)
        return self._extra['register_url']
    
    @register_url.setter
    def register_url(self, value: str):
        """
        Sets the register url
        """
        self.register_path = value
        self._extra['register_url'] = urljoin(self.app_endpoint, value)

    @property
    def callback_url(self) -> str:
        """
        Returns the callback url
        """
        if 'callback_url' not in self._extra:
            self._extra['callback_url'] = urljoin(self.app_endpoint, self.callback_path)
        return self._extra['callback_url']
    
    @callback_url.setter
    def callback_url(self, value: str):
        """
        Sets the callback url
        """
        self.callback_path = value
        self._extra['callback_url'] = urljoin(self.app_endpoint, value)

    @property
    def logout_redirect_url(self) -> str:
        """
        Returns the logout redirect url
        """
        if 'logout_redirect_url' not in self._extra:
            self._extra['logout_redirect_url'] = urljoin(self.app_endpoint, self.logout_redirect_path)
        return self._extra['logout_redirect_url']
    
    @logout_redirect_url.setter
    def logout_redirect_url(self, value: str):
        """
        Sets the logout redirect url
        """
        self.logout_redirect_path = value
        self._extra['logout_redirect_url'] = urljoin(self.app_endpoint, value)
    
    
    """
    Validate/Configure the Kinde Settings
    """

    def add_allowed_api_key(self, key: str, role: Optional[UserRole] = None):
        """
        Adds an allowed api key
        """
        if self.allowed_api_keys is None: self.allowed_api_keys = {}
        self.allowed_api_keys[key] = UserRole.USER if role is None else UserRole.parse_role(role)


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


    def validate_app_endpoint(self, endpoint: Optional[str] = None) -> Optional[str]:
        """
        Validates the app ingress
        """
        if endpoint is None: return
        if not endpoint.startswith('http'): 
            if 'localhost' in endpoint or '127.0.0.1' in endpoint or '0.0.0.0' in endpoint:
                if not self.temp_data.has_logged('app_ingress_validate'):
                    self.logger.warning('`app_ingress` is not using https. This is insecure and is not recommended')
                endpoint = f'http://{endpoint}'
            else:
                endpoint = f'https://{endpoint}'
        return endpoint.rstrip('/')
    

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
    

    def validate_app_scopes(self):
        """
        Validates the app scopes
        """
        if self.app_scopes is None: 
            self.app_scopes = 'openid profile email offline'
            return
        if isinstance(self.app_scopes, list): self.app_scopes = ' '.join(list(set(self.app_scopes)))

    def validate_code_challenge(self):
        """
        Validates the code challenge
        """
        if self.code_verifier is not None: return
        if not self.data.contains('code_verifier'):
            self.code_verifier = create_random_string(length = 44)
            self.data.set('code_verifier', self.code_verifier)
            if not self.temp_data.has_logged('code_verifier'):
                self.logger.info(f'Generated Code Verifier and Storing since it was not provided: {self.code_verifier}')
        else:
            self.code_verifier = self.data.get('code_verifier')

    def validate_secret_key(self):
        """
        Validates the secret key
        """
        if self.secret_key is not None: return
        if not self.data.contains('secret_key'):
            self.secret_key = create_random_string(length = 44)
            self.data.set('secret_key', self.secret_key)
            if not self.temp_data.has_logged('secret_key'):
                self.logger.info(f'Generated Secret Key and Storing since it was not provided: {self.secret_key}')
        else:
            self.secret_key = self.data.get('secret_key')

    def validate_config(self):
        """
        Handles the validation of the configuration after updates / changes
        """
        if self.has_completed_validation: return
        if self.client_id is None: raise ValueError("Kinde Client ID must be set")
        if self.client_secret is None: raise ValueError("Kinde Client Secret must be set")
        if self.issuer_url is None: raise ValueError("Kinde Issuer URL must be set")

        # Check API Keys
        # Validate that the API Key Secret Key is 16 characters
        if not self.api_key_secret_key:
            if self.is_production_env: raise ValueError("API Key Secret Key must be set in production")
            if not self.temp_data.has_logged('api_key_secret_key'):
                self.logger.warning("Using default `KINDE_API_SECRET_KEY` [INSECURE]")
                self.api_key_secret_key = ('abc123' * 10)[:16]
        
        elif len(self.api_key_secret_key) != 16: raise ValueError("API Key Secret Key must be 16 characters")
        
        # Validate that the API Key Access Key is 16 characters
        if not self.api_key_access_key:
            if self.is_production_env: raise ValueError("API Key Access Key must be set in production")
            if not self.temp_data.has_logged('api_key_access_key'):
                self.logger.warning("Using default `KINDE_API_KEY_ACCESS_KEY` [INSECURE]")
                self.api_key_access_key = ('321bca' * 10)[:16]
        
        elif len(self.api_key_access_key) != 16: raise ValueError("API Key Access Key must be 16 characters")
        
        self.validate_allowed_api_keys()
        self.validate_app_scopes()
        self.validate_code_challenge()
        self.validate_secret_key()
        
        # Validate Session Cookie Key
        if self.session_cookie_key is None:
            if self.app_name and self.app_env: self.session_cookie_key = f'{self.app_name}-{self.app_env.name}-session'.replace(' ', '-').lower()
            elif self.app_endpoint: self.session_cookie_key = f'{self.app_endpoint}-session'.split('://', 1)[-1].replace(' ', '-').replace('.', '').lower()

        self.has_completed_validation = True
        self.is_enabled = True
        # self.logger.info(f'Kinde Settings: {self}')

    @overload
    def configure(
        self,
        issuer_id: Optional[str] = None,
        issuer_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,

        audience: Optional[str] = None,
        org_code: Optional[str] = None,
        app_scopes: Optional[Union[str, List[str]]] = None,

        api_key_header: Optional[str] = None,
        
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

        # API Clients
        api_client_id_header_key: Optional[str] = None,
        api_client_env_header_key: Optional[str] = None,
        api_client_api_key_prefix: Optional[str] = None,

        # App Metadata - Used to identify the app
        app_name: Optional[str] = None,
        app_env: Optional[Union[AppEnv, str]] = None,
        app_endpoint: Optional[str] = None,
        **kwargs,
    ):
        """
        Configure the Kinde Settings
        """
        ...



    def configure(
        self,
        **kwargs,
    ):
        """
        Configure the Kinde Settings
        """
        for k,v in kwargs.items():
            if k in {'login_path', 'logout_path', 'register_path', 'callback_path'}:
                _k = k.replace('path', 'url')
                setattr(self, _k, v)
                continue

            if k == 'issuer_id':
                self.issuer_url = f'https://{v}.kinde.com'
                continue

            if k == 'app_ingress':
                self.app_endpoint = v
                continue

            if k == 'app_env':
                if isinstance(v, str): v = AppEnv(v)
            
            
            elif k == 'grant_type':
                if isinstance(v, str): 
                    from kinde_sdk.kinde_api_client import GrantType
                    v = GrantType(v)
            
            elif k == 'templates_path':
                if isinstance(v, str): v = Path(v)
                _ = self._extra.pop('templates', None)
            
            # elif k == 'issuer_id':
            #     self.issuer_url = f'https://{v}.kinde.com'
            #     continue
            
            # elif k == 'app_ingress':
            #     self.app_endpoint = v
            #     continue
            if hasattr(self, k): setattr(self, k, v)
        self.has_completed_validation = False
        self.validate_config()
        return self
    

    def get_kinde_client_config(
        self,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the Kinde Client Config
        """
        from kinde_sdk import Configuration
        from kinde_sdk.kinde_api_client import GrantType
        client_params = {
            "configuration": Configuration(
                host = self.issuer_url
            ),
            "domain": self.issuer_url,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": self.grant_type,
            "callback_url": self.callback_url,
            "scope": self.app_scopes,
            "audience": self.audience,
            "org_code": self.org_code,
        }
        if kwargs: client_params.update(kwargs)
        client_params = {k: v for k, v in client_params.items() if v is not None}
        if 'code_verifier' not in client_params and self.grant_type == GrantType.AUTHORIZATION_CODE_WITH_PKCE:
            client_params['code_verifier'] = self.code_verifier
        return client_params
    
    def get_kinde_mtg_client_config(
        self,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the Kinde MTG Client Config
        """
        from kinde_sdk import Configuration
        from kinde_sdk.kinde_api_client import GrantType
        client_params = {
            "configuration": Configuration(
                host = self.issuer_url
            ),
            "domain": self.issuer_url,
            "client_id": self.mtg_client_id or self.client_id,
            "client_secret": self.mtg_client_secret or self.client_secret,
            "grant_type": GrantType.CLIENT_CREDENTIALS,
            "callback_url": self.callback_url,
            "audience": urljoin(self.issuer_url, 'api'),
            "org_code": self.org_code,
        }
        if kwargs: client_params.update(kwargs)
        client_params = {k: v for k, v in client_params.items() if v is not None}
        return client_params


settings: KindeSettings = ProxyObject(
    obj_getter = 'lazyops.libs.kinde.utils.get_kinde_settings',
)
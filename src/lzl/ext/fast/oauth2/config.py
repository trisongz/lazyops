from __future__ import annotations

import os
import yaml
import base64
from pathlib import Path
from lzo.types import BaseSettings, eproperty
from lzl.logging import logger, null_logger, Logger
from lzl.load import lazy_import
from pydantic import PrivateAttr, model_validator, field_validator, Field
from urllib.parse import urlparse, urlunparse, urljoin, parse_qsl, urlencode, quote
from typing import Any, Dict, Optional, Union, Tuple, TYPE_CHECKING, List, Type, Callable, Annotated, Generator

if TYPE_CHECKING:
    from fastapi import FastAPI
    from .manager import OAuth2Manager
    from .types.user import APIKeyUser
    from ..middlewares.persistent import PersistentMiddleware
    from .middleware import OAuth2Middleware
    from .backend import OAuth2Backend
    from lzl.io import JsonSerializer
    from lzl.io.persistence import TemporaryData
    from Cryptodome.Cipher._mode_ecb import EcbMode

here = Path(__file__).parent

_default_state_kws = {
    'token': '_token',
    'user': '_user',
    'apikey': '_apikey',
}

class OAuth2Config(BaseSettings):
    """
    The Primary OAuth2 Configuration
    """

    config_file: Optional[Path] = None
    config_dir: Optional[Path] = None

    header: Optional[str] = "Authorization"
    scheme: Optional[str] = "Bearer"

    domains: Optional[List[str]] = None
    debug_enabled: Optional[bool] = None

    # Session Configurations
    session_disabled: Optional[bool] = None
    if TYPE_CHECKING:
        session_class: Optional[Union[Type['PersistentMiddleware'], str]] = None
    else:
        session_class: Optional[Any] = None
    
    session_config: Optional[Dict[str, Any]] = None
    session_oauth2_key: Optional[str] = '_oauth2'
    session_state_kws: Optional[Dict[str, str]] = Field(default_factory = lambda: _default_state_kws)

    # Middleware Configurations
    if TYPE_CHECKING:
        manager_class: Optional[Union[Type['OAuth2Manager'], str]] = None
        middleware_class: Optional[Union[Type['OAuth2Middleware'], str]] = None
        backend_class: Optional[Union[Type['OAuth2Backend'], str]] = None
    else:
        manager_class: Optional[Any] = None
        middleware_class: Optional[Any] = None
        backend_class: Optional[Any] = None

    # Enrichment Configurations
    enable_user_info: Optional[bool] = None
    enable_query_params: Optional[bool] = None
    auth_query_param: Optional[str] = "token"
    api_key_query_param: Optional[str] = "apikey"

    # API Key Configurations
    api_keys_enabled: Optional[bool] = True
    allowed_api_keys: Optional[List[str]] = Field(default_factory = list)
    api_key_access_key: Optional[str] = None
    api_key_secret_key: Optional[str] = None

    # User Configurations
    staff_emails: Optional[List[str]] = Field(default_factory = list)
    admin_emails: Optional[List[str]] = Field(default_factory = list)
    sa_emails: Optional[List[str]] = Field(default_factory = list)

    staff_email_domains: Optional[List[str]] = Field(default_factory = list)
    admin_email_domains: Optional[List[str]] = Field(default_factory = list)
    sa_email_domains: Optional[List[str]] = Field(default_factory = list)

    disabled_paths: Optional[List[str]] = Field(default_factory = list)


    class Config:
        env_prefix = "OAUTH2_"
        arbitrary_types_allowed = True
        extra = 'allow'

    
    @property
    def autologger(self) -> 'Logger':
        """
        Returns the autologger
        """
        return logger if self.debug_enabled else null_logger


    @eproperty
    def manager(self) -> 'OAuth2Manager':
        """
        Returns the OAuth2 Manager
        """
        logger.info(f'Creating OAuth2 Manager: {self.manager_class}')
        return self.manager_class(config = self)
    
    @eproperty
    def aes_obj(self) -> Callable[..., 'EcbMode']:
        """
        Returns the AES Object
        """
        from lzl.ext.fast.utils.aes import create_aes_object
        return create_aes_object(self.api_key_secret_key, self.api_key_access_key)
    
    @eproperty
    def serializer(self) -> 'JsonSerializer':
        """
        Returns the serializer
        """
        from lzl.ext.fast.utils import serializer
        return serializer

    @eproperty
    def api_key_users(self) -> Dict[str, 'APIKeyUser']:
        """
        Returns the API Key Users
        """
        if 'api_key_users' not in self._extra:
            self._extra['api_key_users'] = self.parse_api_key_users(self.allowed_api_keys)
        return self._extra['api_key_users']

    def get_manager(self) -> 'OAuth2Manager':
        """
        Returns the OAuth2 Manager
        """
        # self._extra['mtg_class'] = mtg
        # logger.info(f'Creating OAuth2 Manager: {mtg}')
        return self.manager
    
    def parse_api_key_users(
        self, 
        api_keys: List[Union[str, Dict[str, Any]]],
    ) -> Dict[str, 'APIKeyUser']:
        """
        Parses the api key users
        """
        from .types.user import APIKeyUser
        api_key_users: Dict[str, 'APIKeyUser'] = {}
        for item in api_keys:
            api_key = APIKeyUser.parse_string(item) if isinstance(item, str) else APIKeyUser(**item)
            api_key_users[api_key.api_key] = api_key
        return api_key_users

    """
    Configuration Loaders
    """

    def load_domains(self, domains: Union[str, List[str], Dict[str, Union[str, List[str]]]]) -> None:
        """
        Loads the domains
        """
        if isinstance(domains, dict):
            domains = self.app_env.select(domains)
        if isinstance(domains, str): domains = [domains]
        if not self.domains: self.domains = []
        self.domains.extend(domains)
        self.domains = list(set(self.domains))


    def load_api_key_settings(self, data: Dict[str, Any]) -> None:
        """
        Loads the API Key Settings
        """
        if 'enabled' in data: self.api_keys_enabled = data['enabled']
        if data.get('access_key'): 
            self.api_key_access_key = data['access_key']
            assert len(self.api_key_access_key) == 16, "Invalid Access Key Length, must be 16 bytes"
        if data.get('secret_key'): 
            self.api_key_secret_key = data['secret_key']
            assert len(self.api_key_secret_key) in {32, 24, 16}, "Invalid Secret Key Length, must be 16, 24, or 32 bytes"
        if data.get('users'): self.api_key_users = self.parse_api_key_users(data['users'])
        logger.info(f'Loaded |g|{len(self.api_key_users)}|e| API Key Users', colored = True)

    def load_session_settings(self, data: Dict[str, Any]) -> None:
        """
        Loads the session settings
        """
        if 'disabled' in data: self.session_disabled = data['disabled']
        if data.get('config'): 
            self.session_config = data['config']
            if self.session_config.get('session_cookie') and '{env}' in self.session_config['session_cookie']:
                self.session_config['session_cookie'] = self.session_config['session_cookie'].replace('{env}', self.app_env.name)
            if self.session_config.get('state_cookie') and '{env}' in self.session_config['state_cookie']:
                self.session_config['state_cookie'] = self.session_config['state_cookie'].replace('{env}', self.app_env.name)
        if data.get('class'):
            self.session_class = lazy_import(data['class'])
        if data.get('state_kws'):
            self.session_state_kws.update(data['state_kws'])

    def load_middleware_settings(self, data: Union[str, Dict[str, Any]]) -> None:
        """
        Loads the middleware settings
        """
        if data.get('class'): self.middleware_class = lazy_import(data['class'])
        if data.get('backend'): self.backend_class = lazy_import(data['backend'])
        if 'user_info' in data and data['user_info'] is not None:
            self.enable_user_info = data['user_info']
        if 'query_params' in data and data['query_params'] is not None:
            query_data: Dict[str, Any] = data['query_params']
            self.enable_query_params = query_data.get('enabled', True)
            if query_data.get('auth'): self.auth_query_param = query_data['auth']
            if query_data.get('api_key'): self.api_key_query_param = query_data['api_key']

    def load_user_settings(self, users: Union[str, List[str], Dict[str, Union[str, List[str]]]]) -> None:
        """
        Loads the user settings
        """
        if users.get('admin_emails'):
            if not self.admin_emails: self.admin_emails = []
            self.admin_emails.extend(users['admin_emails'])
            self.admin_emails = list(set(self.admin_emails))
        if users.get('staff_emails'):
            if not self.staff_emails: self.staff_emails = []
            self.staff_emails.extend(users['staff_emails'])
            self.staff_emails = list(set(self.staff_emails))
        if users.get('sa_emails'):
            if not self.sa_emails: self.sa_emails = []
            self.sa_emails.extend(users['sa_emails'])
            self.sa_emails = list(set(self.sa_emails))
        if users.get('admin_email_domains'):
            if not self.admin_email_domains: self.admin_email_domains = []
            self.admin_email_domains.extend(users['admin_email_domains'])
            self.admin_email_domains = list(set(self.admin_email_domains))
        if users.get('staff_email_domains'):
            if not self.staff_email_domains: self.staff_email_domains = []
            self.staff_email_domains.extend(users['staff_email_domains'])
            self.staff_email_domains = list(set(self.staff_email_domains))
        if users.get('sa_email_domains'):
            if not self.sa_email_domains: self.sa_email_domains = []
            self.sa_email_domains.extend(users['sa_email_domains'])
            self.sa_email_domains = list(set(self.sa_email_domains))


    def load_from_config_file(self, config_file: Path) -> None:
        """
        Loads the config from a file
        """
        data: Dict[str, Union[Dict[str, Any], List[Dict[str, Any]], Any]] = yaml.safe_load(config_file.read_text())
        if data.get('manager'):
            self.manager_class = lazy_import(data['manager'])
        if data.get('session'): self.load_session_settings(data['session'])
        if data.get('api_keys'): self.load_api_key_settings(data['api_keys'])
        if data.get('users'): self.load_user_settings(data['users'])
        if data.get('domains'): self.load_domains(data['domains'])
        if data.get('providers'):
            self.manager.load_providers(data['providers'])
        if data.get('routes'): self.manager.update_routes(data['routes'])
        if data.get('middleware'): self.load_middleware_settings(data['middleware'])
        if 'debug_enabled' in data: self.debug_enabled = data['debug_enabled']
        # if data.get('routes'): self.manager.routes.update(data['routes'])


    """
    Helpers
    """

    def encrypt_api_key_data(self, data: Dict[str, Any]) -> str:
        """
        Encrypts the API Key Data
        """
        return base64.b64encode(self.aes_obj().encrypt(self.serializer.dumps(data).encode('ascii'))).decode()
    

    def decrypt_api_key_data(self, key: str) -> Dict[str, Any]:
        """
        Decrypts the API Key Data
        """
        return self.serializer.loads(self.aes_obj().decrypt(base64.b64decode(key)))

    
    @model_validator(mode = 'after')
    def validate_oauth_config(self):
        """
        Validates the config
        """
        if self.config_file:
            # Glob the config file
            if '*' in self.config_file.name:
                for config_file in self.config_file.parent.glob(self.config_file.name):
                    self.load_from_config_file(config_file)
            elif self.config_file.exists():
                self.load_from_config_file(self.config_file)
        
        if self.config_dir:
            # Glob the config dir for any yaml files
            for config_file in self.config_dir.glob('*.yaml'):
                self.load_from_config_file(config_file)

        if not self.session_disabled and not self.session_class:
            from ..middlewares.persistent import PersistentMiddleware
            self.session_class = PersistentMiddleware
        if not self.middleware_class:
            from .middleware import OAuth2Middleware
            self.middleware_class = OAuth2Middleware
        if not self.backend_class:
            from .backend import OAuth2Backend
            self.backend_class = OAuth2Backend
        
        if not self.manager_class:
            from .manager import OAuth2Manager
        elif isinstance(self.manager_class, str):
            self.manager_class = lazy_import(self.manager_class)
        return self
    
    @property
    def provider_pattern(self) -> str:
        """
        Returns the provider pattern

        '^(google|kinde|auth0)$'
        """
        if 'provider_pattern' not in self._extra:
            base_pattern = '|'.join(list(self.manager.providers.keys()))
            self._extra['provider_pattern'] = f'^({base_pattern})$'
        return self._extra['provider_pattern']
    
    @property
    def app(self) -> 'FastAPI':
        """
        Returns the app
        """
        return self._extra.get('app')
    
    @app.setter
    def app(self, value: 'FastAPI') -> None:
        """
        Sets the app
        """
        self._extra['app'] = value

    @property
    def temp_data(self) -> 'TemporaryData':
        """
        Returns the temporary data
        """
        if 'temp_data' not in self._extra:
            from lzl.io.persistence import TemporaryData
            filedir = os.getenv('OAUTH2_TEMP_DATA_DIR', here.joinpath('data'))
            self._extra['temp_data'] = TemporaryData(
                filedir = filedir,
                filepath = '_oauth2.json',
            )
        return self._extra['temp_data']
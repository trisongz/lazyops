from __future__ import annotations

import yaml
from pathlib import Path
from lzo.types import BaseSettings, eproperty
from lazyops.libs.abcs.types.persistence import TemporaryData
from pydantic import PrivateAttr, model_validator, field_validator, Field
from urllib.parse import urlparse, urlunparse, urljoin, parse_qsl, urlencode, quote
from typing import Any, Dict, Optional, Union, Tuple, TYPE_CHECKING, List, Type, Annotated, Generator

if TYPE_CHECKING:
    from fastapi import FastAPI
    from .manager import OAuth2Manager

here = Path(__file__).parent

class OAuth2Settings(BaseSettings):
    """
    The Primary OAuth2 Settings
    """

    config_file: Optional[Path] = None
    header: Optional[str] = "Authorization"
    scheme: Optional[str] = "Bearer"

    domains: Optional[List[str]] = None

    # Session Configurations
    session_enabled: Optional[bool] = None

    # User Configurations
    staff_emails: Optional[List[str]] = Field(default_factory = list)
    admin_emails: Optional[List[str]] = Field(default_factory = list)
    sa_emails: Optional[List[str]] = Field(default_factory = list)

    staff_email_domains: Optional[List[str]] = Field(default_factory = list)
    admin_email_domains: Optional[List[str]] = Field(default_factory = list)
    sa_email_domains: Optional[List[str]] = Field(default_factory = list)


    class Config:
        env_prefix = "OAUTH2_"
        arbitrary_types_allowed = True
        extra = 'allow'

    
    @eproperty
    def manager(self) -> 'OAuth2Manager':
        """
        Returns the OAuth2 Manager
        """
        from .manager import OAuth2Manager
        return OAuth2Manager(settings = self)
    
    def get_manager(self) -> 'OAuth2Manager':
        """
        Returns the OAuth2 Manager
        """
        return self.manager

    def load_domains(self, domains: Union[str, List[str], Dict[str, Union[str, List[str]]]]) -> None:
        """
        Loads the domains
        """
        if isinstance(domains, dict):
            domains = self.app_env.select(domains)
        if isinstance(domains, str): domains = [domains]
        self.domains = domains

    def load_user_settings(self, users: Union[str, List[str], Dict[str, Union[str, List[str]]]]) -> None:
        """
        Loads the user settings
        """
        if users.get('admin_emails'):
            self.admin_emails = users['admin_emails']
        if users.get('staff_emails'):
            self.staff_emails = users['staff_emails']
        if users.get('sa_emails'):
            self.sa_emails = users['sa_emails']
        if users.get('admin_email_domains'):
            self.admin_email_domains = users['admin_email_domains']
        if users.get('staff_email_domains'):
            self.staff_email_domains = users['staff_email_domains']
        if users.get('sa_email_domains'):
            self.sa_email_domains = users['sa_email_domains']


    def load_from_config_file(self, config_file: Path) -> None:
        """
        Loads the config from a file
        """
        data: Dict[str, Union[Dict[str, Any], List[Dict[str, Any]], Any]] = yaml.safe_load(config_file.read_text())
        if 'session_enabled' in data:
            self.session_enabled = data['session_enabled']
        if data.get('users'): self.load_user_settings(data['users'])
        if data.get('domains'): self.load_domains(data['domains'])
        if data.get('providers'):
            self.manager.load_providers(data['providers'], domains = self.domains)
        if data.get('routes'): self.manager.routes.update(data['routes'])

    
    @model_validator(mode = 'after')
    def validate_oauth_config(self):
        """
        Validates the config
        """
        if self.config_file and self.config_file.exists():
            self.load_from_config_file(self.config_file)
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
            self._extra['temp_data'] = TemporaryData(
                filepath = here.joinpath('data', 'authz.tmp.json'),
            )
        return self._extra['temp_data']
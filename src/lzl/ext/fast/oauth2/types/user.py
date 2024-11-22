from __future__ import annotations


# from starlette.authentication import BaseUser
from lzo.types import Literal, BaseModel, field_validator, Field, eproperty, PrivateAttr
from lzl.ext.fast.types.roles import UserRole
from typing import Optional, Dict, Any, List, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..providers import ProviderClientT, ProviderTokenT
    from ..manager import OAuth2Manager
    from .token import OAuth2Token, AccessToken, IDToken
    from fastapi import Request
    

AuthMethod = Literal['authentication', 'apikey', 'apikey_user', 'session', 'state', None]


class APIKeyUser(BaseModel):
    """
    A Predefined API Key User
    """
    identity: str
    api_key: str
    role: Union[str, int, UserRole]
    email: Optional[str] = None
    allowed_envs: Optional[List[str]] = Field(default_factory = list)
    allowed_domains: Optional[List[str]] = Field(default_factory = list)
    scopes: Optional[List[str]] = Field(default_factory = list)
    provider: Optional[str] = None
    provider_id: Optional[str] = None

    @field_validator("role")
    def validate_role(cls, v: Union[str, int, UserRole]) -> UserRole:
        """
        Validates the role
        """
        return UserRole.parse_role(v) if isinstance(v, (str, int)) else v

    def has_allowed_env(self, env: str) -> bool:
        """
        Checks if the user has an allowed environment
        """
        if not self.allowed_envs: return True
        return True if '*' in self.allowed_envs else env in self.allowed_envs
    
    def has_allowed_domain(self, domain: str) -> bool:
        """
        Checks if the user has an allowed domain
        """
        if not self.allowed_domains: return True
        if '://' in domain: domain = domain.split('://', 1)[-1]
        return True if '*' in self.allowed_domains else domain in self.allowed_domains
    

    @classmethod
    def parse_string(cls , value: str) -> APIKeyUser:
        """
        Parses the string
        - <identity>:<api_key>
        - <identity>:<api_key>:role=<role>
        - <identity>:<api_key>:role=<role>:email=<email>
        - <identity>:<api_key>:role=<role>:email=<email>:allowed_envs=<allowed_envs>
        """
        parts = value.split(':')
        data = {
            'identity': parts[0],
            'api_key': parts[1],
            'role': UserRole.USER,
        }
        parts = parts[2:]
        for part in parts:
            key, value = part.split('=', 1)
            if key == 'role':
                data['role'] = UserRole.parse_role(value)
                continue
            if key == 'email':
                data['email'] = value
                continue
            if key == 'provider':
                data['provider'] = value
                continue
            if key in {
                'scopes', 'allowed_envs', 'allowed_apps', 'allowed_domains'
            }:
                data[key] = value.split(',')
                continue
        return cls(**data)

if TYPE_CHECKING:
    TokenT = Union[AccessToken, IDToken, OAuth2Token, APIKeyUser, ProviderTokenT]

class UserMixin(BaseModel):
    """
    User Mixin
    """
    method: Optional[AuthMethod] = None
    if TYPE_CHECKING:
        token: Optional['TokenT'] = None
    else:
        token: Optional[Any] = None
    
    # apikey: Optional[str] = None
    data: Optional[Union[Dict[str, Any], Any]] = None
    
    is_admin: Optional[bool] = False
    is_staff: Optional[bool] = False
    is_service_account: Optional[bool] = False

    roles: Optional[List[Union[str, UserRole, Dict[str, str]]]] = None
    provider: Optional[str] = None

    # _extra: Dict[str, Any] = {}

    @eproperty
    def apikey(self) -> Optional[str]:
        """
        Returns the API Key
        """
        return self._extra.get('apikey')

    @property
    def is_authenticated(self) -> bool:
        """
        Returns True if the User is authenticated
        """
        return self.method is not None
    
    @property
    def display_name(self) -> str:
        """
        Returns the User's Display Name
        """
        if not self.is_authenticated: return ""
    
    @property
    def identity(self) -> Optional[str]:
        """
        Returns the Identity
        """
        return self.token.identity if self.is_authenticated else None

    @property
    def provider_id(self) -> Optional[str]:
        """
        Returns the Provider ID
        """
        if not self.is_authenticated: return None
        if self.method == 'apikey_user':
            return self.token.provider_id
        return self.token.identity
    
    @eproperty
    def email(self) -> Optional[str]:
        """
        Returns the User's Email
        """
        if not self.is_authenticated: return None
        if self.data and self.data.get('email'): return self.data.get('email')
        if self.token.email: return self.token.email
        if self.data:
            return self.data.get('preferred_email', self.data.get('email'))
        return None
    
    @email.setter
    def email(self, value: str):
        """
        Sets the User's Email
        """
        self._extra['email'] = value
        self.data['email'] = value

    @eproperty
    def email_domain(self) -> Optional[str]:
        """
        Returns the User's Email Domain
        """
        if not self.is_authenticated: return None
        if self.data and self.data.get('email_domain'): return self.data.get('email_domain')
        if hasattr(self.token, 'hd'): return self.token.hd
        if hasattr(self.token, 'email_domain'): return self.token.email_domain
        return self.email.split('@', 1)[-1] if self.email else None
    
    @email_domain.setter
    def email_domain(self, value: str):
        """
        Sets the User's Email Domain
        """
        self._extra['email_domain'] = value
        self.data['email_domain'] = value
        
    @eproperty
    def scopes(self) -> Optional[List[str]]:
        """
        Returns the User's Scopes
        """
        if not self.is_authenticated: return []
        if self.data and self.data.get('scopes'): return self.data.get('scopes')
        if self.token.scopes: return self.token.scopes
        return self.data.get('scopes') if self.data and self.data.get('scopes') else []
    
    @scopes.setter
    def scopes(self, value: List[str]):
        """
        Sets the User's Scopes
        """
        self._extra['scopes'] = value
        self.data['scopes'] = value

    def has_role(self, role: Union[str, int, UserRole]) -> bool:
        """
        Checks if the user has a role
        """
        if not self.is_authenticated: return False
        if not self.roles: return False
        if isinstance(self.roles[0], str): return role in self.roles
        if isinstance(self.roles[0], dict):
            return any(role in role['name'] for role in self.roles)
        if isinstance(self.roles[0], UserRole):
            return any(role >= role for role in self.roles)
        return False

    def add_role(self, role: Union[str, UserRole]):
        """
        Adds a role
        """
        if hasattr(self, f'is_{role}'): setattr(self, f'is_{role}', True)
        if isinstance(role, str): role = UserRole.parse_role(role)
        if not self.roles: self.roles = []
        if role not in self.roles: self.roles.append(role)

    def get_user_info(self) -> Dict[str, Any]:
        """
        Returns the User Info
        """
        return self.data

    def raise_if_not_authenticated(self):
        """
        Raises if the user is not authenticated
        """
        if not self.is_authenticated: 
            from .errors import NotAuthenticatedError
            raise NotAuthenticatedError()

    def __bool__(self) -> bool:
        """
        Returns True if the user is authenticated
        """
        return self.is_authenticated



class UnauthenticatedUser(UserMixin):
    """
    The Unauthenticated User
    """


class OAuth2User(UserMixin):
    """
    The OAuth2 User
    """
    _apikey: Optional[str] = PrivateAttr(None)
    
    @classmethod
    def initialize(
        cls,
        token: Optional['TokenT'] = None,
        provider: Optional['ProviderClientT'] = None,
        manager: Optional['OAuth2Manager'] = None,
        apikey: Optional[str] = None,
        **kwargs,
    ) -> 'OAuth2User':
        """
        Initializes the OAuth2 User
        """
        new = cls(
            token = token,
        )
        if provider: 
            new.client = provider
            new.provider = provider.name
        if manager: new.manager = manager
        new._apikey = apikey
        return new


    @eproperty
    def manager(self) -> 'OAuth2Manager':
        """
        Returns the OAuth2 Manager
        """
        return self._extra.get('manager')
    
    @eproperty
    def client(self) -> 'ProviderClientT':
        """
        Returns the Provider Client
        """
        return self._extra.get('client')

    async def postinit(self, request: Optional['Request'] = None, **kwargs):
        """
        Post Init
        """
        if not self.is_authenticated: return
        if self.manager.config.enable_user_info:
            await self.retrieve_user_info()
        if self.client is not None: 
            await self.client.set_user_data(self)
        await self.configure_perms()

    async def retrieve_user_info(self):
        """
        Retrieves the User Info
        """
        if self.client is None or self.client.config.user_info_retrieve_disabled: return
        # user_data = await self.client.afetch_user_info(self.provider_id)
        user_data = await self.client.afetch_user_info(self)
        if user_data: self.data = user_data

    async def configure_perms(self):
        """
        Configures the Permissions
        """
        if self.email:
            if self.email in self.manager.config.admin_emails:
                self.add_role('admin')
            elif self.email in self.manager.config.staff_emails:
                self.add_role('staff')
            elif self.email in self.manager.config.sa_emails:
                self.add_role('service_account')
            
        if self.email_domain:
            if self.email_domain in self.manager.config.admin_email_domains:
                self.add_role('admin')
            elif self.email_domain in self.manager.config.staff_email_domains:
                self.add_role('staff')
            elif self.email_domain in self.manager.config.sa_email_domains:
                self.add_role('service_account')
            

    def get_user_info(self) -> Dict[str, Any]:
        """
        Returns the User Info
        """
        data = {
            'method': self.method,
            'provider': self.provider,
            'provider_id': self.provider_id,
            'user': {
                'identity': self.identity,
                'email': self.email,
                'roles': self.roles,
                'scopes': self.scopes,
            },
            'role_types': {
                'is_admin': self.is_admin,
                'is_staff': self.is_staff,
                'is_service_account': self.is_service_account,
            },
        }
        if self.apikey: data['apikey'] = self.apikey
        if self.method == 'authentication': data['authorization'] = self.token.value
        if self.data: data['user'].update(self.data)
        return data
    
    @property
    def apikey(self) -> Optional[str]:
        """
        Returns the API Key
        """
        if 'apikey' not in self._extra:
            if self._apikey: self._extra['apikey'] = self._apikey
            else: self._extra['apikey'] = self.manager.encrypt_api_key(
                {
                    'identity': self.provider_id,
                    'provider': self.provider,
                }
            )
        return self._extra['apikey']


    @property
    def display_name(self) -> str:
        """
        Returns the User's Display Name
        """
        if not self.is_authenticated: return ""
        return self.data.get('name', self.data.get('given_name', '') + ' ' + self.data.get('family_name', ''))

    
    async def alogout(self):
        """
        Logs the User Out
        """
        if not self.is_authenticated: return

    @classmethod
    async def afrom_authorization(
        cls,
        token: 'TokenT',
        provider: 'ProviderClientT',
        manager: 'OAuth2Manager',
        request: 'Request',
        **kwargs,
    ) -> 'OAuth2User':
        """
        Creates the OAuth2 User from an Authorization
        """
        if token._token_type != 'oauth2_token':
            token = provider.config.oauth2_token_class(**{token._token_type: token})
            token.set_provider(provider.name)
        new = cls.initialize(token = token, provider = provider, manager = manager)
        new.method = 'authorization'
        await new.postinit(request = request)
        return new


    @classmethod
    async def afrom_session(
        cls,
        token: 'TokenT',
        provider: 'ProviderClientT',
        manager: 'OAuth2Manager',
        request: 'Request',
        **kwargs,
    ) -> 'OAuth2User':
        """
        Creates the OAuth2 User from a Session
        """
        new = cls.initialize(token = token, provider = provider, manager = manager)
        new.method = 'session'
        await new.postinit( request = request)
        return new
    
    @classmethod
    async def afrom_api_key_user(
        cls,
        api_key_user: 'APIKeyUser',
        provider: 'ProviderClientT',
        manager: 'OAuth2Manager',
        request: 'Request',
        apikey: str,
        **kwargs,
    ) -> 'OAuth2User':
        """
        Creates the OAuth2 User from an API Key User
        """
        new = cls.initialize(token = api_key_user, provider = provider, manager = manager, apikey = apikey)
        new.method = 'apikey_user'
        new.roles = [api_key_user.role] if api_key_user.role else []
        await new.postinit( request = request)
        return new
    

    @classmethod
    async def afrom_api_key(
        cls,
        token: 'TokenT',
        provider: 'ProviderClientT',
        manager: 'OAuth2Manager',
        request: 'Request',
        apikey: str,
        **kwargs,
    ) -> 'OAuth2User':
        """
        Creates the OAuth2 User from an API Key
        """
        new = cls.initialize(token = token, provider = provider, manager = manager, apikey = apikey)
        new.method = 'apikey'
        await new.postinit( request = request)
        return new

    def _refresh_from_state(
        self,
        provider: 'ProviderClientT',
        manager: 'OAuth2Manager',
        token: Optional['TokenT'] = None,
        apikey: Optional[str] = None,
        **kwargs,
    ):
        """
        Helper method to refresh the user from state
        """
        self.client = provider
        self.manager = manager
        self.method = 'state'
        if token is not None: self.token = token
        if apikey is not None: self._apikey = apikey
from __future__ import annotations

import os
import abc
import base64
import hashlib
from lzl import load
from lzl.api import aiohttpx
from lzl.types import eproperty
from lzl.logging import logger, Logger
from urllib.parse import urljoin, urlencode
from .token import OAuth2Token
from typing import Optional, Union, Dict, Any, List, Type, Generator, TYPE_CHECKING

if load.TYPE_CHECKING:
    import jwt
else:
    jwt = load.LazyLoad("jwt", install_missing=True, install_options={'package': 'pyjwt'})

if TYPE_CHECKING:
    from lzl.io import PersistentDict
    from jwt import PyJWKClient
    from .config import BaseOAuth2Config
    from .user import OAuth2User


class M2MTokenAuth(aiohttpx.Auth):
    """
    M2M Token Auth
    """
    def __init__(
        self,
        client: 'BaseOAuth2Client',
    ):
        """
        Initializes the M2M Token Auth
        """
        self.client = client
        self.token: Optional[OAuth2Token] = None
        self.token_key = f'm2m:{self.client.config.m2m_client_id}'


    def fetch_or_refresh_token(self):
        """
        Fetches the token
        """
        if self.token is None and self.client.data.contains(self.token_key):
            self.token = self.client.data.get(self.token_key)
        
        if self.token is None or self.token.is_expired:
            token_data = self.client.fetch_m2m_token()
            self.token = self.client.parse_token_payload(token_data)
            self.client.data.set(self.token_key, self.token)
            logger.info(f'Refreshed M2M Token for |g|{self.token_key}|e|', colored = True, prefix = self.client.name)
        

    @property
    def authorization(self) -> str:
        """
        Returns the authorization
        """
        self.fetch_or_refresh_token()
        return self.token.access_token.value


    def auth_flow(self, request: aiohttpx.Request) -> Generator[aiohttpx.Request, aiohttpx.Response, None]:
        """
        Execute the authentication flow.

        To dispatch a request, `yield` it:

        ```
        yield request
        ```

        The client will `.send()` the response back into the flow generator. You can
        access it like so:

        ```
        response = yield request
        ```

        A `return` (or reaching the end of the generator) will result in the
        client returning the last response obtained from the server.

        You can dispatch as many requests as is necessary.
        """
        request.headers['Authorization'] = f'Bearer {self.authorization}'
        yield request


class BaseOAuth2Client(abc.ABC):
    """
    Base Auth Client
    """
    name: Optional[str] = None
    _extra: Dict[str, Any] = {}

    
    def __init__(
        self, 
        config: Optional['BaseOAuth2Config'] = None,
        **kwargs,
    ):
        """
        Initializes the OAuth Client
        """
        self.config = config if config is not None else self.config_class(**kwargs)
        if self.config.name: self.name = self.config.name
        elif self.name: self.config.name = self.name
        self.init_oauth_config(**kwargs)
        self.post_init(**kwargs)


    """
    Initialization Methods
    """

    def init_oauth_config(self, **kwargs):
        """
        Initialize the config
        """
        pass


    def post_init(self, **kwargs):
        """
        Post Init
        """
        pass


    """
    Properties
    """

    @property
    def data(self) -> 'PersistentDict[str, OAuth2Token]': 
        """
        Returns the data
        """
        if 'data' not in self._extra:
            from lzl.io.persistence import PersistentDict
            base_key = self.config.cache_base_key or \
                f'lzl.oauth.client.{self.name}.{self.config.client_id}'
            self._extra['data'] = PersistentDict(
                base_key = base_key,
                expiration = self.config.cache_expiration, # 3 months
                serializer = 'json',
                url = os.getenv('OAUTH_REDIS_URL'),
            )
        return self._extra['data']

    @property
    def refresh_data(self) -> 'PersistentDict[str, str]':
        """
        Returns the refresh data
        """
        if 'refresh_data' not in self._extra:
            self._extra['refresh_data'] = self.data.get_child('refresh')
        return self._extra['refresh_data']

    @eproperty
    def client(self) -> 'aiohttpx.Client':
        """
        Returns the aiohttpx client
        """
        return aiohttpx.Client()


    @property
    def m2m_token_auth(self) -> Optional[M2MTokenAuth]:
        """
        Returns the m2m token auth
        """
        if self.config.m2m_enabled and 'm2m_token_auth' not in self._extra:
            self._extra['m2m_token_auth'] = M2MTokenAuth(
                data = self.data,
                client = self,
            )
        return self._extra.get('m2m_token_auth')


    @property
    def m2m_client(self) -> Optional[aiohttpx.Client]:
        """
        Returns the M2M client
        """
        if self.config.m2m_enabled and 'm2m_client' not in self._extra:
            self._extra['m2m_client'] = aiohttpx.Client(
                base_url = self.config.issuer_url,
                auth = self.m2m_token_auth,
            )
        return self._extra.get('m2m_client')

    @eproperty
    def config_class(self) -> Type['BaseOAuth2Config']:
        """
        Returns the Config Class
        """
        raise NotImplementedError

    @eproperty
    def jwt_client(self) -> Optional['PyJWKClient']:
        """
        Returns the jwt client
        """
        return jwt.PyJWKClient(self.config.jwt_url)

    @eproperty
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        return logger
    
    """
    Primary Auth Methods
    """

    def get_auth_url(
        self, 
        redirect_url: str,
        scope: Optional[str] = None,
        redirect_params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Returns the auth url
        """
        if redirect_params:
            redirect_url = self.encode_params_to_url(redirect_params, redirect_url)
        params = self.config.get_auth_params(redirect_url = redirect_url, scope = scope, **kwargs)
        return self.encode_params_to_url(params, self.config.authorization_endpoint)

    def fetch_token(
        self,
        code: str,
        redirect_url: str,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the token
        """
        params = self.config.get_fetch_token_params(code = code, redirect_url = redirect_url, **kwargs)
        response = self.client.post(
            url = self.config.token_endpoint,
            headers = self.config.get_headers('token'),
            data = params,
        )
        return response.json()
    
    async def afetch_token(
        self,
        code: str,
        redirect_url: str,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the token
        """
        params = self.config.get_fetch_token_params(code = code, redirect_url = redirect_url, **kwargs)
        response = await self.client.async_post(
            url = self.config.token_endpoint,
            headers = self.config.get_headers('token'),
            data = params,
        )
        response.raise_for_status()
        return response.json()
    
    def refresh_token(
        self,
        refresh_token: str,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Refreshes the token
        """
        params = self.config.get_refresh_token_params(refresh_token = refresh_token, **kwargs)
        response = self.client.post(
            url = self.config.token_endpoint,
            headers = self.config.get_headers('token'),
            data = params,
        )
        response.raise_for_status()
        return response.json()
    
    async def arefresh_token(
        self,
        refresh_token: str,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Refreshes the token
        """
        params = self.config.get_refresh_token_params(refresh_token = refresh_token, **kwargs)
        response = await self.client.async_post(
            url = self.config.token_endpoint,
            headers = self.config.get_headers('token'),
            data = params,
        )
        response.raise_for_status()
        return response.json()


    async def arefresh_oauth_token(
        self,
        oauth_token: OAuth2Token,
        refresh_token: Optional[str] = None,
        **kwargs,
    ) -> Optional[OAuth2Token]:
        """
        Refreshes the oauth token
        """
        if not refresh_token:
            refresh_token = oauth_token.refresh_token or \
                await self.refresh_data.aget(oauth_token.identity)
        try:
            refreshed_token = await self.arefresh_token(refresh_token = refresh_token, **kwargs)
            self.logger.info(f'Refreshed OAuth Token for |g|{oauth_token.identity}|e|', colored = True, prefix = self.name)
        
        except Exception as e:
            self.logger.warning(f'Error refreshing token: {e} - Deleting {oauth_token.identity}', prefix = self.name)
            await self.data.adelete(oauth_token.identity)
            await self.refresh_data.adelete(oauth_token.identity)
            return None
        
        refreshed_token = self.parse_token_payload(refreshed_token)
        if not refreshed_token.refresh_token: refreshed_token.refresh_token = refresh_token
        await self.data.aset(refreshed_token.identity, refreshed_token)
        return refreshed_token
    
    
    def get_login_url(
        self, 
        additional_params: Optional[Dict[str, Any]] = None, 
        state: Optional[str] = None
    ) -> str:
        """
        Returns the login url
        """
        pass


    """
    Helper Methods
    """

    def parse_jwt_token(
        self,
        jwt_token: str,
        kind: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Parses the jwt token
        """
        signing_key = self.jwt_client.get_signing_key_from_jwt(jwt_token)
        return jwt.decode(
            jwt_token,
            signing_key.key, 
            algorithms=['RS256'],
            issuer = self.config.issuer_url,
            options = {
                'verify_signature': True,
                'verify_exp': True,
                'verify_aud': False,
            }
        )
    

    def parse_authorization_token(
        self,
        authorization: str,
        audiences: Optional[List[str]] = None,
        verify_exp: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Parses the authorization token
        """
        return jwt.decode(
            authorization, 
            self.jwt_client.get_signing_key_from_jwt(authorization).key, 
            algorithms = ['RS256'],
            audience = audiences,
            issuer = self.config.jwt_issuer_url,
            options={
                'verify_signature': True,
                'verify_exp': verify_exp,
                'verify_aud': bool(audiences),
            }
        )


    def parse_token_payload(
        self,
        token: Dict[str, Any],
    ) -> Optional[OAuth2Token]:
        """
        Parses the token payload
        """
        auth_token = OAuth2Token(**token)
        if auth_token.access_token:
            if decoded := self.parse_jwt_token(auth_token.access_token, kind = 'access_token'):
                auth_token.set_access_token(decoded)
        if auth_token.id_token:
            if decoded := self.parse_jwt_token(auth_token.id_token, kind = 'id_token'):
                auth_token.set_id_token(decoded)
        if auth_token.refresh_token and auth_token.identity:
            self.refresh_data[auth_token.identity] = auth_token.refresh_token
        auth_token.value = token
        return auth_token


    async def amerge_stored_token(
        self,
        token: 'OAuth2Token',
        **kwargs,
    ) -> 'OAuth2Token':
        """
        Merges the stored token
        """
        if await self.data.acontains(token.identity):
            stored_token = await self.data.aget(token.identity)
            token.merge(stored_token)
            self.logger.info(token, prefix = self.name)
        return token

    async def afetch_user_info(
        self,
        token: str,
        token_payload: Dict[str, Any],
        **kwargs,
    ):
        """
        Fetches the user info
        """
        pass
    

    async def afetch_access_token_info(
        self,
        token: str,
        token_payload: Dict[str, Any],
        **kwargs,
    ):
        """
        Fetches the access token info
        """
        pass


    async def abuild_oauth_token(
        self,
        token: str,
        token_payload: Dict[str, Any],
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Builds the oauth token
        """
        pass



    """
    Static Methods
    """

    @staticmethod
    def create_code_challenge(secret_key: str) -> str:
        """
        Creates a code challenge
        """
        return base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest()).decode().rstrip('=')


    @staticmethod
    def encode_params_to_url(params: Dict[str, Any], url: str) -> str:
        """
        Encodes the params to a url
        """
        return f'{url}?{urlencode(params)}'
    

    """
    M2M Methods
    """


    def fetch_m2m_token(
        self,
        audience: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the token
        """
        params = self.config.get_m2m_token_params(audience = audience)
        response = self.client.post(
            url = self.config.token_endpoint,
            headers = self.config.get_headers('token'),
            data = params,
        )
        response.raise_for_status()
        return response.json()
    

    async def afetch_m2m_token(
        self,
        audience: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the token
        """
        params = self.config.get_m2m_token_params(audience = audience)
        response = await self.client.async_post(
            url = self.config.token_endpoint,
            headers = self.config.get_headers('token'),
            data = params,
        )
        response.raise_for_status()
        return response.json()
    

    """
    M2M App Methods
    """


    async def app_retrieve_existing_domains(
        self,
        **kwargs,
    ) -> Optional[List[str]]:
        """
        Retrieves the existing app domains
        """
        pass

    async def app_add_authorized_domains(
        self,
        domains: List[str],
        **kwargs,
    ) -> None:
        """
        Adds the authorized app domains
        """
        pass

    async def app_retrieve_existing_callbacks(
        self,
        **kwargs,
    ) -> Optional[List[str]]:
        """
        Retrieves the existing app callbacks
        """
        pass

    async def app_add_authorized_callbacks(
        self,
        callback_urls: List[str],
        **kwargs,
    ) -> None:
        """
        Adds the authorized callbacks
        """
        pass

    async def app_retrieve_existing_logouts(
        self,
        **kwargs,
    ) -> Optional[List[str]]:
        """
        Retrieves the existing app logout urls
        """
        pass

    async def app_add_authorized_logouts(
        self,
        logout_urls: List[str],
        **kwargs,
    ) -> None:
        """
        Adds the authorized logouts
        """
        pass

    async def app_authorize_callbacks(
        self,
        domains: Union[str, List[str]] = None,
        path: Optional[str] = None,
    ) -> None:
        """
        Authorize Callbacks
        """
        if not self.m2m_client: return
        if self.config.authorize_disabled: return
        if not domains: domains = self.config.domains
        elif isinstance(domains, str): domains = [domains]
        if not path: path = f'/callback/{self.name}'
        if not domains: return
        callback_urls = [
            urljoin(domain, path)
            for domain in domains
        ]
        existing_callbacks = await self.app_retrieve_existing_callbacks()
        if existing_callbacks:
            callback_urls = [url for url in callback_urls if url not in existing_callbacks]

        if not callback_urls: return
        await self.app_add_authorized_callbacks(callback_urls)


    async def app_authorize_logouts(
        self,
        domains: Union[str, List[str]] = None,
        path: Optional[str] = None,
    ) -> None:
        """
        Authorizes the logout domains
        """
        if not self.m2m_client: return
        if self.config.authorize_disabled: return
        if not domains: domains = self.config.domains
        elif isinstance(domains, str): domains = [domains]
        if not path: path = f'/logout/{self.name}'
        if not domains: return
        logout_urls = [
            urljoin(domain, path)
            for domain in domains
        ]
        existing_logouts = await self.app_retrieve_existing_logouts()
        if existing_logouts:
            logout_urls = [url for url in logout_urls if url not in existing_logouts]
        if not logout_urls: return
        await self.app_add_authorized_logouts(logout_urls)

    async def app_authorize_domains(
        self,
        domains: Union[str, List[str]] = None,
        # domains: Optional[List[str]] = None,
    ) -> None:
        """
        Authorizes the app domains
        """
        if not self.m2m_client: return
        if self.config.authorize_disabled: return
        if not domains: domains = self.config.domains
        elif isinstance(domains, str): domains = [domains]
        existing_domains = await self.app_retrieve_existing_domains()
        if existing_domains:
            domains = [domain for domain in domains if domain not in existing_domains]

        if not domains: return
        await self.app_add_authorized_domains(domains)

    async def app_authorize_with_provider(
        self,
        domains: Union[str, List[str]] = None,
        callback_path: Optional[str] = None,
        logout_path: Optional[str] = None,
    ) -> None:
        """
        Authorizes the app with the provider
        """
        if not self.m2m_client: return
        if self.config.authorize_disabled: return
        if not domains: domains = self.config.domains
        elif isinstance(domains, str): domains = [domains]
        if not callback_path: callback_path = f'/callback/{self.name}'
        if not logout_path: logout_path = f'/logout/{self.name}'
        await self.app_authorize_callbacks(domains = domains, path = callback_path)
        await self.app_authorize_logouts(domains = domains, path = logout_path)
        await self.app_authorize_domains(domains = domains)


    """
    Updating Users
    """

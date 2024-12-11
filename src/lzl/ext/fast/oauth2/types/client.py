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
from .token import OAuth2Token, AccessToken, IDToken
from . import errors
from typing import Optional, Union, Dict, Any, List, Type, Generator, TYPE_CHECKING

if load.TYPE_CHECKING:
    import jwt
else:
    jwt = load.LazyLoad("jwt", install_missing=True, install_options={'package': 'pyjwt'})

if TYPE_CHECKING:
    from lzl.io import PersistentDict
    from jwt import PyJWKClient
    from .config import BaseOAuth2Config
    from .user import OAuth2User, TokenT
    from .token import TokenTypes
    from ..manager import OAuth2Manager


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
        manager: 'OAuth2Manager',
        config: Optional['BaseOAuth2Config'] = None,
        **kwargs,
    ):
        """
        Initializes the OAuth Client
        """
        self.mtg = manager
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
                f'lzl.oauth2.client.{self.name}.{self.config.client_id}'
            
            if not self.config.cache_config:
                self.config.cache_config = {
                    'serializer': 'json',
                    'url': os.getenv('OAUTH_REDIS_URL'),
                }
            elif 'serializer' not in self.config.cache_config:
                self.config.cache_config['serializer'] = 'json'
            
            self._extra['data'] = PersistentDict(
                base_key = base_key,
                expiration = self.config.cache_expiration, # 3 months
                **self.config.cache_config,
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
    
    @property
    def user_data(self) -> 'PersistentDict[str, Any]':
        """
        Returns the user info data
        """
        if 'user_data' not in self._extra:
            self._extra['user_data'] = self.data.get_child('users')
        return self._extra['user_data']

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
    FastAPI Handler Methods
    """
    def get_token_from_payload(self, payload: Dict[str, Any], token: str) -> 'TokenT':
        """
        Returns the token type from the payload
        """
        # This is likely a oauth2 token
        if payload.get('access_token'): 
            return self.config.oauth2_token_class.from_payload(payload = payload, token = token, provider = self.name)
        # Id Token usually has `picture` or `at_hash` in the payload
        if payload.get('picture') or payload.get('at_hash'): 
            return self.config.id_token_class.from_payload(payload = payload, token = token, provider = self.name)
        return self.config.access_token_class.from_payload(payload = payload, token = token, provider = self.name)

    def parse_authorization_token(
        self,
        token: str,
        options: Dict[str, bool] = None,
        raise_errors: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Union[AccessToken, IDToken]]:
        """
        Parses the authorization token
        """
        try:
            payload = self.decode_jwt_token(token, options = options, **kwargs)
            return self.get_token_from_payload(payload, token = token)
        except jwt.ExpiredSignatureError as e:
            logger.warning(f'Expired Signature: {e} - {token}')
            raise errors.ExpiredTokenError(f'Expired Authorization Token - {token}', e) from e
        except Exception as e:
            logger.warning(f'Error Parsing Token: {e}')
            if raise_errors: raise errors.InvalidTokenError(f'Invalid Authorization Token - {token}', e) from e
            return None
    
    async def aparse_authorization_token(
        self,
        token: str,
        options: Dict[str, bool] = None,
        raise_errors: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Union[AccessToken, IDToken]]:
        """
        Parses the authorization token
        """
        try:
            payload = await self.adecode_jwt_token(token, options = options, **kwargs)
            return self.get_token_from_payload(payload, token = token)
        except jwt.ExpiredSignatureError as e:
            logger.warning(f'Expired Signature: {e} - {token}')
            raise errors.ExpiredTokenError(f'Expired Authorization Token - {token}', e) from e
        
        except errors.OAuth2Exception as e:
            raise e
        
        except Exception as e:
            logger.warning(f'Error Parsing Token: {e}')
            if raise_errors: raise errors.InvalidTokenError(f'Invalid Authorization Token - {token}', e) from e
            return None
    
    """
    Session / API Key Methods
    """

    async def afetch_token_for_identity(
        self,
        identity: str,
        raise_errors: Optional[bool] = None,
        **kwargs,
    ) -> Optional[OAuth2Token]:
        """
        Fetches the token for the identity
        """
        if not await self.data.acontains(identity):
            logger.warning(f'No Token for Identity: {identity}')
            if raise_errors: raise errors.InvalidIdentityError(f'No Token for Identity: {identity}')
            return None
        
        oauth_token = await self.data.aget(identity)
        if oauth_token.is_expired:
            logger.warning(f'Token for Identity is Expired: {identity}')
            oauth_token = await self.arefresh_oauth_token(oauth_token)
            if oauth_token is None:
                logger.warning(f'Unable to refresh token for Identity: {identity}')
                if raise_errors: raise errors.InvalidIdentityError(f'Unable to refresh token for Identity: {identity}')
                return None
        return oauth_token
    
    """
    User Info Methods
    """

    def validate_user(
        self,
        user: 'OAuth2User',
        **kwargs,
    ) -> 'OAuth2User':
        """
        Validates the user
        """
        pass

    def retrieve_user_info(
        self,
        # user_id: str,
        user: 'OAuth2User',
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the user info
        """
        pass

    def fetch_user_info(
        self,
        # user_id: str,
        user: 'OAuth2User',
        refresh: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the user info
        """
        self.validate_user(user, **kwargs)
        if not user.provider_id: return
        if refresh or not self.user_data.contains(user.provider_id):
            user_info = self.retrieve_user_info(user.provider_id, **kwargs)
            if user_info: self.user_data.set(user.provider_id, user_info)
        else:
            user_info = self.user_data.get(user.provider_id)
        return user_info
    
    async def avalidate_user(
        self,
        user: 'OAuth2User',
        **kwargs,
    ) -> 'OAuth2User':
        """
        Validates the user
        """
        pass

    async def aretrieve_user_info(
        self,
        # user_id: str,
        user: 'OAuth2User',
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the user info
        """
        pass

    async def afetch_user_info(
        self,
        # user_id: str,
        user: 'OAuth2User',
        refresh: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the user info
        """
        await self.avalidate_user(user, **kwargs)
        if not user.provider_id: return
        if refresh or not await self.user_data.acontains(user.provider_id):
            user_info = await self.aretrieve_user_info(user, **kwargs)
            if user_info: await self.user_data.aset(user.provider_id, user_info)
        else:
            user_info = await self.user_data.aget(user.provider_id)
        return user_info



    """
    Helper Methods
    """

    def decode_jwt_token(
        self,
        token: str,
        options: Optional[Dict[str, bool]] = None,
        disable_signing_key: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Decodes the jwt token
        """
        if options is None: 
            options = {
                'verify_exp': True,
                'verify_iat': True,
                'verify_aud': 'audience' in kwargs,
                'verify_signature': not disable_signing_key,
            }
        signing_key = "" if disable_signing_key else self.jwt_client.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key, 
            algorithms=['RS256'],
            issuer = self.config.issuer_url,
            **kwargs,
            options = options,
        )
    
    async def adecode_jwt_token(
        self,
        token: str,
        options: Optional[Dict[str, bool]] = None,
        disable_signing_key: Optional[bool] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Decodes the jwt token
        """
        return self.decode_jwt_token(token, options = options, disable_signing_key = disable_signing_key, **kwargs)

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
        auth_token = self.config.oauth2_token_class(**token)
        if auth_token.access_token:
            if decoded := self.parse_jwt_token(auth_token.access_token, kind = 'access_token'):
                auth_token.set_access_token(decoded)
        if auth_token.id_token:
            if decoded := self.parse_jwt_token(auth_token.id_token, kind = 'id_token'):
                auth_token.set_id_token(decoded)
        if auth_token.refresh_token and auth_token.identity:
            self.refresh_data[auth_token.identity] = auth_token.refresh_token
        auth_token.value = token
        auth_token.set_provider(self.name)
        return auth_token
    
    async def aparse_token_from_callback(
        self,
        token: str,
        **kwargs,
    ) -> Optional[OAuth2Token]:
        """
        Parses the token from the callback
        """
        oauth_token = self.parse_token_payload(token)
        await self.data.aset(oauth_token.identity, oauth_token)
        return oauth_token


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


    async def set_user_data(self, user: 'OAuth2User', **kwargs) -> None:
        """
        Sets the user data
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
        if not domains: domains = self.mtg.config.domains
        elif isinstance(domains, str): domains = [domains]
        if not path: 
            path = f'{self.mtg.routes["callback"]}/{self.name}'
            # path = f'/callback/{self.name}'
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
        if not domains: domains = self.mtg.config.domains
        elif isinstance(domains, str): domains = [domains]
        if not path: 
            path = f'{self.mtg.routes["logout"]}/{self.name}'
            # path = f'/logout/{self.name}'
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
        if not domains: domains = self.mtg.config.domains
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
        if not domains: domains = self.mtg.config.domains
        elif isinstance(domains, str): domains = [domains]
        if not callback_path:  callback_path = f'{self.mtg.routes["callback"]}/{self.name}'
        if not logout_path: logout_path = f'{self.mtg.routes["logout"]}/{self.name}'
        await self.app_authorize_callbacks(domains = domains, path = callback_path)
        await self.app_authorize_logouts(domains = domains, path = logout_path)
        await self.app_authorize_domains(domains = domains)


    """
    Updating Users
    """

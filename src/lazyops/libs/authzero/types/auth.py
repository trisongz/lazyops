"""
Authentication Objects
"""
import base64
import httpx
from lazyops.libs import lazyload
from typing import Optional, List, Dict, Any, Union, Iterable, Generator, AsyncGenerator
from .base import BaseModel
from .user_data import AZUserData
from .claims import APIKeyJWTClaims


if lazyload.TYPE_CHECKING:
    # import niquests
    from starlette.datastructures import Headers
    from starlette.requests import Request
    from niquests.models import Headers, Request as HTTPRequest
    from ..configs import AuthZeroSettings
    from ..flows.tokens import ClientCredentialsFlow, APIClientCredentialsFlow, AccessToken
# else:
    # niquests = lazyload.LazyLoad("niquests")

class AuthZeroTokenAuth(httpx.Auth):
    """
    [niquests/httpx] Implements the AuthBase for the AuthZero HTTP Token

    - It will always use the `Authorization` header and automatically handle token expiration
    """

    def __init__(
        self,
        token_flow: Union['ClientCredentialsFlow', 'APIClientCredentialsFlow'],
        x_api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.token_flow = token_flow
        self.x_api_key = x_api_key
        self.headers = headers or {}

    """
    Implements the niquests logic
    """
    def __eq__(self, other: Union[str, 'AccessToken', 'AuthZeroTokenAuth']) -> bool:
        """
        Compares the token to the other
        """
        if isinstance(other, str): return self.token_flow.token == other
        if hasattr(other, 'token_flow'): return self.token_flow.token == other.token_flow.token
        return self.token_flow.token == getattr(other, "token", None)
    
    def __ne__(self, other: Union[str, 'AccessToken', 'AuthZeroTokenAuth']) -> bool:
        """
        Compares the token to the other
        """
        return not self == other

    def __call__(self, r: 'HTTPRequest') -> 'HTTPRequest':
        """
        Implements the AuthZero HTTP Credential Injection
        """
        r.headers['Authorization'] = f'Bearer {self.token_flow.token}'
        if self.x_api_key is not None: r.headers['x-api-key'] = self.x_api_key
        if self.headers: 
            for key, value in self.headers.items():
                if key not in r.headers: r.headers[key] = value
        # print(r.headers)
        return r
    
    """
    Implements the httpx logic
    """

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """
        Implements the httpx auth flow
        """
        request.headers['Authorization'] = f'Bearer {self.token_flow.token}'
        if self.x_api_key is not None: request.headers['x-api-key'] = self.x_api_key
        if self.headers: 
            for key, value in self.headers.items():
                if key not in request.headers: request.headers[key] = value
        yield request



class AuthObject(BaseModel):
    auth_token: Optional[str] = None
    x_api_key: Optional[str] = None

    model_config = {'arbitrary_types_allowed': True}
    
    @property
    def has_auth_token(self) -> bool:
        """
        Returns True if the Auth Token is Present
        """
        return bool(self.auth_token)
    
    @property
    def has_x_api_key(self) -> bool:
        """
        Returns True if the X-API-Key is Present
        """
        return bool(self.x_api_key)
    
    @property
    def has_both_auth(self) -> bool:
        """
        Returns True if the Auth Token and X-API-Key are Present
        """
        return self.has_auth_token and self.has_x_api_key
    
    @classmethod
    def get_auth_token(cls, data: Union['Headers', Dict[str, str]], settings: Optional['AuthZeroSettings'] = None) -> Optional[str]:
        """
        Returns the Auth Token from the Headers or Cookies
        """
        settings = settings or cls.get_settings()
        authorization_header_value = data.get(settings.authorization_header)
        if authorization_header_value:
            scheme, _, param = authorization_header_value.partition(" ")
            if scheme.lower() == settings.authorization_scheme and not param.startswith("apikey:"):
                return param
    
    @classmethod
    def get_x_api_key(cls, data: Union['Headers', Dict[str, str]], settings: Optional['AuthZeroSettings'] = None) -> Optional[str]:
        """
        Returns the API Key from the Headers or Cookies
        """
        # We're supporting `Authorization: Basic apikey:secret` for SPARQL Server Implementations
        settings = settings or cls.get_settings()
        if api_key := data.get(settings.apikey_header):
            return api_key
        authorization_header_value = data.get(settings.authorization_header)
        if authorization_header_value:
            scheme, _, param = authorization_header_value.partition(" ")
            if scheme.lower() in {"basic", "bearer"}:
                if scheme.lower() == 'basic':
                    param = base64.b64decode(param).decode("utf-8")
                if "apikey:" not in param:
                    return None
                _, api_key = param.split(":", 1)
                return api_key


    @classmethod
    def from_headers(cls, headers: 'Headers', settings: Optional['AuthZeroSettings'] = None) -> 'AuthObject':
        """
        Returns an AuthObject from the Headers
        """
        settings = settings or cls.get_settings()
        return cls(
            auth_token = cls.get_auth_token(data = headers, settings = settings),
            x_api_key = cls.get_x_api_key(data = headers, settings = settings),
        )


    @classmethod
    def extract_auth_token(cls, *data: Iterable[Union['Headers', Dict[str, str]]], settings: Optional['AuthZeroSettings'] = None) -> Optional[str]:
        """
        Extract the Auth Token from the Headers, Cookies, or Dict
        """
        settings = settings or cls.get_settings()
        for item in data:
            if token := cls.get_auth_token(data = item, settings = settings): return token
        return None

    @classmethod
    def extract_x_api_key(cls, *data: Iterable[Union['Headers', Dict[str, str]]], settings: Optional['AuthZeroSettings'] = None) -> Optional[str]:
        """
        Extract the API Key from the Headers, Cookies, or Dict
        """
        settings = settings or cls.get_settings()
        for item in data:
            if api_key := cls.get_x_api_key(data = item, settings = settings): return api_key
        return None

    @classmethod
    def from_request(cls, request: 'Request', settings: Optional['AuthZeroSettings'] = None) -> 'AuthObject':
        """
        Returns an AuthObject from the Request
        """
        settings = settings or cls.get_settings()
        return cls(
            auth_token = cls.extract_auth_token(request.headers, request.cookies, settings = settings),
            x_api_key = cls.extract_x_api_key(request.headers, request.cookies, settings = settings),
        )

    @classmethod
    def from_items(cls, *items: Iterable[Dict[str, str]], settings: Optional['AuthZeroSettings'] = None) -> 'AuthObject':
        """
        Returns an AuthObject from the Iterable of Dicts
        """
        settings = settings or cls.get_settings()
        return cls(
            auth_token = cls.extract_auth_token(*items, settings = settings),
            x_api_key = cls.extract_x_api_key(*items, settings = settings),
        )
    


class APIKeyData(BaseModel):
    """
    The stored API Key Data
    """
    user_data: AZUserData
    claims: APIKeyJWTClaims

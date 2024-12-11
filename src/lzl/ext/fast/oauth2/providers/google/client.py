from __future__ import annotations


from lzl.api import aiohttpx
from ...types.client import BaseOAuth2Client, eproperty, jwt
from ...types import errors
from .config import GoogleOAuth2Config
from typing import Any, Dict, Optional, Union, Tuple, TYPE_CHECKING, List, Type, Annotated

if TYPE_CHECKING:
    from ...types.user import OAuth2User

class GoogleOAuth2Client(BaseOAuth2Client):
    """
    Google Auth Client
    """
    name: Optional[str] = 'google'

    if TYPE_CHECKING:
        config: GoogleOAuth2Config
    

    @eproperty
    def config_class(self) -> Type['GoogleOAuth2Config']:
        """
        Returns the Config Class
        """
        return GoogleOAuth2Config
    
    def fetch_token_info(
        self,
        token: str,
        kind: str = 'access_token',
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the token info
        """
        response = self.client.get(self.config.token_info_endpoint, params = {kind: token})
        response.raise_for_status()
        return response.json()
    
    async def afetch_token_info(
        self,
        token: str,
        kind: str = 'access_token',
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the token info
        """
        response = await self.client.async_get(self.config.token_info_endpoint, params = {kind: token})
        try:
            response.raise_for_status()
        except aiohttpx.HTTPStatusError as e:
            raise errors.InvalidAuthorizationError(f'Error Fetching Token Info: {e.response.text}') from e
        except Exception as e:
            raise errors.InvalidAuthorizationError('Error Fetching Token Info', e) from e
        return response.json()

    def parse_jwt_token(
        self,
        jwt_token: str,
        kind: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Parses the jwt token
        """
        # Posssible bug with the jwt?
        if kind == 'access_token': 
            return self.fetch_token_info(jwt_token, kind = kind)
        return jwt.decode(
            jwt_token,
            "",
            # signing_key.key, 
            algorithms=['RS256'],
            issuer = self.config.issuer_url,
            options = {
                'verify_signature': False,
                'verify_exp': True,
                'verify_aud': False,
            }
        )
        # return super().parse_jwt_token(jwt_token, kind = kind)

    
    def parse_authorization_token(
        self,
        authorization: str,
        audiences: Optional[List[str]] = None,
        verify_exp: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Parses the authorization token
        """
        # Posssible bug with the jwt?
        return jwt.decode(
            authorization, 
            "", 
            algorithms = ['RS256'],
            audience = audiences,
            issuer = self.config.jwt_issuer_url,
            options={
                'verify_signature': False,
                'verify_exp': verify_exp,
                'verify_aud': bool(audiences),
            }
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
        if token.startswith('ya29.'):
            return await self.afetch_token_info(
                token, 
                kind = 'access_token',
            )
        return await super().adecode_jwt_token(token, options = options, disable_signing_key = disable_signing_key, **kwargs)
    
    async def set_user_data(self, user: 'OAuth2User', **kwargs) -> None:
        """
        Sets the user data
        """
        if not user.token: return
        if user.token.access_token:
            if user.token.access_token.scope:
                user.scopes = user.token.access_token.scope.split(' ')

        if user.token.id_token:
            extra_data = {
                'picture': user.token.id_token.picture,
                'at_hash': user.token.id_token.at_hash,
                'name': user.token.id_token.name,
                'given_name': user.token.id_token.given_name,
                'family_name': user.token.id_token.family_name,
                'email': user.token.id_token.email,
                'email_verified': user.token.id_token.email_verified,
            }
            extra_data = {k: v for k, v in extra_data.items() if v}
            if not user.data: user.data = {}
            user.data.update(extra_data)
        return user


    # async def avalidate_user(
    #     self,
    #     user: 'OAuth2User',
    #     **kwargs,
    # ) -> 'OAuth2User':
    #     """
    #     Validates the user
    #     """
    #     pass

    # async def aretrieve_user_info(
    #     self,
    #     user: 'OAuth2User',
    #     **kwargs,
    # ) -> Optional[Dict[str, Any]]:
    #     """
    #     Retrieves the user info
    #     """
    #     pass





        
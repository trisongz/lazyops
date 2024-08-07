from __future__ import annotations

"""
Kinde API Client with Modifications
"""

import jwt
from authlib.oauth2.rfc6749 import OAuth2Token
from kinde_sdk.kinde_api_client import GrantType, KindeApiClient as BaseKindeApiClient
from kinde_sdk.exceptions import (
    KindeTokenException
)
from authlib.integrations.base_client.errors import OAuthError
from .types.attributes import Organization, Role, Permission, JSONProperty, JSONOrgProperty, serializer
from lazyops.utils.logs import logger, Logger
from lazyops.libs.abcs.types.roles import UserRole
from typing import Optional, List, Dict, Any, Callable, Union, Awaitable, overload, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from kvdb import PersistentDict
    from .client import KindeClient
    from .config import KindeSettings

class KindeM2MApiClient(BaseKindeApiClient):
    """
    The Kinde M2M Api Client
    """
    _attributes: Dict[str, Any] = {}
    _pdicts: Dict[str, 'PersistentDict'] = {}

    @property
    def access_token_obj(self) -> OAuth2Token:
        """
        Returns the access token object
        """
        return self.__access_token_obj
    
    @access_token_obj.setter
    def access_token_obj(self, value: OAuth2Token):
        """
        Sets the access token object
        """
        self.__access_token_obj = value
        self.configuration.access_token = value.get("access_token")

    @property
    def audience(self) -> str:
        """
        Returns the audience
        """
        if 'audience' not in self._attributes:
            self._attributes['audience'] = self.get_claim("aud")["value"][0]
        return self._attributes['audience']
    
    @property
    def app_client_id(self) -> Optional[str]:
        """
        Returns the app client id
        """
        return self._attributes.get('app_client_id')
    
    @app_client_id.setter
    def app_client_id(self, value: Optional[str]):
        """
        Sets the app client id
        """
        self._attributes['app_client_id'] = value

    def _refresh_token(self) -> None:
        """
        Refreshes the token
        """
        super()._refresh_token()
        self._has_refreshed_token = True

    def fetch_token(self, authorization_response: Optional[str] = None) -> None:
        """
        Fetches the token
        """
        super().fetch_token(authorization_response = authorization_response)
        self._has_refreshed_token = True

    @property
    def settings(self) -> 'KindeSettings':
        """
        Returns the settings
        """
        if 'settings' not in self._attributes:
            from .utils import get_kinde_settings
            self._attributes['settings'] = get_kinde_settings()
        return self._attributes['settings']

    @property
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        return self.settings.logger
    
    @property
    def autologger(self) -> 'Logger':
        """
        Returns the autologger
        """
        return self.settings.autologger

    @property
    def data(self) -> 'PersistentDict':
        """
        Returns the Persistent Dict for data
        """
        return self.settings.data


    @property
    def token_data(self) -> 'PersistentDict[str, OAuth2Token]':
        """
        [M2M] Returns the token data
        """
        if 'token_data' not in self._pdicts:
            self._pdicts['token_data'] = self.data.get_child(
                'm2m_token_data',
                serializer = 'pickle',
                compression = 'zstd',
                compression_level = 19,
            )
        return self._pdicts['token_data']

class KindeApiClient(BaseKindeApiClient):
    """
    The Kinde Api Client
    """
    _attributes: Dict[str, Any] = {}

    def _decode_token_if_needed(self, token_name: str) -> None:
        if token_name not in self.__decoded_tokens:
            if not self.__access_token_obj:
                raise KindeTokenException(
                    "Access token doesn't exist.\n"
                    "When grant_type is CLIENT_CREDENTIALS use fetch_token().\n"
                    'For other grant_type use "get_login_url()" or "get_register_url()".'
                )
            token = self.__access_token_obj.get(token_name)
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            if token:
                decode_token_params = {
                    "jwt":token,
                    "key": signing_key.key,
                    "algorithms":["RS256"],
                    "options":{
                        "verify_signature": True,
                        "verify_exp": token_name != "id_token",
                        "verify_aud": False
                    }
                }
                self.__decoded_tokens[token_name] = jwt.decode(**decode_token_params)
            else:
                raise KindeTokenException(f"Token {token_name} doesn't exist.")

    def get_claim(self, key: str, token_name: str = "access_token") -> Any:
        if token_name not in self.TOKEN_NAMES:
            raise KindeTokenException(f"Please use only tokens from the list: {self.TOKEN_NAMES}")
        try:
            self._decode_token_if_needed(token_name)
            value = self.__decoded_tokens[token_name].get(key)
            return {"name": key, "value": value}
        except jwt.exceptions.ExpiredSignatureError as e:
            # if token_name == 'id_token':
            #     logger.info(f'Refreshing Claims Token: {token_name}')
            #     id_token = self._get_id_token()
            #     logger.info(f'Refreshing ID Token: {id_token}')
            self._refresh_token()
            return self.get_claim(key, token_name)
        except Exception as e:
            logger.error(f'Error Decoding JWT Claim: {e}')
            raise e


    @property
    def access_token_obj(self) -> OAuth2Token:
        """
        Returns the access token object
        """
        return self.__access_token_obj
    
    @access_token_obj.setter
    def access_token_obj(self, value: OAuth2Token):
        """
        Sets the access token object
        """
        self.__access_token_obj = value
        self.configuration.access_token = value.get("access_token")

    @property
    def decoded_tokens(self) -> Dict[str, Any]:
        """
        Returns the decoded tokens
        """
        return self.__decoded_tokens
    
    @property 
    def _has_refreshed_token(self) -> bool:
        """
        Returns whether the token has been refreshed
        """
        return self._attributes.get('has_refreshed_token', False)
    
    @_has_refreshed_token.setter
    def _has_refreshed_token(self, value: bool):
        """
        Sets whether the token has been refreshed
        """
        self._attributes['has_refreshed_token'] = value

    @property
    def _app_api(self) -> Optional['KindeClient']:
        """
        Returns the Kinde API Client
        """
        return self._attributes.get('app_api')
    
    @_app_api.setter
    def _app_api(self, value: 'KindeClient'):
        """
        Sets the Kinde API Client
        """
        self._attributes['app_api'] = value


    def _update_user_property(
        self,
        property_key: str,
        value: Any,
        is_json: Optional[bool] = False,
    ) -> None:
        """
        Updates the user property
        """
        if not self._app_api.user_api: return
        # logger.info(f'Updating User Property: {property_key} -> {value}')
        if is_json: value = serializer.dumps(value)
        response = self._app_api.user_api.update_user_property(
            path_params={"user_id": self.user_id, "property_key": property_key},
            query_params={"value": value},
            # accept_content_types=('application/json',),
            skip_deserialization=True,
        )
        # logger.info(response)

    def _update_org_property(
        self,
        property_key: str,
        value: Any,
        is_json: Optional[bool] = False,
    ) -> None:
        """
        Updates the organization property
        """
        if not self._app_api.organization_api: return
        # logger.info(f'Updating Organization Property: {property_key} -> {value}')
        if is_json: value = serializer.dumps(value)
        self._app_api.organization_api.update_organization_property(
            path_params={"org_code": self.org_id, "property_key": property_key},
            query_params={"value": value},
            # accept_content_types=('application/json',),
            skip_deserialization=True,
        )

    @property
    def user_id(self) -> Optional[str]:
        """
        Returns the user id
        """
        if 'user_id' not in self._attributes:
            self._attributes['user_id'] = self.get_claim("sub")["value"]
        return self._attributes['user_id']
    
    @user_id.setter
    def user_id(self, value: str):
        """
        Sets the user id
        """
        self._attributes['user_id'] = value

    @property
    def user_email(self) -> Optional[str]:
        """
        Returns the user email
        """
        if 'user_email' not in self._attributes:
            self._attributes['user_email'] = self.get_claim("email", "id_token")["value"]
        return self._attributes['user_email']
    
    @property
    def email_domain(self) -> Optional[str]:
        """
        Returns the user email domain
        """
        if 'email_domain' not in self._attributes and self.user_email:
            self._attributes['email_domain'] = self.user_email.split('@', 1)[-1]
        return self._attributes['email_domain']
    
    @property
    def org_id(self) -> Optional[str]:
        """
        Returns the org id / code
        """
        if 'org_id' not in self._attributes:
            org_id = self.get_claim("org_code")["value"] or self.org_code
            if not org_id and self.org_codes:
                org_id = self.org_codes[0]
            if not org_id and self.organizations:
                org_id = self.organizations[0].id
            self._attributes['org_id'] = org_id
        return self._attributes['org_id']

    @property
    def org_codes(self) -> List[str]:
        """
        Returns the org codes
        """
        if 'org_codes' not in self._attributes:
            self._attributes['org_codes'] = self.get_claim("org_codes", "id_token")["value"]
        return self._attributes['org_codes']
    
    @property
    def organizations(self) -> Optional[List[Organization]]:
        """
        Returns the organizations
        """
        if 'organizations' not in self._attributes:
            orgs = self.get_claim("organizations", "id_token")["value"]
            if orgs:
                self._attributes['organizations'] = [Organization(**org) for org in orgs]
            else: self._attributes['organizations'] = []
        return self._attributes['organizations']

    @property
    def roles(self) -> List[Role]:
        """
        Returns the roles
        """
        if 'roles' not in self._attributes:
            roles = self.get_claim("roles")["value"]
            roles = [Role(**role) for role in roles] if roles else []
            if roles: self._app_api.update_roles_with_permissions(roles)
            self._attributes['roles'] = roles
        return self._attributes['roles']
    
    @property
    def role(self) -> Optional[Role]:
        """
        Returns the role
        """
        if 'role' not in self._attributes and self.roles:
            self._attributes['role'] = self.roles[0]
        return self._attributes.get('role')

    @property
    def user_role(self) -> Optional[UserRole]:
        """
        Returns the user role
        """
        return self._attributes.get('user_role')
    
    @user_role.setter
    def user_role(self, value: UserRole):
        """
        Sets the user role
        """
        self._attributes['user_role'] = value

    @property
    def _user_properties(self) -> Dict[str, Any]:
        """
        Returns the user properties
        """
        if 'user_properties' not in self._attributes:
            if self._app_api.user_api:
                response = self._app_api.user_api.get_user_property_values(
                    path_params={"user_id": self.user_id},
                    skip_deserialization=True,
                )
                response_data: Dict[str, Union[str, List[Dict[str, str]]]] = serializer.loads(response.response.data.decode())
                properties = response_data.get('properties', {})
                if properties: properties = {i['key']: i['value'] for i in properties}
                self._attributes['user_properties'] = properties
            else: self._attributes['user_properties'] = {}
        return self._attributes['user_properties']
    
    @property
    def _org_properties(self) -> Dict[str, Any]:
        """
        Returns the organization properties
        """
        if 'org_properties' not in self._attributes:
            if self._app_api.organization_api:
                response = self._app_api.organization_api.get_organization_property_values(
                    path_params={"org_code": self.org_id},
                    skip_deserialization=True,
                    # accept_content_types=('application/json',),

                )
                response_data: Dict[str, Union[str, List[Dict[str, str]]]] = serializer.loads(response.response.data.decode())
                properties = response_data.get('properties', {})
                if properties: properties = {i['key']: i['value'] for i in properties}
                self._attributes['org_properties'] = properties
            else: self._attributes['org_properties'] = {}
        return self._attributes['org_properties']

    @property
    def app_data(self) -> Dict[str, Any]:
        """
        Returns the application data
        """
        if 'app_data' not in self._attributes:
            self._attributes['app_data'] = JSONProperty(self, 'app_data', self._user_properties.get('app_data'))
        return self._attributes['app_data']

    
    @property
    def user_data(self) -> Dict[str, Any]:
        """
        Returns the user data
        """
        if 'user_data' not in self._attributes:
            self._attributes['user_data'] = JSONProperty(self, 'user_data', self._user_properties.get('user_data'))
        return self._attributes['user_data']

    @property
    def user_org_data(self) -> Dict[str, Any]:
        """
        Returns the user organization data
        """
        if 'user_org_data' not in self._attributes:
            self._attributes['user_org_data'] = JSONProperty(self, 'user_org_data', self._user_properties.get('user_org_data'))
        return self._attributes['user_org_data']
    
    @property
    def org_data(self) -> Dict[str, Any]:
        """
        Returns the organization data
        """
        if 'org_data' not in self._attributes:
            self._attributes['org_data'] = JSONOrgProperty(self, 'org_data', self._org_properties.get('org_data'))
        return self._attributes['org_data']

    def _refresh_token(self) -> None:
        """
        Refreshes the token
        """
        super()._refresh_token()
        self._has_refreshed_token = True

    def fetch_token(self, authorization_response: Optional[str] = None) -> None:
        """
        Fetches the token
        """
        super().fetch_token(authorization_response = authorization_response)
        self._has_refreshed_token = True

    def _get_id_token(self) -> Optional[str]:
        """
        Returns the ID Token
        """
        # if not self._app_api.mtg_api: return None
        return self._app_api.fetch_refresh_claims_token(self.user_id)



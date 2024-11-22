from __future__ import annotations

"""
Kinde OAuth2 Client
"""

from ...types.client import BaseOAuth2Client, eproperty
from typing import Any, Dict, Optional, Union, Tuple, TYPE_CHECKING, List, Type, Annotated
from .config import KindeOAuth2Config
from .types import UserInfo

if TYPE_CHECKING:
    from lzl.io import PersistentDict
    from lzl.io.ser import JsonSerializer
    from ...types.user import OAuth2User

class KindeOAuth2Client(BaseOAuth2Client):
    """
    Kinde OAuth2 Client
    """
    name: Optional[str] = 'kinde'

    if TYPE_CHECKING:
        config: KindeOAuth2Config

    
    @property
    def user_data(self) -> 'PersistentDict[str, UserInfo]':
        """
        Returns the user info data
        """
        if 'user_data' not in self._extra:
            self._extra['user_data'] = self.data.get_child('users', expiration = 300)
        return self._extra['user_data']


    @eproperty
    def config_class(self) -> Type['KindeOAuth2Config']:
        """
        Returns the Config Class
        """
        return KindeOAuth2Config

    @eproperty
    def serializer(self) -> 'JsonSerializer':
        """
        Returns the serializer
        """
        from lzl.io.ser import get_serializer
        return get_serializer('json', disable_nested_values = True)


    async def app_retrieve_existing_callbacks(
        self,
        **kwargs,
    ) -> Optional[List[str]]:
        """
        Retrieves the existing app callbacks
        """
        response = await self.m2m_client.async_get(
            f'/api/v1/applications/{self.config.client_id}/auth_redirect_urls',
            headers = {
                'Accept': 'application/json',
            }
        )
        response.raise_for_status()
        data: Dict[str, List[str]] = response.json()
        # logger.info(data)
        return data.get('redirect_urls', [])


    async def app_add_authorized_callbacks(
        self,
        callback_urls: List[str],
        **kwargs,
    ) -> None:
        """
        Adds the authorized callbacks
        """
        response = await self.m2m_client.async_post(
            f'/api/v1/applications/{self.config.client_id}/auth_redirect_urls',
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json; charset=utf-8',
            },
            json = {
                'urls': callback_urls,
            }
        )
        response.raise_for_status()
        data = response.json()
        data['urls'] = callback_urls
        self.logger.info(data, colored = True, prefix = f'{self.name} - Added {len(callback_urls)} Authorized Callbacks')
        
    
    async def app_retrieve_existing_logouts(
        self,
        **kwargs,
    ) -> Optional[List[str]]:
        """
        Retrieves the existing app logout urls
        """
        response = await self.m2m_client.async_get(
            f'/api/v1/applications/{self.config.client_id}/auth_logout_urls',
            headers = {
                'Accept': 'application/json',
            }
        )
        response.raise_for_status()
        data: Dict[str, List[str]] = response.json()
        return data.get('logout_urls', [])

    async def app_add_authorized_logouts(
        self,
        logout_urls: List[str],
        **kwargs,
    ) -> None:
        """
        Adds the authorized logouts
        """
        response = await self.m2m_client.async_post(
            f'/api/v1/applications/{self.config.client_id}/auth_logout_urls',
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json; charset=utf-8',
            },
            json = {
                'urls': logout_urls,
            }
        )
        response.raise_for_status()
        data = response.json()
        data['urls'] = logout_urls
        self.logger.info(data, colored = True, prefix = f'{self.name} - Added {len(logout_urls)} Authorized Logouts')
    
    async def aretrieve_user_info(
        self,
        # user_id: str,
        user: 'OAuth2User',
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the user info
        """
        response = await self.m2m_client.async_get(
            f'/api/v1/user?id={user.provider_id}',
            headers = {
                'Accept': 'application/json',
            }
        )
        response.raise_for_status()
        return response.json()
        # data = response.json()
        # self.logger.info(data)
        # return data

    def map_feature_flags(self, feature_flags: Dict[str, Dict[str, Union[str, bool, dict]]]) -> Dict[str, Any]:
        """
        Maps the feature flags
        """
        result = {}
        for key, flag in feature_flags.items():
            if flag['t'] == 's':
                result[key] = flag['v']
                continue
            if flag['t'] == 'b':
                result[key] = flag['v'] == 'true'
                continue
            if flag['t'] == 'i':
                result[key] = int(flag['v'])
                continue
            if flag['t'] == 'j':
                result[key] = self.serializer.loads(flag['v']) if \
                    isinstance(flag['v'], str) else flag['v']
                continue
        return result

    def map_properties(self, props: Dict[str, Dict[str, Union[str, bool]]]) -> Dict[str, Any]:
        """
        Maps the properties
        """
        result = {}
        for key, value in props.items():
            if value.get('v'):
                if '{' in value['v']:
                    value['v'] = self.serializer.loads(value['v'])
                elif value['v'] in {'true', 'false'}:
                    value['v'] = value['v'] == 'true'
            else:
                value['v'] = None
            result[key] = value
        return result
    
    def serialize_properties(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serializes the properties
        """
        result = {}
        for key, value in props.items():
            if value is None:
                continue
            if isinstance(value, str):
                result[key] = {'v': value}
                continue
            result[key] = {'v': self.serializer.dumps(value)}
        return result
        
    async def set_user_data(self, user: 'OAuth2User', **kwargs) -> None:
        """
        Sets the user data
        """
        # if user.method not in {'session', 'authorization'}: return
        if not user.token: return
        # self.logger.info(f'Fetching User Data: {user.token}')
        # self.logger.info(f'Setting User Data: {user.token}')
        if user.token.access_token.scp:
            user.scopes = user.token.access_token.scp
        roles = [role['name'] for role in user.token.access_token.get('roles', [])]
        for role in roles:
            user.add_role(role)
        extra_data = {}
        if user.token.access_token:
            extra_data.update({
                'external_org_id': user.token.access_token.get('external_org_id'),
                'org_code': user.token.access_token.get('org_code'),
                'org_name': user.token.access_token.get('org_name'),
                'permissions': user.token.access_token.get('permissions'),
            })
            if feature_flags := user.token.access_token.get('feature_flags'):
                extra_data['feature_flags'] = self.map_feature_flags(feature_flags)
            if organization_properties := user.token.access_token.get('organization_properties'):
                extra_data['organization_properties'] = self.map_properties(organization_properties)
            if user_properties := user.token.access_token.get('user_properties'):
                extra_data['user_properties'] = self.map_properties(user_properties)
        if user.token.id_token:
            extra_data.update({
                'org_codes': user.token.id_token.get('org_codes'),
                'organizations': user.token.id_token.get('organizations'),
                'name': user.token.id_token.get('name'),
                'given_name': user.token.id_token.get('given_name'),
                'family_name': user.token.id_token.get('family_name'),
            })
            if not extra_data.get('feature_flags') and (feature_flags := user.token.id_token.get('feature_flags')):
                extra_data['feature_flags'] = self.map_feature_flags(feature_flags)
            if not extra_data.get('organization_properties') and (organization_properties := user.token.id_token.get('organization_properties')):
                extra_data['organization_properties'] = self.map_properties(organization_properties)
            if not extra_data.get('user_properties') and (user_properties := user.token.id_token.get('user_properties')):
                extra_data['user_properties'] = self.map_properties(user_properties)
        extra_data = {k: v for k, v in extra_data.items() if v}
        if not extra_data: return
        if not user.data: user.data = {}
        user.data.update(extra_data)
        return user

    def update_user_properties(
        self,
        user: 'OAuth2User',
    ):
        """
        Updates the user property
        """
        props = {}
        if user.data.get('organization_properties'):
            props.update(user.data['organization_properties'])
        if user.data.get('user_properties'):
            props.update(user.data['user_properties'])
        if not props: return
        response = self.m2m_client.patch(
            f'/api/v1/users/{user.provider_id}/properties',
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            json = {
                'properties': self.serialize_properties(props),
            }
        )
        response.raise_for_status()
        data = response.json()
        self.logger.info(data, colored = True, prefix = f'{self.name} - Updated User Properties')
        return user

    async def aupdate_user_properties(
        self,
        user: 'OAuth2User',
    ):
        """
        Updates the user property
        """
        props = {}
        if user.data.get('organization_properties'):
            props.update(user.data['organization_properties'])
        if user.data.get('user_properties'):
            props.update(user.data['user_properties'])
        if not props: return
        response = await self.m2m_client.async_patch(
            f'/api/v1/users/{user.provider_id}/properties',
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            json = {
                'properties': self.serialize_properties(props),
            }
        )
        response.raise_for_status()
        data = response.json()
        self.logger.info(data, colored = True, prefix = f'{self.name} - Updated User Properties')
        return user
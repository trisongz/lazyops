from __future__ import annotations

"""
User Context Types
"""

from pydantic import BaseModel, PrivateAttr, Field
from authlib.oauth2.rfc6749 import OAuth2Token
from lazyops.libs.abcs.utils.helpers import update_dict
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from kinde_sdk.kinde_api_client import KindeApiClient

class UserContext(BaseModel):
    """
    User Context
    """
    api_key: Optional[str] = Field(None, description = "The API Key")
    data: Dict[str, Union[str, OAuth2Token, Any]] = Field(default_factory = dict)

    _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)
    model_config = {'arbitrary_types_allowed': True, 'extra': 'allow'}

    
    @property
    def token(self) -> Optional[OAuth2Token]:
        """
        Returns the OAuth2 Token
        """
        return self.data.get('token')
    
    @token.setter
    def token(self, value: OAuth2Token):
        """
        Sets the OAuth2 Token
        """
        self.data['token'] = value


    @property
    def client(self) -> Optional['KindeApiClient']:
        """
        Returns the Kinde Client
        """
        return self._extra.get('client')


    @client.setter
    def client(self, value: 'KindeApiClient'):
        """
        Sets the Kinde Client
        """
        if value.__access_token_obj:
            self.token = value.__access_token_obj
        elif self.token:
            value.__access_token_obj = self.token
            value.configuration.access_token = self.token.get('access_token')
        self._extra['client'] = value


    
    def update(self, **kwargs):
        """
        Updates the User Session Data
        """
        self.data = update_dict(self.data, kwargs)
        return self.data
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Gets the Item
        """
        return self.data.get(key, default)
    
    def pop(self, key: str, default: Any = None) -> Any:
        """
        Pops the Item
        """
        return self.data.pop(key, default)

    def __setitem__(self, key: str, value: Any):
        """
        Sets the Item
        """
        self.data[key] = value

    def __getitem__(self, key: str) -> Any:
        """
        Gets the Item
        """
        if self.data is None:
            self.data = {}
        return self.data[key]
    
    def __delitem__(self, key: str):
        """
        Deletes the Item
        """
        del self.data[key]

    def __contains__(self, key: str) -> bool:
        """
        Returns True if the Item is in the User Session
        """
        return key in self.data
    

    




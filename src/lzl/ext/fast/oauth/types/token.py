from __future__ import annotations

"""
Base Token Types
"""

import time
from lzo.types import BaseModel, Field, eproperty, model_validator
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING


class AccessTokenPayload(BaseModel):
    iss: Optional[str] = None
    sub: Optional[str] = None
    aud: Optional[Union[List, str]] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    nbf: Optional[int] = None
    jti: Optional[str] = None
    typ: Optional[str] = None
    azp: Optional[str] = None
    scope: Optional[str] = None

    value: Optional[str] = None # The actual token value
    

    def update(self, data: Dict[str, Any]):
        """
        Updates the payload
        """
        if not data.get('iat') or \
            data['iat'] < self.iat: return
        for key, value in data.items():
            if value and hasattr(self, key): setattr(self, key, value)
    
    @property
    def is_expired(self) -> bool:
        """
        Returns True if the Token is Expired
        """
        return self.exp < int(time.time()) if self.exp else False


class IDTokenPayload(AccessTokenPayload):
    hd: Optional[str] = None
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    at_hash: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None


class OAuth2Token(BaseModel):
    
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    token_type: Optional[str] = None

    access_token: Optional[Union[AccessTokenPayload, str]] = None
    id_token: Optional[Union[IDTokenPayload, str]] = None
    issued_at: Optional[int] = None
    expiration_ts: Optional[float] = None
    provider: Optional[str] = None
    # value: Optional[str] = None # The actual token value

    @model_validator(mode = 'after')
    def validate_oauth_token(self):
        """
        Sets the Expires At
        """
        if self.expiration_ts is None:
            if self.expires_in is not None:
                self.expiration_ts = time.time() + (self.expires_in - 10)
            elif self.issued_at is not None:
                self.expiration_ts = self.issued_at + (self.expires_in - 10)
        elif self.expires_in is not None:
            self.expires_in = int(self.expiration_ts - time.time())
        return self
    

    @property
    def is_expired(self) -> bool:
        """
        Returns True if the Token is Expired
        """
        return self.expiration_ts < time.time() if self.expiration_ts else False
    

    def set_access_token(
        self, 
        data: Dict[str, Any],
        token: Optional[str] = None,
    ) -> None:
        """
        Sets the Access Token
        """
        access_token = AccessTokenPayload(**data)
        if token is not None: access_token.value = token
        elif isinstance(self.access_token, str):
            access_token.value = self.access_token
        self.access_token = access_token

    def set_id_token(
        self, 
        data: Dict[str, Any],
        token: Optional[str] = None,
    ) -> None:
        """
        Sets the ID Token
        """
        id_token = IDTokenPayload(**data)
        if token is not None: id_token.value = token
        elif isinstance(self.id_token, str):
            id_token.value = self.id_token
        self.id_token = id_token
    
    @property
    def identity(self) -> Optional[str]:
        """
        Returns the Identity
        """
        if 'identity' not in self._extra:
            if self.id_token and not isinstance(self.id_token, str) and self.id_token.sub:
                self._extra['identity'] = self.id_token.sub
            elif self.access_token and not isinstance(self.access_token, str) and self.access_token.sub:
                self._extra['identity'] = self.access_token.sub
        return self._extra.get('identity')

    @property
    def email(self) -> Optional[str]:
        """
        Returns the Email
        """
        if 'email' not in self._extra:
            if self.id_token and not isinstance(self.id_token, str) and self.id_token.email:
                self._extra['email'] = self.id_token.email
            elif self.access_token and not isinstance(self.access_token, str) and self.access_token.get('email'):
                self._extra['email'] = self.access_token.get('email')
        return self._extra.get('email')

    @property
    def roles(self) -> Optional[List[str]]:
        """
        Returns the Roles
        """
        if 'roles' not in self._extra:
            if self.id_token and not isinstance(self.id_token, str) and self.id_token.get('roles'):
                self._extra['roles'] = self.id_token.get('roles')
            elif self.access_token and not isinstance(self.access_token, str) and self.access_token.get('roles'):
                self._extra['roles'] = self.access_token.get('roles')
            
            if self._extra.get('roles') and isinstance(self._extra['roles'], list) and \
                isinstance(self._extra['roles'][0], dict):
                self._extra['roles'] = [role['name'] for role in self._extra['roles']]
        return self._extra.get('roles')

    @property
    def role(self) -> Optional[str]:
        """
        Returns the Role
        """
        if 'role' not in self._extra:
            if self.id_token and not isinstance(self.id_token, str) and self.id_token.get('role'):
                self._extra['role'] = self.id_token.get('role')
            elif self.access_token and not isinstance(self.access_token, str) and self.access_token.get('role'):
                self._extra['role'] = self.access_token.get('role')
            elif self.roles:
                self._extra['role'] = self.roles[0]
        return self._extra.get('role')
    
    @property
    def scopes(self) -> Optional[List[str]]:
        """
        Returns the Scopes
        """
        return ' '.split(self.scope) if self.scope else []
    
    @property
    def value(self) -> Optional[str]:
        """
        Returns the Value
        """
        if self.access_token and not isinstance(self.access_token, str) \
            and self.access_token.value:
            return self.access_token.value
        if self.id_token and not isinstance(self.id_token, str) \
            and self.id_token.value:
            return self.id_token.value
        return self.access_token
    
    @property
    def display_name(self) -> Optional[str]:
        """
        Returns the Display Name
        """
        if 'display_name' not in self._extra:
            if self.id_token and self.id_token.get('name'):
                self._extra['display_name'] = self.id_token.get('name')
            elif self.access_token and self.access_token.get('name'):
                self._extra['display_name'] = self.access_token.get('name')
        return self._extra.get('display_name')


    def merge(self, other: Dict[str, Any]):
        """
        Merges from a token payload
        """
        # This is likely a id_token
        if other.get('email'): 
            # print('Merging ID Token')
            self.id_token.update(other)
        elif other.get('sub'): 
            # print('Merging Access Token')
            self.access_token.update(other)
        return self

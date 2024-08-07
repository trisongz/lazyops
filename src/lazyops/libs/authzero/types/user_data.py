from __future__ import annotations

"""
User data model for Auth0
"""

import time
from .base import BaseModel
from pydantic import Field, model_validator
from typing import Dict, Optional, List, Any

class UserDataBase(BaseModel):
    """
    Base User Data
    """
    username: Optional[str] = None
    family_name: Optional[str] = None
    given_name: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    nickname: Optional[str] = None
    phone_number: Optional[str] = None
    phone_verified: Optional[bool] = None
    picture: Optional[str] = None
    user_metadata: Optional[Dict[Any, Any]] = None
    app_metadata: Optional[Dict[Any, Any]] = None

class AZUserData(UserDataBase):
    """
    User Data
    """
    user_id: str
    multifactor: Optional[List[str]] = None
    expiration_ts: Optional[int] = None

    @model_validator(mode = 'after')
    def set_expiration_ts(self):
        """
        Sets the Expiration Timestamp
        """
        if self.expiration_ts is None: 
            self.expiration_ts = int(time.time()) + (self.settings.user_data_expiration or 60)
        return self
    

    @property
    def is_expired(self) -> bool:
        """
        Returns True if the User Data is Expired
        """
        return self.expiration_ts < int(time.time())




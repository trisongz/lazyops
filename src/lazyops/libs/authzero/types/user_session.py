from __future__ import annotations

"""
User Session
"""

import time

from pydantic import Field, model_validator
from lazyops.libs.abcs.utils.helpers import update_dict

from .base import BaseModel
from typing import Dict, Optional, List, Any, TYPE_CHECKING

class UserSession(BaseModel):
    """
    User Session Data
    """
    user_id: str
    api_key: str
    expiration_ts: Optional[int] = None
    data: Optional[Dict[str, Any]] = Field(default_factory = dict)

    model_config = {'arbitrary_types_allowed': True, 'extra': 'allow'}

    @model_validator(mode = 'after')
    def set_expiration_ts(self):
        """
        Sets the Expiration Timestamp
        """
        if not self.expiration_ts: self.expiration_ts = int(time.time()) + self.settings.user_session_expiration
        return self

    @property
    def is_expired(self) -> bool:
        """
        Returns True if the User Data is Expired
        """
        return self.expiration_ts < int(time.time())
    
    @property
    def ttl(self) -> int:
        """
        Returns the TTL
        """
        return max(self.expiration_ts - int(time.time()), 0)

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
    

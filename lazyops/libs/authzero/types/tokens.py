"""
Tokens
"""
import time
from pydantic import BaseModel, model_validator
from typing import Optional, Union, List, Dict


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    expiration_ts: Optional[int] = None

    @model_validator(mode = 'after')
    def validate_expiration(self):
        """
        Validates the expiration
        """
        if not self.expiration_ts:
            self.expiration_ts = int(time.time()) + (self.expires_in - 45)
        return self
        

    @property
    def is_expired(self) -> bool:
        """
        Returns True if the Token is Expired
        """
        return self.expiration_ts < int(time.time())
    
class AccessToken(Token):
    scope: str


class TokenPayload(BaseModel):
    sub: Optional[int] = None


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
    issued_at: Optional[int] = None

    @model_validator(mode = 'after')
    def validate_expiration(self):
        """
        Validates the expiration
        """
        if self.issued_at is None:
            self.issued_at = int(time.time())
        if self.expiration_ts is None:
            # self.expiration_ts = self.issued_at + 30
            self.expiration_ts = self.issued_at + (self.expires_in - 30)
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


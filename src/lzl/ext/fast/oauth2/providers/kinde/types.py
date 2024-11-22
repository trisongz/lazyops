from __future__ import annotations

"""
Extra Types
"""


from lzo.types import BaseModel, Field, eproperty, model_validator
from typing import Optional, List, Dict, Any, Union, Type, TYPE_CHECKING

class UserInfo(BaseModel):
    """
    User Info
    """

    id: Optional[str] = None
    provided_id: Optional[str] = None
    preferred_email: Optional[str] = None
    username: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    is_suspended: Optional[bool] = None
    picture: Optional[str] = None
    total_sign_ins: Optional[int] = None
    last_signed_in: Optional[str] = None
    created_on: Optional[str] = None

    organizations: Optional[List[str]] = None
    identities: Optional[List[Dict[str, str]]] = None
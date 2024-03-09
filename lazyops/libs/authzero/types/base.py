from __future__ import annotations

"""
Base Types
"""

from pydantic import BaseModel as _BaseModel
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..configs import AuthZeroSettings

class BaseModel(_BaseModel):
    """
    Base Model
    """

    model_config = {'arbitrary_types_allowed': True}

    @property
    def settings(self) -> 'AuthZeroSettings':
        """
        Returns the settings
        """
        from ..utils.lazy import get_az_settings
        return get_az_settings()
    

    @classmethod
    def get_settings(cls) -> 'AuthZeroSettings':
        """
        Returns the settings
        """
        from ..utils.lazy import get_az_settings
        return get_az_settings()
from __future__ import annotations

"""
Base Types
"""

from pydantic import BaseModel as _BaseModel
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..configs import AuthZeroSettings
    from ..flows import AZFlow
    from . import AZResourceSchema, AZResource

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
    
    @classmethod
    def get_flow(cls, name: str, *args, **kwargs) -> 'AZFlow':
        """
        Returns the flow
        """
        from ..utils.lazy import get_az_flow
        return get_az_flow(name, *args, **kwargs)
    
    @classmethod
    def get_resource_schema(cls, name: str) -> 'AZResourceSchema':
        """
        Returns the resource schema
        """
        from ..utils.lazy import get_az_resource_schema
        return get_az_resource_schema(name)
    
    @classmethod
    def get_resource(cls, name: str, *args, **kwargs) -> 'AZResource':
        """
        Returns the resource
        """
        from ..utils.lazy import get_az_resource
        return get_az_resource(name, *args, **kwargs)
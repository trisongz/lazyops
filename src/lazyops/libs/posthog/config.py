from __future__ import annotations

from pydantic import model_validator, PrivateAttr
from lazyops.types import BaseSettings
from lazyops.libs.proxyobj import ProxyObject
from typing import Optional


class PostHogSettings(BaseSettings):
    """
    Posthog Settings
    """

    endpoint: Optional[str] = 'https://app.posthog.com'
    enabled: Optional[bool] = None
    api_key: Optional[str] = None
    project_id: Optional[str] = None

    client_timeout: Optional[float] = 60.0

    batch_size: Optional[int] = 100 # If the total events is greater than this, it will dispatch the batch
    batch_interval: Optional[float] = 60.0 # if the wait duration is greater than this, it will dispatch the batch
    default_retries: Optional[int] = 3
    batched: Optional[bool] = True
    num_workers: Optional[int] = 1
    
    debug_enabled: Optional[bool] = None

    # The internal enabled flag without affecting the user-provided value
    _enabled: Optional[bool] = PrivateAttr(None)

    class Config:
        env_prefix = 'POSTHOG_'
        case_sensitive = False
        extra = 'allow'

    
    @model_validator(mode = 'after')
    def validate_posthog_config(self):
        """
        Validates the Posthog Configuration
        """
        self.update_enabled()
        return self
    
    def update_enabled(self):
        """
        Update the enabled status
        """
        if self.enabled is None: self._enabled = self.api_key is not None
        else: self._enabled = self.enabled
        

    @property
    def is_enabled(self) -> bool:
        """
        Returns True if the Posthog is enabled
        """
        return self._enabled

ph_settings: PostHogSettings = ProxyObject(
    obj_getter = 'lazyops.libs.posthog.utils.get_posthog_settings',
)
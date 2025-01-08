from __future__ import annotations

"""
TemporalIO Config: Worker
"""

import typing as t
from urllib.parse import urlparse
from lzo.types import BaseSettings, model_validator, Field
from lzl.types import eproperty
from lzl.proxied import ProxyObject
from ..utils import logger

if t.TYPE_CHECKING:
    from lzl.io.persistence import TemporaryData
    from temporalio.converter import DataConverter
    from ..registry import TemporalRegistry

class TemporalWorkerConfig(BaseSettings):
    """
    Temporal Worker Configuration
    """
    queue: str = Field(default="")
    name: str = Field(default="")
    identity: t.Optional[str] = Field(None, description = "Identity for this client. If unset, a default is created based on the version of the SDK.")
    namespace: t.Optional[str] = Field(default="")
    interceptors: t.Optional[t.List[str]] = Field(default=None)
    activities: t.Optional[t.List[str]] = Field(default_factory=list)
    workflows: t.Optional[t.List[str]] = Field(default_factory=list)
    
    converter: t.Optional[str] = Field(default=None)
    factory: t.Optional[str] = Field(default=None)
    pre_init: t.Optional[t.List[str]] = Field(default=None)
    max_concurrent_activities: int = Field(default=100)
    max_concurrent_workflow_tasks: int = Field(default=100)
    debug_mode: bool = Field(default=False)
    disable_eager_activity_execution: bool = Field(default=True) # pylint: disable=invalid-name
    metric_bind_address: str = Field(default="0.0.0.0:9000")

    mapping: t.Optional[t.Dict[str, str]] = Field(default=None, description = "Mapping of workflow names to activity names")

    class Config(BaseSettings.Config):
        env_prefix = "TEMPORAL_WORKER_"

    @model_validator(mode = 'before')
    def validate_config_values(cls, values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        """
        Validates the values
        """
        if values.get('mapping') and 'workflows' not in values and 'activities' not in values:
            values['workflows'] = list(values['mapping'].keys())
            values['activities'] = list(values['mapping'].values())
        return values

            



    



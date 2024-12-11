from __future__ import annotations

import typing as t
from .base import RegistryItem
from .main import TemporalRegistry, registry

if t.TYPE_CHECKING:
    from ..mixins import (
        BaseTemporalMixin, TemporalWorkflowMixin, TemporalActivityMixin,
        TemporalMixinT, TemporalWorkflowT, TemporalActivityT, 
        MixinKinds
    )
    from temporalio.types import CallableType, ClassType

from __future__ import annotations

import typing as t
from .base import BaseTemporalMixin, MixinKinds, TemporalInputT, TemporalReturnT
from .workflows import TemporalWorkflowMixin
from .activities import TemporalActivityMixin
from .dispatch import TemporalDispatchMixin, ParamT, ReturnT


TemporalMixinT = t.TypeVar('TemporalMixinT', bound = BaseTemporalMixin)
TmpMixinT = t.TypeVar('TmpMixinT')

TemporalWorkflowT = t.TypeVar('TemporalWorkflowT', bound = TemporalWorkflowMixin)
TemporalActivityT = t.TypeVar('TemporalActivityT', bound = TemporalActivityMixin)
TemporalDispatchT = t.TypeVar('TemporalDispatchT', bound = TemporalDispatchMixin)

TemporalObjT = t.Union[TemporalWorkflowT, TemporalActivityT, TemporalDispatchT]
from __future__ import annotations

"""
Temporal Workflow Mixins: Workflows
"""

import typing as t
from .base import BaseTemporalMixin, MixinKinds

class TemporalWorkflowMixin(BaseTemporalMixin):
    """
    [Temporal] Workflow Mixin that will automatically registered
    """

    mixin_kind: t.Optional[MixinKinds] = 'workflow'
    _is_subclass_: t.Optional[bool] = True

    # These will be passed to the workflow defn decorator
    sandboxed: t.Optional[bool] = None
    dynamic: t.Optional[bool] = None
    failure_exception_types: t.Optional[t.Sequence[t.Type[BaseException]]] = None
    enable_init: t.Optional[bool] = None

    @classmethod
    def configure_registered(cls, **kwargs):
        """
        Configures the registered workflow
        """
        _kws = {k: kwargs.pop(k) for k in kwargs if k in {'sandboxed', 'dynamic', 'failure_exception_types'}}
        new = super().configure_registered(**kwargs)
        if 'sandboxed' in _kws: new.sandboxed = _kws.pop('sandboxed')
        if 'dynamic' in _kws: new.dynamic = _kws.pop('dynamic')
        if _kws.get('failure_exception_types'): new.failure_exception_types = _kws.pop('failure_exception_types')
        return new

    @classmethod
    def _on_register_hook_(cls):
        """
        Runs the workflow hook
        """
        pass


    def _on_init_hook_(self):
        """
        Runs the workflow init hook
        """
        pass

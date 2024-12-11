from __future__ import annotations

"""
Temporal Workflow Mixins: Activities
"""

import typing as t
from .base import BaseTemporalMixin, MixinKinds

class TemporalActivityMixin(BaseTemporalMixin):
    """
    [Temporal] Activity Mixin that will automatically registered
    """

    mixin_kind: t.Optional[MixinKinds] = 'activity'
    _is_subclass_: t.Optional[bool] = True

    # These will be passed to the activity defn decorator
    no_thread_cancel_exception: t.Optional[bool] = None
    dynamic: t.Optional[bool] = None

    include_funcs: t.Optional[t.List[str]] = None
    exclude_funcs: t.Optional[t.List[str]] = None

    @classmethod
    def configure_registered(cls, **kwargs):
        """
        Configures the registered activity
        """
        _kws = {k: kwargs.pop(k) for k in kwargs if k in {'no_thread_cancel_exception', 'dynamic', 'include_funcs', 'exclude_funcs'}}
        new = super().configure_registered(**kwargs)
        if 'no_thread_cancel_exception' in _kws: new.no_thread_cancel_exception = _kws.pop('no_thread_cancel_exception')
        if 'dynamic' in _kws: new.dynamic = _kws.pop('dynamic')
        if 'include_funcs' in _kws: new.include_funcs = _kws.pop('include_funcs')
        if 'exclude_funcs' in _kws: new.exclude_funcs = _kws.pop('exclude_funcs')
        return new

    @classmethod
    def _on_register_hook_(cls):
        """
        Runs the activity hook
        """
        pass

    def _on_init_hook_(self):
        """
        Runs the activity init hook
        """
        pass

from __future__ import annotations

"""
Proxied Types
"""


from lazyops.types.lazydict import LazyDict
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Set, TYPE_CHECKING


if TYPE_CHECKING:
    from lazyops.libs.abcs.state.registry import ClientT
    from lazyops.libs.abcs.configs.base import AppSettings


class BaseProxySource(LazyDict):
    """
    A Proxy Dictionary that lazily defers initialization of the components until they are called
    """
    name: Optional[str] = "proxy"
    source: Optional[str] = None
    kind: Optional[str] = "proxy"
    exclude_schema_attrs: Optional[bool] = True
    components: Optional[List[str]] = None
    proxy_schema: Optional[Dict[str, str]] = None
    _settings: Optional['AppSettings'] = None

    def __init__(self, **kwargs):
        """
        Handles the initialization of the proxy
        """
        self.proxy_schema = {
            kind: f'scout.{self.source}.{kind}' for kind in self.components
        }
        self._dict = {}
        self.excluded_attrs = self.components
        self.post_init(**kwargs)

    @property
    def settings(self) -> 'AppSettings':
        """
        Returns the settings
        """
        if self._settings is None:
            from lazyops.libs.abcs.configs.lazy import get_module_settings
            self._settings = get_module_settings(self.__module__)
        return self._settings
    
    def post_init(self, **kwargs):
        """
        Post Initialization to be overwritten by the subclass
        """
        self.settings.ctx.register_client(self, kind = self.kind)

    def get_or_init(self, name: str, default: Any = None) -> 'ClientT':
        """
        Gets the component
        """
        if name not in self._dict and name not in self.proxy_schema:
            raise ValueError(f"Invalid Client {name} for {self.source}")
        if name not in self._dict:
            self._dict[name] = self.settings.ctx.get_client(name)
        return self._dict[name]

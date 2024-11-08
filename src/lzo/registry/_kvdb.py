from __future__ import annotations

"""
Maintains a Stateful Registry of KVDB Clients
"""

import abc
import copy
from typing import Optional, Dict, Any, List, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from kvdb import KVDBSession, PersistentDict

class KVDBRegistry(abc.ABC):
    """
    The KVDB Registry
    """
    module: Optional[str] = None

    default_serializer: Optional[str] = 'json'
    default_kwargs: Optional[Dict[str, Any]] = {}

    default_pdict_expiration: Optional[int] = None
    default_pdict_kwargs: Optional[Dict[str, Any]] = {}

    default_fdict_serializer: Optional[str] = None # If None, will use the default serializer, or if explicitly 'none' will not use any serializer
    default_fdict_expiration: Optional[int] = -1
    default_fdict_kwargs: Optional[Dict[str, Any]] = {}

    sessions: Dict[str, 'KVDBSession'] = {}
    pdicts: Dict[str, 'PersistentDict'] = {}
    pdict_aliases: Dict[str, str] = {}
    pdict_prefix_module: Optional[bool] = True
    
    _extra: Dict[str, Any] = {}

    def __init__(
        self, 
        module: Optional[str] = None,
        default_serializer: Optional[str] = None,
        default_kwargs: Optional[Dict[str, Any]] = None,
        default_pdict_expiration: Optional[int] = None,
        default_pdict_kwargs: Optional[Dict[str, Any]] = None,
        default_fdict_serializer: Optional[str] = None,
        default_fdict_expiration: Optional[int] = None,
        default_fdict_kwargs: Optional[Dict[str, Any]] = None,
        pdict_prefix_module: Optional[bool] = None,
        **kwargs,
    ):
        """
        The KVDB Registry
        """
        self._extra: Dict[str, Any] = {}
        if module: self.module = module
        if default_serializer: self.default_serializer = default_serializer
        if default_kwargs: self.default_kwargs = default_kwargs
        if default_pdict_expiration: self.default_pdict_expiration = default_pdict_expiration
        if default_pdict_kwargs: self.default_pdict_kwargs = default_pdict_kwargs
        if pdict_prefix_module is not None: self.pdict_prefix_module = pdict_prefix_module
        if default_fdict_serializer: self.default_fdict_serializer = default_fdict_serializer
        elif self.default_serializer is None: self.default_fdict_serializer = self.default_serializer
        if default_fdict_expiration: self.default_fdict_expiration = default_fdict_expiration
        if default_fdict_kwargs: self.default_fdict_kwargs = default_fdict_kwargs

        if not self.module: self.pdict_prefix_module = False
        self.post_init(**kwargs)

    def post_init(self, **kwargs):
        """
        Post Initialization
        """
        pass

    @property
    def module_prefix(self) -> str:
        """
        Returns the module prefix
        """
        return self.module
    
    def _build_kwargs(self, src_kwargs: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Builds the kwargs
        """
        _kwargs = copy.deepcopy(src_kwargs)
        if kwargs: _kwargs.update(kwargs)
        return _kwargs

    def get(
        self, 
        name: Optional[str] = None,
        serializer: Optional[str] = None,
        **kwargs,
    ) -> 'KVDBSession':
        """
        Gets the KVDB Session
        """
        if name is None: name = self.module or 'global'
        if name not in self.sessions:
            from kvdb import KVDBClient
            serializer = serializer or self.default_serializer
            if serializer == 'none': serializer = None
            if self.default_kwargs: kwargs = self._build_kwargs(self.default_kwargs, **kwargs)
            self.sessions[name] = KVDBClient.get_session(
                name = name,
                serializer = serializer,
                **kwargs,
            )
        return self.sessions[name]

    def pdict(
        self, 
        base_key: str,
        expiration: Optional[int] = None,
        aliases: Optional[List[str]] = None,
        **kwargs,
    ) -> 'PersistentDict':
        """
        Returns the Persistent Dict for data
        """
        if self.pdict_prefix_module:
            if self.module_prefix not in base_key: base_key = f'{self.module_prefix}.{base_key}'
        if base_key not in self.pdicts and base_key not in self.pdict_aliases:
            session = self.get(f'{self.module_prefix}.persistence' if self.module else 'persistence', serializer = 'none', url = kwargs.pop('url', None))
            if expiration is None and self.default_pdict_expiration: expiration = self.default_pdict_expiration
            if expiration is not None and expiration <= 0: expiration = None
            if self.default_pdict_kwargs: kwargs = self._build_kwargs(self.default_pdict_kwargs, **kwargs)
            self.pdicts[base_key] = session.create_persistence(
                base_key = base_key,
                expiration = expiration,
                **kwargs,
            )
            if aliases:
                for alias in aliases:
                    self.pdict_aliases[alias] = base_key
        elif base_key in self.pdict_aliases:
            base_key = self.pdict_aliases[base_key]
        return self.pdicts[base_key]

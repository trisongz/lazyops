from __future__ import annotations

"""Helpers for maintaining stateful KVDB client registries."""

import abc
import copy
import typing as t

if t.TYPE_CHECKING:
    from kvdb import KVDBSession, PersistentDict

__all__ = ['KVDBRegistry']


class KVDBRegistry(abc.ABC):
    """Manage shared KVDB sessions and persistent dictionaries for a module."""

    module: t.Optional[str] = None

    default_serializer: t.Optional[str] = 'json'
    default_kwargs: t.Dict[str, t.Any] = {}

    default_pdict_expiration: t.Optional[int] = None
    default_pdict_kwargs: t.Dict[str, t.Any] = {}

    # If ``None`` we fall back to ``default_serializer``; if ``'none'`` we skip serialisation
    default_fdict_serializer: t.Optional[str] = None
    default_fdict_expiration: t.Optional[int] = -1
    default_fdict_kwargs: t.Dict[str, t.Any] = {}

    sessions: t.Dict[str, 'KVDBSession'] = {}
    pdicts: t.Dict[str, 'PersistentDict'] = {}
    pdict_aliases: t.Dict[str, str] = {}
    pdict_prefix_module: t.Optional[bool] = True

    _extra: t.Dict[str, t.Any] = {}

    def __init__(
        self,
        module: t.Optional[str] = None,
        default_serializer: t.Optional[str] = None,
        default_kwargs: t.Optional[t.Mapping[str, t.Any]] = None,
        default_pdict_expiration: t.Optional[int] = None,
        default_pdict_kwargs: t.Optional[t.Mapping[str, t.Any]] = None,
        default_fdict_serializer: t.Optional[str] = None,
        default_fdict_expiration: t.Optional[int] = None,
        default_fdict_kwargs: t.Optional[t.Mapping[str, t.Any]] = None,
        pdict_prefix_module: t.Optional[bool] = None,
        **kwargs: t.Any,
    ) -> None:
        """Configure default serialisation options for KVDB resources."""

        self._extra = {}
        if module:
            self.module = module
        if default_serializer:
            self.default_serializer = default_serializer
        if default_kwargs:
            self.default_kwargs = dict(default_kwargs)
        if default_pdict_expiration:
            self.default_pdict_expiration = default_pdict_expiration
        if default_pdict_kwargs:
            self.default_pdict_kwargs = dict(default_pdict_kwargs)
        if pdict_prefix_module is not None:
            self.pdict_prefix_module = pdict_prefix_module
        if default_fdict_serializer:
            self.default_fdict_serializer = default_fdict_serializer
        elif self.default_serializer is None:
            self.default_fdict_serializer = self.default_serializer
        if default_fdict_expiration:
            self.default_fdict_expiration = default_fdict_expiration
        if default_fdict_kwargs:
            self.default_fdict_kwargs = dict(default_fdict_kwargs)

        if not self.module:
            self.pdict_prefix_module = False
        self.post_init(**kwargs)

    def post_init(self, **kwargs: t.Any) -> None:  # pragma: no cover - hook for subclasses
        """Finalise subclass configuration after initial settings are applied."""

    @property
    def module_prefix(self) -> t.Optional[str]:
        """Return the prefix applied to session and persistence names."""

        return self.module

    def _build_kwargs(self, src_kwargs: t.Mapping[str, t.Any], **kwargs: t.Any) -> t.Dict[str, t.Any]:
        """Clone ``src_kwargs`` and merge ``kwargs`` without mutating inputs."""

        merged = copy.deepcopy(src_kwargs)
        if kwargs:
            merged.update(kwargs)
        return merged

    def get(
        self,
        name: t.Optional[str] = None,
        serializer: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> 'KVDBSession':
        """Fetch or create a named KVDB session."""

        session_name = name or self.module_prefix or 'global'
        if session_name not in self.sessions:
            from kvdb import KVDBClient

            effective_serializer = serializer or self.default_serializer
            if effective_serializer == 'none':
                effective_serializer = None
            if self.default_kwargs:
                kwargs = self._build_kwargs(self.default_kwargs, **kwargs)
            self.sessions[session_name] = KVDBClient.get_session(
                name=session_name,
                serializer=effective_serializer,
                **kwargs,
            )
        return self.sessions[session_name]

    def pdict(
        self,
        base_key: str,
        expiration: t.Optional[int] = None,
        aliases: t.Optional[t.Iterable[str]] = None,
        **kwargs: t.Any,
    ) -> 'PersistentDict':
        """Return a persistent dictionary scoped to ``base_key``.

        Args:
            base_key: Identifier for the persistence bucket.
            expiration: Optional TTL applied during creation. ``<=0`` disables.
            aliases: Alternate keys that reference the same dictionary.
            **kwargs: Additional arguments forwarded to ``create_persistence``.
        """

        effective_key = base_key
        if self.pdict_prefix_module and self.module_prefix and self.module_prefix not in effective_key:
            effective_key = f'{self.module_prefix}.{effective_key}'

        if effective_key not in self.pdicts and effective_key not in self.pdict_aliases:
            persistence_session = self.get(
                f'{self.module_prefix}.persistence' if self.module_prefix else 'persistence',
                serializer='none',
                url=kwargs.pop('url', None),
            )
            ttl = expiration
            if ttl is None and self.default_pdict_expiration:
                ttl = self.default_pdict_expiration
            if ttl is not None and ttl <= 0:
                ttl = None
            if self.default_pdict_kwargs:
                kwargs = self._build_kwargs(self.default_pdict_kwargs, **kwargs)
            self.pdicts[effective_key] = persistence_session.create_persistence(
                base_key=effective_key,
                expiration=ttl,
                **kwargs,
            )
            if aliases:
                for alias in aliases:
                    self.pdict_aliases[alias] = effective_key
        elif effective_key in self.pdict_aliases:
            effective_key = self.pdict_aliases[effective_key]

        return self.pdicts[effective_key]

from __future__ import annotations

"""Mapping utilities that lazily initialise components on first use."""

import collections.abc
import typing as t

KT = t.TypeVar("KT")
VT = t.TypeVar("VT")
DictValue = t.Union[VT, t.Callable[[], VT], t.Tuple[str, t.Dict[str, t.Any]], str, t.Any]


class ProxyDict(collections.abc.MutableMapping, t.MutableMapping[KT, VT]):
    """Dictionary-like container that defers constructing its values."""

    _dict: t.Dict[KT, DictValue] = {}
    _initialized: t.Dict[KT, bool] = {}
    _excluded_attrs: t.Set[str] = set()
    _pdict_attrs: t.Set[str] = {
        "get_or_init",
        "keys",
        "values",
        "items",
        "get",
        "clear",
        "pop",
        "popitem",
        "setdefault",
        "initialize_objects",
        "update",
        "post_init",
        "pre_init",
        "cls_init",
        "cls_post_init",
        "proxy_schema",
        "module",
        "components",
        "_init_component",
        "_prevalidate_component",
        "_init_default",
    }

    module: str | None = None
    components: t.Optional[t.List[str]] = None
    proxy_schema: t.Optional[t.Dict[str, str]] = {}
    initialize_objects: bool = False

    def __init__(
        self,
        initialize_objects: bool | None = None,
        module: str | None = None,
        components: t.Optional[t.List[str]] = None,
        proxy_schema: t.Optional[t.Dict[str, str]] = None,
        **kwargs: t.Any,
    ) -> None:
        """Configure module metadata and optionally pre-initialise components."""

        self.cls_init(**kwargs)
        if initialize_objects is not None:
            self.initialize_objects = initialize_objects
        if module is not None:
            self.module = module
        if components is not None:
            self.components = components
        if proxy_schema is not None:
            self.proxy_schema = proxy_schema
        self.cls_post_init(**kwargs)
        self.pre_init(**kwargs)
        self.post_init(**kwargs)

    def cls_init(self, **kwargs: t.Any) -> None:
        """Hook executed before instance level configuration is applied."""

    def cls_post_init(self, **kwargs: t.Any) -> None:
        """Hook executed after class-level configuration has run."""

    def pre_init(self, **kwargs: t.Any) -> "ProxyDict[KT, VT]":
        """Normalise component metadata before instance initialisation."""

        if self.components:
            for component in self.components:
                if component not in self.proxy_schema:
                    ref_name = f"{self.module}.{component}" if self.module else component
                    self.proxy_schema[component] = ref_name
        return self

    def post_init(self, **kwargs: t.Any) -> None:
        """Extension hook for subclasses; no-op by default."""

    def __init_subclass__(cls: type["ProxyDict"], **kwargs: t.Any) -> None:
        """Reset class-level caches for each subclass and track custom attrs."""

        super().__init_subclass__(**kwargs)
        cls._dict = {}
        cls._initialized = {}
        for attr in dir(cls):
            if attr in cls._pdict_attrs or attr.startswith("_"):
                continue
            cls._pdict_attrs.add(attr)

    def _init_component(self, name: KT, default: VT | None = None) -> None:
        """Subclasses can override to eagerly populate ``name``."""

    def _prevalidate_component(self, name: KT) -> None:
        """Validate ``name`` before attempting to initialise it."""

    def _init_default(self, name: KT) -> None:
        """Materialise the underlying object for ``name`` based on schema hints."""

        from lzl.load import lazy_import

        value = self._dict[name]
        if isinstance(value, str):
            value = lazy_import(value)
            if self.initialize_objects:
                value = value()
        elif isinstance(value, tuple):
            obj_class, kwargs = value
            if isinstance(obj_class, str):
                obj_class = lazy_import(obj_class)
            for key, val in kwargs.items():
                if callable(val):
                    kwargs[key] = val()
            value = obj_class(**kwargs)
        elif isinstance(value, dict):
            value = type(self)(value)
        elif isinstance(value, type):
            value = value()
        self._dict[name] = value
        self._initialized[name] = True

    def get_or_init(self, name: KT, default: VT | None = None) -> VT:
        """Return ``name`` initialising it when absent."""

        if name not in self._dict:
            self._prevalidate_component(name)
            if name in (self.proxy_schema or {}):
                self._init_component(name, default)
                self._initialized[name] = True
            elif default is not None:
                self._dict[name] = default
            else:
                raise ValueError(f"Default value for {name} is None")
        if name not in self._initialized:
            self._init_default(name)
        return t.cast(VT, self._dict[name])

    def __getattr__(self, name: str) -> VT:
        """Proxy attribute access into the backing dictionary."""

        if (
            (name.startswith("__") and name.endswith("__"))
            or name.startswith("_r")
            or name in self._excluded_attrs
            or name in self._pdict_attrs
        ):
            return super().__getattr__(name)  # type: ignore[misc]
        return self.get_or_init(t.cast(KT, name), None)

    def __setattr__(self, name: str, value: VT) -> None:
        """Store ``value`` in the backing dictionary unless reserved."""

        if (
            (name.startswith("__") and name.endswith("__"))
            or name.startswith("_r")
            or name in self._excluded_attrs
            or name in self._pdict_attrs
        ):
            super().__setattr__(name, value)
            return
        self._dict[t.cast(KT, name)] = value

    def __getitem__(self, name: KT) -> VT:
        return self.get_or_init(name, None)

    def __setitem__(self, name: KT, value: VT) -> None:
        self._dict[name] = value

    def __contains__(self, name: KT) -> bool:  # type: ignore[override]
        return name in self._dict

    def __repr__(self) -> str:
        return repr(self._dict)

    def __str__(self) -> str:
        return str(self._dict)

    def __len__(self) -> int:
        return len(self._dict)

    def __iter__(self) -> t.Iterator[KT]:
        return iter(self._dict)

    def __delitem__(self, key: KT) -> None:
        del self._dict[key]

    def keys(self) -> t.KeysView[KT]:
        return self._dict.keys()

    def values(self) -> t.ValuesView[VT]:
        return t.cast(t.ValuesView[VT], self._dict.values())

    def items(self) -> t.ItemsView[KT, VT]:
        return t.cast(t.ItemsView[KT, VT], self._dict.items())

    def get(self, name: KT, default: VT | None = None) -> VT:
        return self.get_or_init(name, default)


__all__ = ["ProxyDict", "DictValue"]

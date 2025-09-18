from __future__ import annotations

"""Abstract base class that wires :class:`Client` into application services."""

import typing as t
from abc import ABC

from httpx._models import Request, Response

from .client import Client


class ApiClient(ABC):
    """Thin wrapper exposing the :class:`Client` API for easy subclassing."""

    _api: t.Optional[Client] = None

    def __init__(self, **kwargs: t.Any) -> None:
        """Run optional pre/post hooks to customise client initialization."""

        self.pre_init(**kwargs)
        self.post_init(**kwargs)

    def pre_init(self, **kwargs: t.Any) -> None:
        """Hook executed before :class:`Client` creation."""

    def post_init(self, **kwargs: t.Any) -> None:
        """Hook executed after :class:`Client` creation."""

    def init_client(self, **kwargs: t.Any) -> None:
        """Instantiate the underlying :class:`Client` lazily."""

        self._api = Client(**kwargs)

    async def ainit_client(self, **kwargs: t.Any) -> None:
        """Asynchronous variant of :meth:`init_client` for parity."""

        self._api = Client(**kwargs)

    @property
    def api(self) -> Client:
        """Return the lazily-initialised :class:`Client` instance."""

        if self._api is None:
            self.init_client()
        return self._api

    async def aget(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.async_get`."""

        return await self.api.async_get(*args, **kwargs)

    async def aput(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.async_put`."""

        return await self.api.async_put(*args, **kwargs)

    async def apost(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.async_post`."""

        return await self.api.async_post(*args, **kwargs)

    async def adelete(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.async_delete`."""

        return await self.api.async_delete(*args, **kwargs)

    async def apatch(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.async_patch`."""

        return await self.api.async_patch(*args, **kwargs)

    async def arequest(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.async_request`."""

        return await self.api.async_request(*args, **kwargs)

    async def astream(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.async_stream`."""

        return await self.api.async_stream(*args, **kwargs)

    async def _abuild_request(self, *args: t.Any, **kwargs: t.Any) -> Request:
        """Proxy :meth:`Client.async_build_request`."""

        return await self.api.async_build_request(*args, **kwargs)

    def get(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.get`."""

        return self.api.get(*args, **kwargs)

    def put(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.put`."""

        return self.api.put(*args, **kwargs)

    def post(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.post`."""

        return self.api.post(*args, **kwargs)

    def delete(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.delete`."""

        return self.api.delete(*args, **kwargs)

    def patch(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.patch`."""

        return self.api.patch(*args, **kwargs)

    def request(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.request`."""

        return self.api.request(*args, **kwargs)

    def stream(self, *args: t.Any, **kwargs: t.Any) -> Response:
        """Proxy :meth:`Client.stream`."""

        return self.api.stream(*args, **kwargs)

    def _build_request(self, *args: t.Any, **kwargs: t.Any) -> Request:
        """Proxy :meth:`Client.build_request`."""

        return self.api.build_request(*args, **kwargs)

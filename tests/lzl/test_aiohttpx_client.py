import asyncio
import typing as t

import httpx

from lzl.api.aiohttpx.client import Client


def _html_response(request: httpx.Request) -> httpx.Response:
    document = "<html><head><title>ok</title></head><body>ready</body></html>"
    return httpx.Response(200, text=document)


def _json_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"method": request.method, "url": str(request.url)})


def test_client_sync_get_uses_mock_transport() -> None:
    transport = httpx.MockTransport(_html_response)
    client = Client(base_url="https://example.org", transport=transport, retries=0, soup_enabled=True)

    with client as session:
        response = session.get("/html")

    assert response.status_code == 200
    assert hasattr(response.__class__, "soup")


def test_client_async_get_uses_mock_transport() -> None:
    transport = httpx.MockTransport(_json_response)

    async def _runner() -> t.Dict[str, t.Any]:
        async with Client(base_url="https://example.org", async_transport=transport, retries=0) as session:
            response = await session.async_get("/ping")
        return response.json()

    payload = asyncio.run(_runner())
    assert payload["method"] == "GET"
    assert payload["url"].endswith("/ping")

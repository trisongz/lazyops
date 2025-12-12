import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from lzl.api.aiohttpx import Client

def test_client_get():
    """
    Test basic GET request using manual async execution
    """
    async def _test_get():
        # Mocking at the httpx level because Client wraps it
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value={"status": "ok"})
            mock_response.text = "OK"
            mock_request.return_value = mock_response

            from lzl.api.aiohttpx import Client
            client = Client()
            
            # Test Async
            response = await client.async_get("https://example.com/api")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            
            # Verify mock called
            assert mock_request.called

    import anyio
    anyio.run(_test_get)


def test_client_context_manager():
    """
    Test Context Manager
    """
    async def _test_ctx():
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            from lzl.api.aiohttpx import Client
            async with Client() as client:
                await client.async_get("https://example.com/")
                assert mock_request.called

    import anyio
    anyio.run(_test_ctx)

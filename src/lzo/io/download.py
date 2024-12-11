from __future__ import annotations

"""
File Download Utilities
"""
import tempfile
import contextlib
from lzl import load
from .resolver import get_http_download_headers, normalize_url
from typing import Optional, List, Dict, Tuple, Union, TYPE_CHECKING

if load.TYPE_CHECKING:
    import aiofiles
    from lzl.api import aiohttpx
    from lzl.api.aiohttpx import Response
else:
    aiofiles = load.LazyLoad("aiofiles", install_missing=True)
    aiohttpx = load.lazy_load('lzl.api.aiohttpx', install_missing = False)

def download_url_to_bytes(
    url: str,
    follow_redirects: Optional[bool] = True,
    verbose: Optional[bool] = True,
    return_response: Optional[bool] = False,
    **kwargs,
) -> Optional[Union[bytes, Tuple[bytes, 'Response']]]:
    """
    Downloads the url to a tempfile
    """
    from lzo.utils import logger
    url = normalize_url(url)
    with contextlib.suppress(Exception):
        with aiohttpx.Client() as client:
            response = client.get(url, follow_redirects = follow_redirects, **kwargs)
            if response.status_code > 400:
                if verbose: logger.error(f"[{response.status_code}] Error fetching url {url}\n{response.text[:1000]}...")
                if return_response: return (None, response)
                return
            return (response.read(), response) if return_response else response.read()


async def adownload_url_to_bytes(
    url: str,
    follow_redirects: Optional[bool] = True,
    verbose: Optional[bool] = True,
    return_response: Optional[bool] = False,
    **kwargs,
) -> Optional[Union[bytes, Tuple[bytes, 'Response']]]:
    """
    Downloads the url to a tempfile
    """
    from lzo.utils import logger
    url = normalize_url(url)
    with contextlib.suppress(Exception):
        async with aiohttpx.Client() as client:
            response = await client.async_get(url, follow_redirects = follow_redirects, **kwargs)
            if response.status_code > 400:
                if verbose: logger.error(f"[{response.status_code}] Error fetching url {url}\n{response.text[:1000]}...")
                if return_response: return (None, response)
                return
            return (response.read(), response) if return_response else response.read()


def download_url_to_tempfile(
    url: str,
    follow_redirects: Optional[bool] = True,
    verbose: Optional[bool] = True,
    **kwargs,
) -> Optional[str]:
    """
    Downloads the url to a tempfile
    """
    # from lzo.utils import logger
    from lazyops.utils import Timer, logger
    t = Timer()
    tmp_file = None
    headers = kwargs.pop('headers', None)
    headers = headers or get_http_download_headers()
    file_bytes, response = download_url_to_bytes(url, follow_redirects = follow_redirects, headers = headers, return_response = True, **kwargs)
    if not file_bytes: return None
    with contextlib.suppress(Exception):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_file = f.name
            f.write(file_bytes)
            f.flush()
            if verbose: logger.info(f"[{response.status_code}] Saved {url} to {tmp_file} in {t.duration_s}", colored = True)
            return tmp_file

async def adownload_url_to_tempfile(
    url: str,
    follow_redirects: Optional[bool] = True,
    verbose: Optional[bool] = True,
    **kwargs,
) -> Optional[str]:
    """
    Downloads the url to a tempfile
    """
    # from lzo.utils import logger
    from lazyops.utils import Timer, logger
    t = Timer()
    tmp_file = None
    headers = kwargs.pop('headers', None)
    headers = headers or get_http_download_headers()
    file_bytes, response = await adownload_url_to_bytes(url, follow_redirects = follow_redirects, headers = headers, return_response = True, **kwargs)
    if not file_bytes: return None
    async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as f:
        tmp_file = f.name
        await f.write(file_bytes)
        await f.flush()
        if verbose: logger.info(f"[{response.status_code}] Saved {url} to {tmp_file} in {t.duration_s}", colored = True)
        return tmp_file


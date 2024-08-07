from __future__ import annotations

"""
HTTP Utilities
"""
import socket
import functools
import contextlib
from urllib.parse import urlparse
from lazyops.libs import lazyload
from typing import Optional, List, Dict, TYPE_CHECKING

if lazyload.TYPE_CHECKING:
    import pythonping
    import aiohttpx
    import tldextract
    import async_lru
else:
    pythonping = lazyload.LazyLoad("pythonping")
    aiohttpx = lazyload.LazyLoad("aiohttpx")
    tldextract = lazyload.LazyLoad("tldextract")
    async_lru = lazyload.LazyLoad("async_lru")

def normalize_url(url: str) -> str:
    """
    Normalizes the URL
    """
    url = url.lower()
    url = url.replace('http//', '').replace('https//', '').replace('htpps://', '').replace('htp://', '')
    if '@' in url: url = url.split('@')[-1]
    if url.startswith('www://'): url = url.replace('www://', 'www.')
    if not url.startswith('http://') and not url.startswith('https://'): url = f'https://{url}'
    return url.replace('http://', 'https://').rstrip('/')

_http_download_headers: Dict[str, str] = None

def get_http_download_headers() -> Dict[str, str]:
    """
    Returns the http download headers
    """
    global _http_download_headers
    if _http_download_headers is None:
        try:
            from browserforge.headers import HeaderGenerator
            _http_download_headers = HeaderGenerator().generate(browser='chrome')
        except ImportError:
            _http_download_headers = {
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'accept-language': 'en-US,en;q=0.9',
                'accept-encoding': 'gzip, deflate, br',
                'cache-control': 'no-cache',
            }
    return _http_download_headers


async def adownload_url_to_tempfile(
    url: str,
    follow_redirects: Optional[bool] = True,
    verbose: Optional[bool] = True,
    **kwargs,
) -> Optional[str]:
    """
    Downloads the url to a tempfile
    """
    import aiofiles
    import aiohttpx
    from lazyops.utils import Timer, logger

    t = Timer()
    tmp_file = None
    
    headers = kwargs.pop('headers', None)
    headers = headers or get_http_download_headers()

    with contextlib.suppress(Exception):
        async with aiohttpx.Client(follow_redirects = follow_redirects) as client:
            url = normalize_url(url)
            response = await client.async_get(url, headers = headers, **kwargs)
            if response.status_code > 400:
                logger.error(f"[{response.status_code}] Error fetching url {url}\n{response.text[:1000]}...")
                return

            async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as f:
                tmp_file = f.name
                await f.write(response.read())
                await f.flush()
                if verbose: logger.info(f"[{response.status_code}] Saved {url} to {tmp_file} in {t.duration_s}", colored = True)

        return tmp_file



async def adownload_url_to_bytes(
    url: str,
    follow_redirects: Optional[bool] = True,
    verbose: Optional[bool] = True,
    **kwargs,
) -> Optional[bytes]:
    """
    Downloads the url to a tempfile
    """
    import aiohttpx
    from lazyops.utils import logger
    url = normalize_url(url)
    # headers = kwargs.pop('headers', None)
    # headers = headers or get_http_download_headers()
    # headers['Accept'] = '*/*'
    # logger.info(headers)
    with contextlib.suppress(Exception):
        async with aiohttpx.Client() as client:
            # response = await client.async_get(url, follow_redirects = follow_redirects, headers = headers, **kwargs)
            response = await client.async_get(url, follow_redirects = follow_redirects, **kwargs)
            if response.status_code > 400:
                if verbose: logger.error(f"[{response.status_code}] Error fetching url {url}\n{response.text[:1000]}...")
                return
            return response.read()


async def adownload_batch_urls_to_tempfiles(
    urls: List[str],
    follow_redirects: Optional[bool] = True,
    verbose: Optional[bool] = True,
    **kwargs,
) -> List[str]:
    """
    Downloads the urls to a tempfile
    """
    import niquests
    import aiofiles
    from lazyops.utils import Timer, logger

    t = Timer()
    responses: List[niquests.AsyncResponse] = []
    tmp_files: List[str] = []
    headers = kwargs.pop('headers', None)
    headers = headers or get_http_download_headers()

    async with niquests.AsyncSession(multiplexed=True) as s:
        for url in urls:
            url = normalize_url(url)
            try:
                responses.append(await s.get(url, allow_redirects = follow_redirects, stream = True, headers = headers, **kwargs))
                
            except Exception as e:
                if verbose: logger.error(f"[{e.__class__.__name__}] Error fetching url {url}\n{e}")
                continue
        await s.gather()
        for response in responses:
            if response.status_code > 400:
                logger.error(f"[{response.status_code}] Error fetching url {response.url}: {(await response.text)[:100]}...")
                continue
            async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as f:
                tmp_file = f.name
                async for chunk in await response.iter_content():
                    await f.write(chunk)
                await f.flush()
                if verbose: logger.info(f"[{response.status_code}] Saved {response.url} to {tmp_file} in {t.duration_s}", colored = True)
            tmp_files.append(tmp_file)

    if verbose: logger.info(f"Saved {len(tmp_files)} files in {t.duration_s}", colored = True)
    return tmp_files
    

def validate_website_with_ping(
    url: str,
    timeout: Optional[int] = 2,
    count: Optional[int] = 4,
) -> bool:
    """
    Validates a website
    """
    url = normalize_url(url)
    ping_results = pythonping.ping(url, count = count, timeout = timeout)
    return ping_results.success(3)


def validate_website_with_socket(
    url: str,
) -> bool:
    """
    Validates a website
    """
    url = extract_clean_domain(url)
    with contextlib.suppress(Exception):
        socket.gethostbyname(url)
        return True
    return False

def validate_website_with_httpx(
    url: str,
    timeout: Optional[int] = 15,
    headers: Optional[Dict[str, str]] = None,
    **kwargs,
) -> bool:
    """
    Validates a website
    """
    url = normalize_url(url)
    try:
        # Try with head first
        headers = headers or get_http_download_headers()
        response = aiohttpx.head(url, timeout = timeout, headers = headers,follow_redirects = True)
        if response.status_code == 405:
            response = aiohttpx.get(url, timeout = timeout, headers = headers, follow_redirects = True)
        response.raise_for_status()
        return True
    except (aiohttpx.ConnectTimeout, aiohttpx.ReadTimeout) as e:
        return False
    except aiohttpx.HTTPStatusError as e:
        return e.response.status_code < 500
    except Exception as e:
        return False
    
async def avalidate_website_with_httpx(
    url: str,
    timeout: Optional[int] = 15,
    headers: Optional[Dict[str, str]] = None,
    **kwargs,
) -> bool:
    """
    Validates a website
    """
    url = normalize_url(url)
    try:
        # Try with head first
        headers = headers or get_http_download_headers()
        response = await aiohttpx.async_head(url, timeout = timeout, headers = headers, follow_redirects = True)
        if response.status_code == 405:
            response = await aiohttpx.async_get(url, headers = headers, timeout = timeout, follow_redirects = True)
        response.raise_for_status()
        return True
    except (aiohttpx.ConnectTimeout, aiohttpx.ReadTimeout) as e:
        return False
    except aiohttpx.HTTPStatusError as e:
        return e.response.status_code < 500
    except Exception as e:
        return False


@functools.lru_cache(500)
def extract_registered_domain(url: str) -> str:
    """
    Returns the domain
    """
    return tldextract.extract(url).registered_domain


def extract_clean_domain(
    url: str
) -> str:
    """
    Extracts and cleans the domain
    """
    domain = extract_registered_domain(url.lower())
    if domain.startswith('www.'): domain = domain.replace('www.', '')
    return domain.lower()


@functools.lru_cache()
def extract_root_domain(url: str, attempts: Optional[int] = None) -> str:
    """
    Returns the root domain of a website after redirection
    """
    if url.startswith('www://'): url = url.replace('www://', '')
    if not url.startswith('http'): url = f'https://{url}'
    try:
        with aiohttpx.Client(follow_redirects = True, verify = False) as client:
            r = client.get(url, timeout = 5)
        r.raise_for_status()
        return str(r.url).rstrip('/')
    except (aiohttpx.ConnectTimeout, aiohttpx.ReadTimeout) as e:
        return url
    except aiohttpx.HTTPStatusError as e:
        return str(e.response.url).rstrip('/') if e.response.status_code < 500 else url
    except Exception as e:
        attempts = attempts + 1 if attempts else 1
        if attempts > 2:
            return None
        new_url = f'https://{extract_registered_domain(url)}'
        return extract_root_domain(new_url, attempts = attempts)


@async_lru.alru_cache(maxsize=1200)
async def aextract_root_domain(url: str, attempts: Optional[int] = None) -> str:
    """
    Returns the root domain after redirection
    """
    if url.startswith('www://'): url = url.replace('www://', '')
    if not url.startswith('http'): url = f'https://{url}'
    try:
        async with aiohttpx.Client(follow_redirects = True, verify = False) as client:
            r = await client.async_get(url, timeout = 5)
        r.raise_for_status()
        return str(r.url).rstrip('/')
    except (aiohttpx.ConnectTimeout, aiohttpx.ReadTimeout) as e:
        return url
    except aiohttpx.HTTPStatusError as e:
        return str(e.response.url).rstrip('/') if e.response.status_code < 500 else url
    except Exception as e:
        attempts = attempts + 1 if attempts else 1
        if attempts > 2:
            return None
        new_url = f'https://{extract_registered_domain(url)}'
        return await aextract_root_domain(new_url, attempts = attempts)



@functools.lru_cache(maxsize=1200)
def validate_hostname(url: str) -> bool:
    """
    Validates the hostname
    """    
    hostname = urlparse(url).hostname if '://' in url else url
    with contextlib.suppress(Exception):
        socket.gethostbyname(hostname)
        return True
    return False


def validate_website_exists(
    url: str,
    timeout: Optional[int] = 15,
    headers: Optional[Dict[str, str]] = None,
    soft_validate: Optional[bool] = False,
) -> bool:
    """
    Validates the website exists
    """
    url = normalize_url(url)
    hn_valid = validate_website_with_ping(url)
    if soft_validate or not hn_valid: return hn_valid
    return validate_website_with_httpx(url, headers = headers, timeout = timeout)



async def avalidate_website_exists(
    url: str,
    timeout: Optional[int] = 15,
    headers: Optional[Dict[str, str]] = None,
    soft_validate: Optional[bool] = False,
) -> bool:
    """
    Validates the website exists
    """
    url = normalize_url(url)
    hn_valid = validate_website_with_ping(url)
    if soft_validate or not hn_valid: return hn_valid
    return await avalidate_website_with_httpx(url, headers = headers, timeout = timeout)


def determine_invalid_domains(
    urls: List[str],
    timeout: Optional[int] = 4,
) -> List[str]:
    """
    Determines the invalid domains
    """
    if not urls: return []
    return [
        url
        for url in urls
        if not validate_website_with_ping(url, timeout=timeout)
    ]


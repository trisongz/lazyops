from __future__ import annotations

"""
HTTP / DNS Resolver Utilities
"""

import time
import socket
import functools
import contextlib
from urllib.parse import urlparse
from lzl import load
from typing import Optional, List, Dict, TYPE_CHECKING

if load.TYPE_CHECKING:
    import pythonping
    import tldextract
    import async_lru
    from lzl.api import aiohttpx
else:
    pythonping = load.LazyLoad("pythonping")
    aiohttpx = load.lazy_load('lzl.api.aiohttpx', install_missing = False)
    tldextract = load.LazyLoad("tldextract")
    async_lru = load.LazyLoad("async_lru")


def normalize_url(url: str) -> str:
    """
    Normalizes a URL string to a standard HTTPS format.

    Handles various edge cases like missing schemes, 'www://', and malformed prefixes.

    Args:
        url: The URL string to normalize.

    Returns:
        The normalized URL starting with 'https://'.
    """
    url = url.lower()
    url = url.replace('http//', '').replace('https//', '').replace('htpps://', '').replace('htp://', '')
    if '@' in url: url = url.split('@')[-1]
    if url.startswith('www://'): url = url.replace('www://', 'www.')
    if not url.startswith('http://') and not url.startswith('https://'): url = f'https://{url}'
    return url.replace('http://', 'https://').rstrip('/')


@functools.lru_cache(500)
def extract_registered_domain(url: str) -> str:
    """
    Extracts the registered domain (e.g., 'google.com' from 'sub.google.com') using tldextract.

    Args:
        url: The URL to extract the domain from.

    Returns:
        The registered domain string.
    """
    return tldextract.extract(url).registered_domain

def extract_clean_domain(
    url: str
) -> str:
    """
    Extracts the registered domain and removes any leading 'www.'.

    Args:
        url: The URL to process.

    Returns:
        The cleaned domain string.
    """
    domain = extract_registered_domain(url.lower())
    if domain.startswith('www.'): domain = domain.replace('www.', '')
    return domain.lower()

_http_download_headers: Optional[Dict[str, str]] = None

def get_http_download_headers() -> Dict[str, str]:
    """
    Retrieves HTTP headers suitable for mimicking a real browser.

    Uses `browserforge` if available; otherwise falls back to a hardcoded Chrome-like user agent.

    Returns:
        A dictionary of HTTP headers.
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



"""
Validators
"""

def validate_website_with_ping(
    url: str,
    timeout: Optional[int] = 2,
    count: Optional[int] = 4,
) -> bool:
    """
    Validates a website's reachability using ICMP ping.

    Args:
        url: The URL or hostname to ping.
        timeout: Timeout in seconds for each ping.
        count: Number of ping attempts.

    Returns:
        True if the host is reachable (success count >= 3), False otherwise.
    """
    url = normalize_url(url)
    ping_results = pythonping.ping(url, count = count, timeout = timeout)
    return ping_results.success(3)


def validate_website_with_socket(
    url: str,
) -> bool:
    """
    Validates a website's reachability by resolving its hostname via DNS.

    Args:
        url: The URL to validate.

    Returns:
        True if DNS resolution succeeds, False otherwise.
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
    Validates a website by sending an HTTP HEAD (or GET) request.

    Args:
        url: The URL to validate.
        timeout: Connection timeout in seconds.
        headers: Optional HTTP headers.
        **kwargs: Additional arguments passed to the client.

    Returns:
        True if the server responds with a 2xx-4xx status (excluding 405 which triggers a GET retry), False on connection error.
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
    Asynchronously validates a website by sending an HTTP HEAD (or GET) request.

    Args:
        url: The URL to validate.
        timeout: Connection timeout in seconds.
        headers: Optional HTTP headers.
        **kwargs: Additional arguments passed to the client.

    Returns:
        True if the server responds with a 2xx-4xx status, False on connection error.
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

@functools.lru_cache(maxsize=1200)
def validate_hostname(url: str) -> bool:
    """
    Validates that a hostname resolves to an IP address.

    Args:
        url: The URL or hostname.

    Returns:
        True if resolvable, False otherwise. Retries up to 5 times.
    """    
    hostname = urlparse(url).hostname if '://' in url else url
    for _attempts in range(5):
        with contextlib.suppress(Exception):
            socket.gethostbyname(hostname)
            return True
        time.sleep(1.5)
    return False


def validate_website_exists(
    url: str,
    timeout: Optional[int] = 15,
    headers: Optional[Dict[str, str]] = None,
    soft_validate: Optional[bool] = False,
) -> bool:
    """
    Comprehensive website validation checking ping first, then HTTP accessibility.

    Args:
        url: The URL to check.
        timeout: Timeout for requests.
        headers: Optional HTTP headers.
        soft_validate: If True, only checks ping/DNS, skips HTTP check if ping succeeds.

    Returns:
        True if the website appears to exist and be reachable.
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
    Async version of comprehensive website validation.

    Args:
        url: The URL to check.
        timeout: Timeout for requests.
        headers: Optional HTTP headers.
        soft_validate: If True, only checks ping/DNS, skips HTTP check if ping succeeds.

    Returns:
        True if the website appears to exist and be reachable.
    """
    url = normalize_url(url)
    hn_valid = validate_website_with_ping(url)
    if soft_validate or not hn_valid: return hn_valid
    return await avalidate_website_with_httpx(url, headers = headers, timeout = timeout)


"""
Resolvers
"""


@functools.lru_cache()
def resolve_domain(url: str, attempts: Optional[int] = None) -> str:
    """
    Resolves the final root URL of a website after following redirects.

    Args:
        url: The starting URL.
        attempts: Recursion counter for retries (internal use).

    Returns:
        The final resolved URL, or the original if resolution fails.
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
        return resolve_domain(new_url, attempts = attempts)
    


@async_lru.alru_cache(maxsize=1200)
async def aresolve_domain(url: str, attempts: Optional[int] = None) -> str:
    """
    Asynchronously resolves the final root URL of a website after following redirects.

    Args:
        url: The starting URL.
        attempts: Recursion counter for retries (internal use).

    Returns:
        The final resolved URL, or the original if resolution fails.
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
        return await aresolve_domain(new_url, attempts = attempts)

def determine_invalid_domains(
    urls: List[str],
    timeout: Optional[int] = 4,
) -> List[str]:
    """
    Filters a list of URLs and returns those that are unreachable.

    Args:
        urls: List of URLs to check.
        timeout: Timeout for each check.

    Returns:
        List of invalid/unreachable URLs.
    """
    if not urls: return []
    return [
        url
        for url in urls
        if not validate_website_with_ping(url, timeout=timeout)
    ]


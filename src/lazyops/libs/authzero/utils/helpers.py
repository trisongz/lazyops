from __future__ import annotations

"""
Hash Utilities
"""

import uuid
import hashlib
import base64
# from pydantic import ValidationError
# from lazyops.libs import lazyload
from lazyops.libs.pooler import ThreadPooler
# from lazyops.utils.helpers import lazy_import
from lazyops.imports._pycryptodome import resolve_pycryptodome
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Any, Optional, List, Dict

# if lazyload.TYPE_CHECKING:
#     import xxhash
#     import jose
#     # from Cryptodome.Cipher import AES
#     from fastapi import Request
#     # from fastapi.datastructures import Headers
#     # from jose import jwt, JWTError
#     from ..configs import AuthZeroSettings

# else:
#     xxhash = lazyload.LazyLoad("xxhash")
#     # jose = lazyload.LazyLoad('jose')
#     # jwt = jose.jwt
#     # JWTError = jose.JWTError
#     jwt = lazy_import('jose.jwt', is_module=True, allow_module=True)
#     JWTError = lazy_import('jose.exceptions.JWTError')
    # AES = lazy_import('Cryptodome.Cipher.AES', is_module=True, allow_module=True)
    # AES = lazyload.LazyLoad("Cryptodome.Cipher.AES", package = 'pycryptodomex')

    # jwt = lazyload.LazyLoad('jose.jwt')
    # JWTError = lazyload.LazyLoad('jose.exceptions.JWTError')

def create_uuid() -> str:
    """
    Returns a UUID
    """
    return str(uuid.uuid4())

def get_hashed_key(key: Any) -> str:
    """
    Returns a Hashed Key
    """
    return hashlib.sha256(str(key).encode()).hexdigest()
    # return xxhash.xxh128_hexdigest(str(key).encode())

def resize_key(key: str, length: int = 16) -> str:
    """
    Resizes the Key
    """
    return key.rjust((len(key) // length + 1) * length)

def encrypt_key(key: str, secret_key: str, access_key: str) -> str:
    """
    Encrypts the Key
    """
    resolve_pycryptodome(True)
    from Cryptodome.Cipher import AES

    cipher = AES.new(secret_key.encode(), AES.MODE_CBC, access_key.encode())
    string = cipher.encrypt(resize_key(key).encode())
    string = "".join("{:02x}".format(c) for c in string)
    return string

def decrypt_key(key: str, secret_key: str, access_key: str) -> str:
    """
    Decrypts the Key
    """
    resolve_pycryptodome(True)
    from Cryptodome.Cipher import AES

    cipher = AES.new(secret_key.encode(), AES.MODE_CBC, access_key.encode())
    string = cipher.decrypt(bytes.fromhex(key)).decode()
    return string.lstrip()

async def aencrypt_key(key: str, secret_key: str, access_key: str) -> str:
    """
    Encrypts the Key
    """
    return await ThreadPooler.run_async(
        encrypt_key,
        key,
        secret_key,
        access_key,
    )

async def adecrypt_key(key: str, secret_key: str, access_key: str) -> str:
    """
    Decrypts the Key
    """
    return await ThreadPooler.run_async(
        decrypt_key,
        key,
        secret_key,
        access_key,
    )

def parse_scopes(
    scope: Optional[str] = None,
    scopes: Optional[List[str]] = None,
) -> Optional[List[str]]:
    """
    Parses the Scopes
    """
    if scopes is None: scopes = []
    if scope is not None: 
        if " " in scope: scopes.extend(scope.split(' '))
        else: scopes.append(scope)
    return scopes or None

def normalize_audience_name(name: str) -> str:
    """
    Normalizes the audience name to transform the url

    >>> normalize_audience_name('https://domain.us.auth0.com/userinfo')
    'domain-us-auth0-com-userinfo'
    """
    return name.replace('https://', '').replace('http://', '').replace('/', '-').replace('.', '-').lower()

def create_code_challenge(secret_key: str) -> str:
    """
    Creates a code challenge
    """
    return base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest()).decode().rstrip('=')

def encode_params_to_url(params: Dict[str, Any], url: str) -> str:
    """
    Encodes the params to a url
    """
    url_parts = list(urlparse(url))
    query = dict(parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urlencode(query)
    return urlunparse(url_parts)

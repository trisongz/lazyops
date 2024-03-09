from __future__ import annotations

"""
Hash Utilities
"""

import uuid
from pydantic import ValidationError
from lazyops.libs import lazyload
from lazyops.libs.pooler import ThreadPooler
from typing import Any, Optional, List

if lazyload.TYPE_CHECKING:
    import xxhash
    from Cryptodome.Cipher import AES
    from fastapi import Request
    from fastapi.datastructures import Headers
    from jose import jwt, JWTError
    from ..configs import AuthZeroSettings

else:
    xxhash = lazyload.LazyLoad("xxhash")
    AES = lazyload.LazyLoad("Cryptodome.Cipher.AES", package = 'pycryptodomex')
    jose = lazyload.LazyLoad('jose')
    jwt = lazyload.LazyLoad('jose.jwt')
    JWTError = lazyload.LazyLoad('jose.exceptions.JWTError')

def create_uuid() -> str:
    """
    Returns a UUID
    """
    return str(uuid.uuid4())

def get_hashed_key(key: Any) -> str:
    """
    Returns a Hashed Key
    """
    return xxhash.xxh128_hexdigest(str(key).encode())

def resize_key(key: str, length: int = 16) -> str:
    """
    Resizes the Key
    """
    return key.rjust((len(key) // length + 1) * length)

def encrypt_key(key: str, secret_key: str, access_key: str) -> str:
    """
    Encrypts the Key
    """
    cipher = AES.new(secret_key.encode(), AES.MODE_CBC, access_key.encode())
    string = cipher.encrypt(resize_key(key).encode())
    string = "".join("{:02x}".format(c) for c in string)
    return string

def decrypt_key(key: str, secret_key: str, access_key: str) -> str:
    """
    Decrypts the Key
    """
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
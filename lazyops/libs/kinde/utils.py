from __future__ import annotations

"""
Hash Utilities
"""

import uuid
import hashlib
import base64
import string
from pathlib import Path
from lazyops.libs.pooler import ThreadPooler
from lazyops.imports._pycryptodome import resolve_pycryptodome
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Any, Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from kvdb import PersistentDict
    from lazyops.libs.kinde.config import KindeSettings


ALPHA_NUMERIC = string.ascii_letters + string.digits


_kinde_settings: Optional['KindeSettings'] = None
_kinde_pdicts: Dict[str, 'PersistentDict'] = {}
_kinde_pdict_aliases: Dict[str, str] = {}

def get_kinde_settings() -> 'KindeSettings':
    """
    Returns the Kinde Settings
    """
    global _kinde_settings
    if _kinde_settings is None:
        from lazyops.libs.kinde.config import KindeSettings
        _kinde_settings = KindeSettings()
    return _kinde_settings


def get_kinde_pdict(
    base_key: str,
    serializer: Optional[str] = 'json',
    hset_disabled: Optional[bool] = False,
    expiration: Optional[int] = None,
    data_dir: Optional[Path] = None,
    allow_local_fallback: bool = True,
    aliases: Optional[List[str]] = None,
    **kwargs,
) -> 'PersistentDict':
    """
    Returns the Kinde Persistent Dict
    """
    global _kinde_pdicts, _kinde_pdict_aliases
    if base_key not in _kinde_pdicts and base_key not in _kinde_pdict_aliases:
        sess = None
        if data_dir is None:
            from .base import lib_path
            data_dir = lib_path.joinpath('data')

        try:
            from kvdb import KVDBClient
            from lazyops.utils.logs import logger
            sess = KVDBClient.get_session(name = 'kinde.global')
            from lazyops.utils.helpers import fail_after
            try:
                with fail_after(5):
                    sess.ping()
            except Exception as e:
                if not allow_local_fallback: raise ValueError(f'KVDB Sesssion is not available and local fallback is not allowed: {e}') from e
                logger.warning(f'KVDB Sesssion is not available and local fallback is not allowed: {e}')
                sess = None
            
        except ImportError as e:
            if not allow_local_fallback: raise ImportError('Kinde Persistent Dict is not available and local fallback is not allowed') from e
            
        
        if sess is not None:
            _kinde_pdicts[base_key] = sess.create_persistence(
                base_key = base_key,
                serializer = serializer,
                hset_disabled = hset_disabled,
                expiration = expiration,
                **kwargs,
            )
        else:
            from lazyops.libs.persistence import PersistentDict
            _kinde_pdicts[base_key] = PersistentDict(
                base_key = base_key,
                serializer = serializer,
                hset_disabled = hset_disabled,
                expiration = expiration,
                file_path = data_dir.joinpath(f'{base_key}.cache'),
                **kwargs,
            )
        
        if aliases:
            for alias in aliases:
                _kinde_pdict_aliases[alias] = base_key
        
    elif base_key in _kinde_pdict_aliases:
        base_key = _kinde_pdict_aliases[base_key]
    return _kinde_pdicts[base_key]
    


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


def create_random_string(length: int = 44) -> str:
    """
    Creates a random string
    """
    import secrets
    result = secrets.token_hex(length)
    for i in result:
        if i not in ALPHA_NUMERIC: result = result.replace(i, secrets.choice(ALPHA_NUMERIC))
    return result[:length]

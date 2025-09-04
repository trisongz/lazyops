from __future__ import annotations

"""
KeyGen Utilities
"""

import os
import sys
import hashlib
import xxhash
import string
import secrets
import base64
import typing as t
import uuid as _uuid
from enum import Enum
from lzl import load

if t.TYPE_CHECKING:
    import bcrypt
else:
    bcrypt = load.lazy_load("bcrypt")


ALPHA_NUMERIC = string.ascii_letters + string.digits

# Base Classes

class Base64:
    encoding: str = 'utf-8'

    @classmethod
    def encode(cls, text: str, encoding: str = 'utf-8', *args, **kwargs) -> str:
        return base64.b64encode(text.encode(encoding = encoding), *args, **kwargs).decode(encoding = encoding)

    @classmethod
    def decode(cls, data: t.Union[str, bytes], encoding: str = 'utf-8', *args, **kwargs) -> str:
        if isinstance(data, str): data = data.encode(encoding = encoding)
        return base64.b64decode(data, *args, **kwargs).decode(encoding = encoding)

    @classmethod
    def dumps(cls, data: str, encoding: str = 'utf-8', *args, **kwargs) -> str:
        return cls.encode(data, encoding = encoding, *args, **kwargs)
    
    @classmethod
    def loads(cls, data: t.Union[str, bytes], encoding: str = 'utf-8', *args, **kwargs) -> str:
        return cls.decode(data, encoding = encoding, *args, **kwargs)


class Generate:
    default_method: str = 'uuid4'

    @classmethod
    def uuid(cls, method: str = None, *args, **kwargs):
        method = method or cls.default_method
        t = getattr(_uuid, method, cls.default_method)
        return str(t(*args, **kwargs))

    @classmethod
    def uuid_passcode(cls, length: int = None, clean: bool = True, method: str = None, raw: bool = False):
        rez = cls.uuid(method=method)
        if raw: return rez
        if clean: rez = rez.replace('-', '').strip()
        if length: rez = rez[:length]
        return rez
    
    @classmethod
    def alphanumeric_passcode(cls, length: int = 16, alpha_only: bool = False):
        select = string.ascii_letters if alpha_only else ALPHA_NUMERIC
        return ''.join(secrets.choice(select) for _ in range(length))
    
    @classmethod
    def token(cls, length: int = 32, safe: bool = False, clean: bool = True):
        rez = secrets.token_hex(length) if safe else secrets.token_urlsafe(length)
        if clean:
            for i in rez: 
                if i not in ALPHA_NUMERIC: rez.replace(i, secrets.choice(ALPHA_NUMERIC))
        return rez
    
    @classmethod
    def openssl_random_key(cls, length: int = 64, base: bool = True):
        # openssl rand 64 | base64
        key = secrets.token_hex(length)
        if base: key = Base64.encode(key)
        return key
    
    @classmethod
    def keypair(cls, key_length: int = 16, secret_length: int = 36) -> t.Dict[str, str]:
        return {
            'key': cls.alphanumeric_passcode(key_length),
            'secret': cls.alphanumeric_passcode(secret_length) 
        }


def generate_htpasswd_key(
    secret: str,
    salt: t.Optional[str] = None,
    rounds: int = 10,
    repeat: int = 1,
) -> t.Generator[str, None, None]:
    """
    Generate a bcrypt hashed password for use in htpasswd files.
    """
    for _ in range(repeat):
        if salt:
            hashed = bcrypt.hashpw(secret.encode(), salt.encode())
        else:
            hashed = bcrypt.hashpw(secret.encode(), bcrypt.gensalt(rounds = rounds))
        yield hashed.decode()

def validate_htpasswd_key(
    secret: str,
    hashed: str,
) -> bool:
    """
    Validate a bcrypt hashed password against a plain text password.
    """
    return bcrypt.checkpw(secret.encode(), hashed.encode())
    
from __future__ import annotations

"""Key generation helpers used for secrets, tokens, and passcodes."""

import os
import sys
import hashlib
import string
import secrets
import base64
import typing as t
import uuid as _uuid
from lzl import load

if t.TYPE_CHECKING:
    import bcrypt
else:
    bcrypt = load.lazy_load("bcrypt")


ALPHA_NUMERIC = string.ascii_letters + string.digits

__all__ = [
    'ALPHA_NUMERIC',
    'Base64',
    'Generate',
    'generate_htpasswd_key',
    'validate_htpasswd_key',
]

class Base64:
    """Convenience wrapper for base64 encoding/decoding strings."""

    encoding: str = 'utf-8'

    @classmethod
    def encode(cls, text: str, encoding: str = 'utf-8', *args: t.Any, **kwargs: t.Any) -> str:
        """Encode ``text`` using ``base64.b64encode``."""

        return base64.b64encode(text.encode(encoding=encoding), *args, **kwargs).decode(encoding=encoding)

    @classmethod
    def decode(
        cls,
        data: t.Union[str, bytes],
        encoding: str = 'utf-8',
        *args: t.Any,
        **kwargs: t.Any,
    ) -> str:
        """Decode base64 data back into a UTF-8 string."""

        if isinstance(data, str):
            data = data.encode(encoding=encoding)
        return base64.b64decode(data, *args, **kwargs).decode(encoding=encoding)

    @classmethod
    def dumps(cls, data: str, encoding: str = 'utf-8', *args: t.Any, **kwargs: t.Any) -> str:
        """Alias for :meth:`encode` to mirror JSON-like APIs."""

        return cls.encode(data, encoding=encoding, *args, **kwargs)

    @classmethod
    def loads(
        cls,
        data: t.Union[str, bytes],
        encoding: str = 'utf-8',
        *args: t.Any,
        **kwargs: t.Any,
    ) -> str:
        """Alias for :meth:`decode` to mirror JSON-like APIs."""

        return cls.decode(data, encoding=encoding, *args, **kwargs)


class Generate:
    """Helpers for creating pseudo-random identifiers and secrets."""

    default_method: str = 'uuid4'

    @classmethod
    def uuid(cls, method: t.Optional[str] = None, *args: t.Any, **kwargs: t.Any) -> str:
        """Return a UUID string using ``method`` (falls back to ``uuid4``)."""

        method_name = method or cls.default_method
        generator = getattr(_uuid, method_name, getattr(_uuid, cls.default_method))
        return str(generator(*args, **kwargs))

    @classmethod
    def uuid_passcode(
        cls,
        length: t.Optional[int] = None,
        clean: bool = True,
        method: t.Optional[str] = None,
        raw: bool = False,
    ) -> str:
        """Return a UUID-derived passcode with optional cleanup/truncation."""

        value = cls.uuid(method=method)
        if raw:
            return value
        if clean:
            value = value.replace('-', '').strip()
        if length:
            value = value[:length]
        return value

    @classmethod
    def alphanumeric_passcode(cls, length: int = 16, alpha_only: bool = False) -> str:
        """Return a random ASCII alphanumeric string of ``length`` characters."""

        select = string.ascii_letters if alpha_only else ALPHA_NUMERIC
        return ''.join(secrets.choice(select) for _ in range(length))

    @classmethod
    def token(cls, length: int = 32, safe: bool = False, clean: bool = True) -> str:
        """Generate URL-safe or hex tokens suitable for API keys."""

        value = secrets.token_hex(length) if safe else secrets.token_urlsafe(length)
        if clean:
            for char in value:
                if char not in ALPHA_NUMERIC:
                    value = value.replace(char, secrets.choice(ALPHA_NUMERIC))
        return value

    @classmethod
    def openssl_random_key(cls, length: int = 64, base: bool = True) -> str:
        """Mimic ``openssl rand`` with optional base64 encoding."""

        key = secrets.token_hex(length)
        if base:
            key = Base64.encode(key)
        return key

    @classmethod
    def keypair(cls, key_length: int = 16, secret_length: int = 36) -> t.Dict[str, str]:
        """Return a random key/secret pair using ``alphanumeric_passcode``."""

        return {
            'key': cls.alphanumeric_passcode(key_length),
            'secret': cls.alphanumeric_passcode(secret_length),
        }


def generate_htpasswd_key(
    secret: str,
    salt: t.Optional[str] = None,
    rounds: int = 10,
    repeat: int = 1,
) -> t.Generator[str, None, None]:
    """Yield bcrypt hashes suitable for ``htpasswd`` entries."""
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
    """Return ``True`` when ``secret`` matches the bcrypt ``hashed`` value."""
    return bcrypt.checkpw(secret.encode(), hashed.encode())
    

from __future__ import annotations


import hashlib
import pathlib
import typing as t
from enum import Enum
from typer import Typer, echo, Option, Argument, Exit
from lzo.utils.keygen import Base64, Generate, generate_htpasswd_key, validate_htpasswd_key

# Keygen / Encryption / Secrets Helper Functions

cmd = Typer(no_args_is_help=True)


class SecretMethod(str, Enum):
    secret = 'secret'
    uuid = 'uuid'
    keypair = 'keypair'
    token = 'token'
    ssl = 'ssl'


@cmd.command('secret', help = "Create an alphanmeric secret")
def create_secret_key(
    length: int = Argument(32, help = "Length of Secret Key"),
    repeat: int = Option(1, '-r', '-n', '--repeat', help = "Number of Secret Keys to Generate"),
    alpha_only: bool = Option(False, help = "Use only Alpha Characters"),
    hash: t.Optional[str] = Option(None, help = "Hash the Secret Key. Ex: sha256"),
    lower: bool = Option(False, help = "Lowercase the Secret Key"),
    prefix: t.Optional[str] = Option(None, '-p', help = "Prefix for the Secret Key"),
    from_string: t.Optional[str] = Option(None, '-s', '--string', help = "Generate from a length string"),
    from_file: t.Optional[pathlib.Path] = Option(None, '-f', '--file', help = "Generate and replace secrets within a file"),
    file_key: t.Optional[str] = Option('<key>', '-k', '--key', help = "Key to replace in the file"),
):
    """
    Generate a random alphanumeric secret key.

    >>> lzo kg secret
    """
    if from_string: length = len(from_string)
    existing = None
    if from_file:
        existing = from_file.read_text()
        if file_key not in existing:
            raise ValueError(f"Key '{file_key}' not found in file '{from_file}'")
        # Find the number of times the key appears in the file
        repeat = existing.count(file_key)
    for _ in range(repeat):
        value = Generate.alphanumeric_passcode(length, alpha_only)
        if lower: value = value.lower()
        if prefix: value = f'{prefix}{value}'
        echo(value)
        if existing and not hash: existing = existing.replace(file_key, value, 1)
        if hash:
            hashed_value = getattr(hashlib, hash)(value.encode()).hexdigest()
            if lower: hashed_value = hashed_value.lower()
            echo(hashed_value)
            if existing: existing = existing.replace(file_key, hashed_value, 1)
    if from_file: 
        from_file.write_text(existing)
        echo(f"Replaced '{file_key}' x {repeat}")

@cmd.command('uuid', help = "Generate UUID Key")
def create_uuid_key(
    length: int = Argument(None, help = "Length of UUID Key"),
    clean: bool = Option(True, help = "Strip '-' from UUID"),
    repeat: int = Option(1, help = "Number of Secret Keys to Generate"),
    raw: bool = Option(False, help = "Return Raw UUID Key"),
):
    """
    Generate a UUID key.

    >>> lzo kg uuid
    """
    for _ in range(repeat):
        value = Generate.uuid_passcode(length = length, clean = clean, raw = raw)
        echo(value)


@cmd.command('htpass', help = "Generate htpasswd Key using bcrypt")
def generate_htpasswd(
    secret: str = Argument(..., help = "Secret Key to Hash"),
    salt: t.Optional[str] = Option(None,  "-s", "--salt", help = "Salt for the Hash"),
    rounds: int = Option(10, "-r", "--rounds", help = "Number of Rounds for the Hash"),
    repeat: int = Option(1, "-n", "--num",  help = "Number of Secret Keys to Generate"),
):
    """
    Generate a bcrypt hashed password for use in htpasswd files.

    >>> lzo kg htpass mysecret
    """
    for hashed in generate_htpasswd_key(secret, salt=salt, rounds=rounds, repeat=repeat):
        echo(hashed)



@cmd.command('htpass-validate', help = "Validate a bcrypt hashed password")
def validate_htpasswd(
    secret: str = Argument(..., help = "Secret Key to Validate"),
    hashed: str = Argument(..., help = "Hashed Key to Validate Against"),
):
    """
    Validate a bcrypt hashed password against a plain text password.

    >>> lzo kg htpass-validate mysecret $2b$12$eImiTMZG4ELQ2Z8K1z3uOe
    """
    echo(validate_htpasswd_key(secret, hashed))


@cmd.command('keypair', help = "Create Key Pair")
def create_keypair(
    key_length: int = Argument(16, help = "Length of Key"),
    secret_length: int = Argument(32, help = "Length of Secret"),
    repeat: int = Option(1, help = "Number of Secret Keys to Generate"),
):
    """
    Create a Key Pair.

    >>> lzo kg keypair
    """
    for _ in range(repeat):
        value = Generate.keypair(key_length = key_length, secret_length = secret_length)
        echo(f'{value["key"]}:{value["secret"]}')


@cmd.command('token', help = "Create a Token")
def create_token(
    length: int = Argument(32, help = "Length of Token"),
    safe: bool = Option(False, help = "Use URL Safe Token"),
    clean: bool = Option(True, help = "Remove non-alphanumeric from Token"),
    repeat: bool = Option(1, help = "Number of Tokens to Generate"),
):
    """
    Create a Token.

    >>> lzo kg token
    """
    for _ in range(repeat):
        value = Generate.token(length = length, safe = safe, clean = clean)
        echo(value)


@cmd.command('ssl', help = "Create a Token using OpenSSL")
def create_ssl_token(
    length: int = Argument(64, help = "Length of Token"),
    base_encode: bool = Option(False, help = "Base64 Encode the Token"),
    repeat: int = Option(1, help = "Number of Secret Keys to Generate"),
):
    """
    Create a Token using OpenSSL.

    >>> lzo kg ssl
    """
    for _ in range(repeat):
        value = Generate.openssl_random_key(length = length, base = base_encode)
        echo(value)


@cmd.command('create', help = "Generate a Unique Key")
def create_key(
    method: SecretMethod = Option(SecretMethod.secret, help = "Method to generate Key"),
    length: int = Option(32, help = "Length of Key"),
    secret_length: int = Option(32, help = "[Optional] Length of Secret"),
    clean: bool = Option(True, help = "[Optional] Remove non-alphanumeric from Key"),
    safe: bool = Option(False, help = "[Optional] Use URL Safe Token"),
    base_encode: bool = Option(True, help = "[Optional] Base64 Encode the Token"),
    repeat: bool = Option(1, help = "[Optional] Number of Tokens to Generate"),
):
    """
    Generate a Unique Key.

    >>> lzo kg create secret
    """
    for _ in range(repeat):
        if method == SecretMethod.secret:
            value = Generate.alphanumeric_passcode(length = length)
        elif method == SecretMethod.uuid:
            value = Generate.uuid_passcode(length = length, clean = clean)
        elif method == SecretMethod.keypair:
            value = Generate.keypair(key_length = length, secret_length = secret_length)
        elif method == SecretMethod.token:
            value = Generate.token(length = length, clean = clean, safe = safe)
        elif method == SecretMethod.ssl:
            value = Generate.openssl_random_key(length = length, base = base_encode)
        if isinstance(value, dict):
            echo(f'{value["key"]}:{value["secret"]}')
        else:
            echo(value)

from __future__ import annotations

import os
import typing as t
from lzl.proxied import ProxyObject

if t.TYPE_CHECKING:
    from .config import KeycloakSettings
    from .manager import KeycloakManager
    from lzl.io.persistence import PersistentDict
    from kvdb import KVDBSession

_kc_settings: t.Optional['KeycloakSettings'] = None
_keycloak_client: t.Optional['KeycloakManager'] = None



def get_keycloak_settings() -> 'KeycloakSettings':
    """
    Get the Keycloak settings instance.
    If it does not exist, create a new instance.
    """
    global _kc_settings
    if _kc_settings is None:
        from lzl.api.keycloak.config import KeycloakSettings
        _kc_settings = KeycloakSettings()
    return _kc_settings

def get_keycloak_client() -> 'KeycloakManager':
    """
    Get the Keycloak client instance.
    If it does not exist, create a new instance.
    """
    global _keycloak_client
    if _keycloak_client is None:
        from lzl.api.keycloak.manager import KeycloakManager
        _keycloak_client = KeycloakManager()
    return _keycloak_client


def get_kvdb(*args, **kwargs) -> 'KVDBSession':
    """
    Get the KVDB session.
    """
    from kvdb import KVDBClient
    return KVDBClient.get_session(
        name = 'global',
        serializer = 'json',
    )


def get_persistence_kvdb(*args, **kwargs) -> 'KVDBSession':
    """
    Get the KVDB session.
    """
    from kvdb import KVDBClient
    return KVDBClient.get_session(
        name = 'persistence.global',
        serializer = None,
    )

def get_kv_pdict(*args, **kwargs) -> 'PersistentDict[str, t.Any]':
    """
    Get the KV persistence dictionary.
    """
    kdb = get_persistence_kvdb()
    settings = get_keycloak_settings()
    return kdb.create_persistence(
        'keycloak',
        serializer = 'json',
        base_key = f'keycloak.auth.{settings.instance_id}',
    )



keycloak_client: 'KeycloakManager' = ProxyObject(obj_getter = get_keycloak_client)
kc_settings: 'KeycloakSettings' = ProxyObject(obj_getter = get_keycloak_settings)
kv: 'KVDBSession' = ProxyObject(obj_getter = get_kvdb)
kv_pdict: 'PersistentDict[str, t.Any]' = ProxyObject(obj_getter = get_kv_pdict)
kv_available = bool(os.getenv('REDIS_URL'))
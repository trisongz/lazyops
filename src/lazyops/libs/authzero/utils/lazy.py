from __future__ import annotations

"""
Lazy Loading Utilities
"""

from lazyops.libs import lazyload
from lazyops.libs.pooler import ThreadPooler
from lazyops.utils.logs import logger
from lazyops.utils.lazy import lazy_import
from lazyops.utils.helpers import fail_after
from typing import Any, Callable, Dict, List, Optional, Union, Type

if lazyload.TYPE_CHECKING:
    import kvdb
    from lazyops.libs.authzero.configs import AuthZeroSettings
    from kvdb import KVDBSession, PersistentDict

    from ..types import AZResource, AZResourceSchema
    from ..flows import AZFlow, AZFlowSchema, AZManagementAPI

else:
    kvdb = lazyload.LazyLoad("kvdb")
    # KVDBClient = lazyload.LazyLoad("kvdb.KVDBClient", package = 'kvdb')


_az_sessions_configured: Optional[bool] = False
_az_kdbs: Dict[str, 'KVDBSession'] = {}
_az_pdicts: Dict[str, 'PersistentDict'] = {}
_az_pdict_aliases: Dict[str, str] = {}
_az_settings: Optional['AuthZeroSettings'] = None
_az_mtg_api: Optional['AZManagementAPI'] = None

def get_az_kdb(
    name: Optional[str] = None,
    serializer: Optional[str] = 'json',
    **kwargs,
) -> 'KVDBSession':
    """
    Returns the KVDB Session
    """
    global _az_kdbs
    if name is None: name = 'global'
    if name not in _az_kdbs:
        _az_kdbs[name] = kvdb.KVDBClient.get_session(
            name = name,
            serializer = serializer,
            **kwargs,
        )
    return _az_kdbs[name]

def get_az_pdict(
    base_key: str,
    expiration: Optional[int] = None,
    aliases: Optional[List[str]] = None,
    hset_disabled: Optional[bool] = False,
    **kwargs,
) -> 'PersistentDict':
    """
    Lazily initializes the persistent dict
    """
    global _az_pdicts, _az_pdict_aliases
    if base_key not in _az_pdicts and base_key not in _az_pdict_aliases:
        s = get_az_settings()
        sess = get_az_kdb(
            'persistence',
            serializer = None,
        )
        if s.local_persistence_fallback:
            try:
                with fail_after(5):
                    sess.ping()
            except Exception as e:
                logger.warning(f'Failed to connect to KVDB persistence backend, falling back to local: {e}')
        if sess is not None:
            _az_pdicts[base_key] = sess.create_persistence(
                base_key = base_key,
                expiration = expiration,
                hset_disabled = hset_disabled,
                **kwargs,
            )
        else:
            from lazyops.libs.persistence import PersistentDict
            _az_pdicts[base_key] = PersistentDict(
                base_key = base_key,
                expiration = expiration,
                hset_disabled = hset_disabled,
                file_path = s.data_dir.joinpath(f'{s.app_name}.cache'),
                **kwargs,
            )

        if aliases:
            for alias in aliases:
                _az_pdict_aliases[alias] = base_key
    elif base_key in _az_pdict_aliases:
        base_key = _az_pdict_aliases[base_key]
    return _az_pdicts[base_key]


def get_az_settings() -> 'AuthZeroSettings':
    """
    Returns the AuthZero Settings
    """
    global _az_settings
    if _az_settings is None:
        from ..configs import AuthZeroSettings
        _az_settings = AuthZeroSettings()
    return _az_settings


_az_flow_schemas: Dict[str, 'AZFlowSchema'] = {
    'api_key': 'lazyops.libs.authzero.flows.api_keys.APIKeyDataFlow',
    'api_client_credentials': 'lazyops.libs.authzero.flows.tokens.APIClientCredentialsFlow',
    'client_credentials': 'lazyops.libs.authzero.flows.tokens.ClientCredentialsFlow',
    'user_data': 'lazyops.libs.authzero.flows.user_data.UserDataFlow',
    'user_session': 'lazyops.libs.authzero.flows.user_session.UserSessionFlow',
    
}

def get_az_flow_schema(
    name: str
) -> 'AZFlowSchema':
    """
    Returns the AZFlowSchema
    """
    global _az_flow_schemas
    if name not in _az_flow_schemas:
        raise ValueError(f"Invalid AuthZero Flow: {name}, must be one of {list(_az_flow_schemas.keys())}")
    if isinstance(_az_flow_schemas[name], str):
        _az_flow_schemas[name] = lazy_import(_az_flow_schemas[name])
    return _az_flow_schemas[name]

def get_az_flow(
    name: str, 
    *args, 
    **kwargs
) -> 'AZFlow':
    """
    Returns the AZFlow
    """
    return get_az_flow_schema(name)(*args, **kwargs)


_az_resource_schemas: Dict[str, 'AZResourceSchema'] = {
    'current_user': 'lazyops.libs.authzero.types.current_user.CurrentUser',
    'user_role': 'lazyops.libs.authzero.types.user_roles.UserRole',
    'user_data': 'lazyops.libs.authzero.types.user_data.AZUserData',
    'auth_object': 'lazyops.libs.authzero.types.auth.AuthObject',
    'user_jwt_claims': 'lazyops.libs.authzero.types.claims.UserJWTClaims',
    'api_key_jwt_claims': 'lazyops.libs.authzero.types.claims.APIKeyJWTClaims',
    'auth_zero_token_auth': 'lazyops.libs.authzero.types.auth.AuthZeroTokenAuth',
    'user_session': 'lazyops.libs.authzero.types.user_session.UserSession',
}

def get_az_resource_schema(
    name: str,
) -> 'AZResourceSchema':
    """
    Returns the AZResource Schema
    """
    global _az_resource_schemas
    if name not in _az_resource_schemas:
        raise ValueError(f"Invalid AuthZero Resource: {name}, must be one of {list(_az_resource_schemas.keys())}")
    if isinstance(_az_resource_schemas[name], str):
        _az_resource_schemas[name] = lazy_import(_az_resource_schemas[name])
    return _az_resource_schemas[name]


def get_az_resource(
    name: str,
    *args, 
    **kwargs
) -> 'AZResource':
    """
    Returns the AZResource
    """
    schema = get_az_resource_schema(name)
    return schema(*args, **kwargs)


def get_az_mtg_api() -> 'AZManagementAPI':
    """
    Returns the AZ Management API
    """
    global _az_mtg_api
    if _az_mtg_api is None:
        from ..flows.admin import AZManagementClient
        _az_mtg_api = AZManagementClient
    return _az_mtg_api
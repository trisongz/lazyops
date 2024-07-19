from __future__ import annotations

"""
Hatchet Utilities
"""

import os
import grpc
import pathlib
from hatchet_sdk.connection import new_conn
from hatchet_sdk.clients.admin import new_admin
from hatchet_sdk.clients.dispatcher import new_dispatcher
from hatchet_sdk.clients.events import new_event
from hatchet_sdk.clients.rest_client import RestApi
from hatchet_sdk.client import ClientImpl
from hatchet_sdk.loader import ClientConfig, ConfigLoader
from lazyops.libs.logging import logger
from kvdb.io.serializers import get_serializer
from typing import Any, Dict, Union, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from lazyops.libs.hatchet.config import HatchetSettings
    from lazyops.libs.hatchet.base import HatchetClient
    from lazyops.libs.hatchet.session import HatchetSession

    
lib_path = pathlib.Path(__file__).parent
json_serializer = get_serializer(
    'json',
    compression = None,
)

_hatchet_settings: Optional['HatchetSettings'] = None
_hatchet_client: Optional['HatchetClient'] = None
_hatchet_sessions: Dict[str, 'HatchetSession'] = {}

def get_hatchet_settings() -> 'HatchetSettings':
    """
    Retrieves the Hatchet settings
    """
    global _hatchet_settings
    if _hatchet_settings is None:
        from lazyops.libs.hatchet.config import HatchetSettings
        _hatchet_settings = HatchetSettings()
    return _hatchet_settings

def set_hatchet_settings(settings: 'HatchetSettings', override: bool = False):
    """
    Sets the global Hatchet Settings
    """
    global _hatchet_settings
    if _hatchet_settings is None or override:
        _hatchet_settings = settings

def get_hatchet_session(
    instance: str = 'default'
) -> Optional['HatchetSession']:
    """
    Retrieves the Hatchet Session
    """
    global _hatchet_sessions
    return _hatchet_sessions.get(instance)

def set_hatchet_session(
    session: 'HatchetSession',
):
    """
    Sets the global Hatchet Session
    """
    global _hatchet_sessions
    _hatchet_sessions[session.instance] = session



def get_hatchet_client() -> 'HatchetClient':
    """
    Retrieves the Hatchet Client
    """
    global _hatchet_client
    if _hatchet_client is None:
        from lazyops.libs.hatchet.base import HatchetClient
        _hatchet_client = HatchetClient()
    return _hatchet_client

def set_hatchet_client(client: 'HatchetClient'):
    """
    Sets the global Hatchet Client
    """
    global _hatchet_client
    _hatchet_client = client

def get_ulimits():
    import resource
    soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    return soft_limit


def set_ulimits(
    max_connections: int = 500,
    verbose: bool = False,
):
    """
    Sets the system ulimits
    to allow for the maximum number of open connections

    - if the current ulimit > max_connections, then it is ignored
    - if it is less, then we set it.
    """
    import resource

    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft_limit > max_connections: return
    if hard_limit < max_connections and verbose:
        logger.warning(f"The current hard limit ({hard_limit}) is less than max_connections ({max_connections}).")
    new_hard_limit = max(hard_limit, max_connections)
    if verbose: logger.info(f"Setting new ulimits to ({soft_limit}, {hard_limit}) -> ({max_connections}, {new_hard_limit})")
    resource.setrlimit(resource.RLIMIT_NOFILE, (max_connections + 10, new_hard_limit))
    new_soft, new_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if verbose: logger.info(f"New Limits: ({new_soft}, {new_hard})")


_patched_json = None

def patch_json():
    """
    Patches the json module to use our custom encoder and decoder
    """
    global _patched_json
    if _patched_json is not None: return
    import json
    json.loads = json_serializer.loads
    json.dumps = json_serializer.dumps
    _patched_json = True


def new_client(
    defaults: Union[ClientConfig, Dict[str, Any]] = None, 
    *opts_functions
) -> ClientImpl:
    """
    Create a new Hatchet client instance
    """
    patch_json()
    settings = get_hatchet_settings()
    defaults = defaults or {}
    settings.autologger.info(f'Initializing Hatchet Client: v{settings.version}')
    if not settings.in_k8s: set_ulimits(max_connections = 1024)
    if settings.in_k8s: os.environ['HATCHET_CLIENT_TLS_STRATEGY'] = 'none'
    config: ClientConfig = ConfigLoader(
        settings.config_lib_path or '.'
        # lib_path.joinpath('configs', 'defaults').as_posix()
    ).load_client_config(defaults)

    # Here we do some overrides
    settings.configure_client_endpoints(config)
    config.namespace = f'{settings.app_env.short_name}.'

    if not settings.temp_data.has_logged('hatchet_init'):
        logger.info(f'{config.server_url} - {config.host_port}', prefix = 'Hatchet Config', colored = True)
    
    for opt_function in opts_functions:
        opt_function(config)

    if config.tls_config is None: raise ValueError("TLS config is required")
    if config.host_port is None: raise ValueError("Host and port are required")

    conn: grpc.Channel = new_conn(config)

    # Instantiate client implementations
    event_client = new_event(conn, config)
    admin_client = new_admin(config)
    dispatcher_client = new_dispatcher(config)
    rest_client = RestApi(config.server_url, config.token, config.tenant_id)
    workflow_listener_client = None
    return ClientImpl(
        event_client,
        admin_client,
        dispatcher_client,
        workflow_listener_client,
        rest_client,
        config,
    )



def new_session(
    defaults: Union[ClientConfig, Dict[str, Any]] = None, 
    settings: Optional['HatchetSettings'] = None,
    instance: str = 'default',
    *opts_functions,
    namespace: Optional[str] = None,
    api_endpoint: Optional[str] = None,
    grpc_endpoint: Optional[str] = None,
    # include_instance_name: Optional[bool] = None,
    **kwargs,
) -> ClientImpl:
    """
    Create a new Hatchet Session instance
    """
    patch_json()
    if settings is None: settings = get_hatchet_settings()
    defaults = defaults or ClientConfig()
    settings.autologger.info(f'Initializing Hatchet Session: v{settings.version}', prefix = instance, colored = True)
    if not settings.in_k8s: set_ulimits(max_connections = 1024)
    if settings.in_k8s: os.environ['HATCHET_CLIENT_TLS_STRATEGY'] = 'none'
    
    config: ClientConfig = ConfigLoader(settings.config_lib_path or '.').load_client_config(defaults)

    # Here we do some overrides
    settings.configure_session_endpoints(
        config,
        instance = instance,
        api_endpoint = api_endpoint,
        grpc_endpoint = grpc_endpoint,
        **kwargs,
    )
    if not namespace and os.getenv(f'HATCHET_NAMESPACE_{instance.upper()}'):
        namespace = os.getenv(f'HATCHET_NAMESPACE_{instance.upper()}')
    
    config.namespace = namespace or f'{settings.app_env.short_name}.'
    if not settings.temp_data.has_logged(f'hatchet_init_{instance}'):
        logger.info(f'{config.server_url} - {config.host_port} (Namespace: {config.namespace})', prefix = f'Hatchet Config: {instance}', colored = True)
    
    for opt_function in opts_functions:
        opt_function(config)

    if config.tls_config is None: raise ValueError("TLS config is required")
    if config.host_port is None: raise ValueError("Host and port are required")
    # config.logger = settings.logger

    conn: grpc.Channel = new_conn(config)
    # Instantiate client implementations
    event_client = new_event(conn, config)
    admin_client = new_admin(config)
    dispatcher_client = new_dispatcher(config)
    rest_client = RestApi(config.server_url, config.token, config.tenant_id)
    workflow_listener_client = None
    return ClientImpl(
        event_client,
        admin_client,
        dispatcher_client,
        workflow_listener_client,
        rest_client,
        config,
    )



from __future__ import annotations

"""
Hatchet Utilities
"""

import os
import grpc
import pathlib
from hatchet_sdk.connection import new_conn
from hatchet_sdk.clients.dispatcher import new_dispatcher
from hatchet_sdk.clients.events import new_event
from hatchet_sdk.clients.listener import new_listener
from hatchet_sdk.clients.rest_client import RestApi
from hatchet_sdk.client import ClientImpl
from hatchet_sdk.loader import ClientConfig, ConfigLoader
from lazyops.libs.logging import logger
from kvdb.io.serializers import get_serializer
from lazyops.libs.abcs.utils.http import validate_website_with_socket
from typing import Any, Dict, Union, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from lazyops.libs.hatchet.config import HatchetSettings

    
lib_path = pathlib.Path(__file__).parent
json_serializer = get_serializer(
    'json',
    compression = None,
)

_hatchet_settings: Optional['HatchetSettings'] = None


def get_hatchet_settings() -> 'HatchetSettings':
    """
    Retrieves the Hatchet settings
    """
    global _hatchet_settings
    if _hatchet_settings is None:
        from lazyops.libs.hatchet.config import HatchetSettings
        _hatchet_settings = HatchetSettings()
    return _hatchet_settings


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


def configure_client_endpoints(
    config: ClientConfig,
    endpoints: Optional[Dict[str, Dict[str, str]]] = None,
) -> None:
    """
    Configure the client endpoints based on the environment variables
    """
    settings = get_hatchet_settings()
    endpoints = endpoints or settings.endpoints

    if settings.in_k8s and endpoints and endpoints.get('api', {}).get('cluster') and validate_website_with_socket(
        endpoints['api']['cluster'],
    ):
        config.server_url = endpoints['api']['cluster']
        config.host_port = endpoints['grpc']['cluster']
    return config

def new_client(
    defaults: Union[ClientConfig, Dict[str, Any]] = None, 
    endpoints: Optional[Dict[str, Dict[str, str]]] = None,
    *opts_functions
) -> ClientImpl:
    """
    Create a new Hatchet client instance
    """
    settings = get_hatchet_settings()
    defaults = defaults or {}
    if not settings.temp_data.has_logged('hatchet_client'):
        logger.info('Initializing Hatchet Client')
        set_ulimits(max_connections = 1024)
    if settings.in_k8s:
        os.environ['HATCHET_CLIENT_TLS_STRATEGY'] = 'none'

    config: ClientConfig = ConfigLoader(
        lib_path.joinpath('configs', 'defaults').as_posix()
    ).load_client_config(defaults)

    # Here we do some overrides
    configure_client_endpoints(config)
    config.namespace = f'{settings.app_env.short_name}.'

    if not settings.temp_data.has_logged('hatchet_init'):
        logger.info(f'{config.server_url} - {config.host_port}', prefix = 'Hatchet Config', colored = True)
    
    for opt_function in opts_functions:
        opt_function(config)

    if config.tls_config is None:
        raise ValueError("TLS config is required")

    if config.host_port is None:
        raise ValueError("Host and port are required")

    conn: grpc.Channel = new_conn(config)
    from .admin import new_admin

    # Instantiate client implementations
    event_client = new_event(conn, config)
    admin_client = new_admin(conn, config)
    dispatcher_client = new_dispatcher(conn, config)
    listener_client = new_listener(conn, config)
    rest_client = RestApi(config.server_url, config.token, config.tenant_id)

    return ClientImpl(
        event_client,
        admin_client,
        dispatcher_client,
        listener_client,
        rest_client,
        config,
    )


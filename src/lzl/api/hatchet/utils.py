from __future__ import annotations

"""
Hatchet Utilities
"""

import os
import pathlib
from hatchet_sdk.client import ClientImpl
from hatchet_sdk.loader import ClientConfig, ConfigLoader
from lzl.logging import logger
from lzo.utils.system import get_ulimits, set_ulimits
from kvdb.io.serializers import get_serializer
from typing import Any, Dict, Union, Optional, TYPE_CHECKING
from .version import CURRENT_VERSION as VERSION

if TYPE_CHECKING:
    from lzl.api.hatchet.config import HatchetSettings
    from lzl.api.hatchet.client import HatchetClient
    from lzl.api.hatchet.session import HatchetSession

    
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
        from lzl.api.hatchet.config import HatchetSettings
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


def get_hatchet_client(**kwargs) -> 'HatchetClient':
    """
    Retrieves the Hatchet Client
    """
    global _hatchet_client
    if _hatchet_client is None:
        from lzl.api.hatchet.client import HatchetClient
        _hatchet_client = HatchetClient(**kwargs)
    return _hatchet_client

def set_hatchet_client(client: 'HatchetClient'):
    """
    Sets the global Hatchet Client
    """
    global _hatchet_client
    _hatchet_client = client

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
    settings.autologger.info(f'Initializing Hatchet Session: v{settings.version} (SDK Version: v{VERSION})', prefix = instance, colored = True)
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
    
    return ClientImpl.from_config(config)
    # if config.tls_config is None: raise ValueError("TLS config is required")
    # if config.host_port is None: raise ValueError("Host and port are required")
    # # config.logger = settings.logger

    # conn: grpc.Channel = new_conn(config)
    # # Instantiate client implementations
    # event_client = new_event(conn, config)
    # admin_client = new_admin(config)
    # dispatcher_client = new_dispatcher(config)
    # rest_client = RestApi(config.server_url, config.token, config.tenant_id)
    # workflow_listener_client = None
    # return ClientImpl(
    #     event_client,
    #     admin_client,
    #     dispatcher_client,
    #     workflow_listener_client,
    #     rest_client,
    #     config,
    # )



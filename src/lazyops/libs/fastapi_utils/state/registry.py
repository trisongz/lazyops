from __future__ import annotations

"""
Stateful Registry

- Migrated to `lazyops.libs.abcs.state.registry`
"""

from lazyops.libs.abcs.state.registry import (
    ClientT, ClientTypeT, 
    _registered_clients, _client_registry_mapping,
    update_client_registry_mapping, 
    get_global_client, 
    get_client, 
    register_client
)


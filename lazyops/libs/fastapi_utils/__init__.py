from __future__ import annotations

"""
FastAPI Utilities
"""

from .openapi import (
    OpenAPIStoplight,
    get_server_domain,
    patch_openapi_schema,
    create_openapi_schema_patch, 
    create_openapi_schema_by_role_function,
    UserRole,
    OpenAPIRoleSpec,
)

from .processes import (
    spawn_new_worker,
    stop_worker,
    run_until_complete,
    arun_until_complete,
    GlobalContext,
    GracefulKiller,
)

from .tasks import (
    register_server_task,
    start_bg_tasks,
)
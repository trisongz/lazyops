from .stoplight import OpenAPIStoplight
from .spec import (
    get_server_domain,
    patch_openapi_schema,
    create_openapi_schema_patch, 
    create_openapi_schema_by_role_function,
    OpenAPIRoleSpec,
    UserRole
)

"""
module_name = __package__.split('.')[0]

_openapi_spec_patches = {
    '/v1/services/create': {
        'source': 'Body_Create_v1_services_create',
        'schema': 'CreateService',
    },
}

_openapi_spec_exclude_schemas = [
    'BaseSchema',
    'BlockItem',
]

_included_paths = [
    '/v1/private/admin',
]


def description_patch(
    description: str,
    *args,
) -> str:

    description = description.split('page to authenticate.**\n\n', 1)[-1].strip()
    description = "## Private API Documentation\n" + description
    return description

role_specs = [
    OpenAPIRoleSpec(
        role = UserRole.ANON,
        excluded_tags = ['Private', 'Admin'],
        excluded_schemas = [
            'Private*',
        ],
    ),
    OpenAPIRoleSpec(
        role = UserRole.STAFF,
        included_paths = _included_paths,
        description_callable = description_patch,
    ),
    OpenAPIRoleSpec(
        role = UserRole.USER,
        excluded_tags = ['Admin'],
    ),
    OpenAPIRoleSpec(
        role = UserRole.SYSTEM,
        excluded_tags = ['Admin'],
    ),
    OpenAPIRoleSpec(
        role = UserRole.ADMIN,
        included_paths = _included_paths,
        description_callable = description_patch,
    ),
] 
patch_openapi_schema = create_openapi_schema_patch(
    module_name = module_name,
    schemas_patches = _openapi_spec_patches,
    excluded_schemas = _openapi_spec_exclude_schemas,
)
get_openapi_schema_by_role = create_openapi_schema_by_role_function(
    module_name = module_name,
    roles = role_specs,
    default_exclude_paths = _included_paths,
)


"""
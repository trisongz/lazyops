from __future__ import annotations

"""
Usage:



"""

import re
import json
import copy
import contextlib

from abc import ABC
from typing import Any, Dict, List, Optional, Union, Callable, Tuple, TYPE_CHECKING
from lazyops.utils import logger
from lazyops.libs.fastapi_utils.types.user_roles import UserRole

if TYPE_CHECKING:
    from fastapi import Request, FastAPI


KEY_START = '[x-repl-start]'
KEY_END = '[x-repl-end]'
KEY_SEP = '||'

def json_replace(
    schema: Dict[str, Any],
    key: str,
    value: Optional[str] = None,

    verbose: Optional[bool] = False,
    # Control Vars
    key_start: Optional[str] = KEY_START,
    key_end: Optional[str] = KEY_END,
    sep_char: Optional[str] = KEY_SEP,
) -> Dict[str, Any]:
    """
    Replace the json
    """
    plaintext = json.dumps(schema, ensure_ascii=False)
    if f'{key_start} {key}' not in plaintext:
        return schema
    while f'{key_start} {key}' in plaintext:
        src_value = value
        start = plaintext.index(f'{key_start} {key}')
        end = plaintext.index(f'{key_end}', start)
        segment = plaintext[start:end + len(key_end)].strip()
        # Default Value
        if not src_value and sep_char in segment:
            src_value = segment.split(sep_char, 1)[-1].rsplit(' ', 1)[0].strip()
        plaintext = plaintext.replace(segment, src_value)
        if verbose: logger.info(f"Replaced {segment} -> {src_value}", colored = True, prefix = "|g|OpenAPI|e|")
        if f'{key_start} {key}' not in plaintext:
            break
    schema = json.loads(plaintext)
    return schema


"""
Dynamic Patching of OpenAPI Specs

- route_schemas: Dict[str, Dict[str, str]]
- excluded_schemas: List[str]
"""

_openapi_schemas: Dict[str, Dict[str, Any]] = {}

def patch_openapi_schema(
    openapi_schema: Dict[str, Any], # OpenAPI Schema

    schemas_patches: Dict[str, Dict[str, str]], # Schemas to patch
    excluded_schemas: List[str], # Schemas to exclude

    overwrite: Optional[bool] = None, 
    verbose: Optional[bool] = True, 
    module_name: Optional[str] = None, # this will get injected

    # Patches
    replace_patches: Optional[List[Tuple[str, Union[Callable, Optional[str]]]]] = None,
    replace_key_start: Optional[str] = KEY_START,
    replace_key_end: Optional[str] = KEY_END,
    replace_sep_char: Optional[str] = KEY_SEP,
    **kwargs
) -> Dict[str, Any]:
    """
    Patch the openapi schema
    """
    global _openapi_schemas
    if module_name not in _openapi_schemas or overwrite:
        if verbose: logger.warning(f"[{module_name}] Patching OpenAPI Schema")
        for path, patch in schemas_patches.items():
            with contextlib.suppress(Exception):
                patch_source = openapi_schema['components']['schemas'].pop(patch['source'], None)
                if patch_source is None: continue

                patch_source['title'] = patch['schema']
                openapi_schema['components']['schemas'][patch['schema']] = patch_source

                # Handle Paths
                openapi_schema['paths'][path]['post']['requestBody']['content']['multipart/form-data']['schema']['$ref'] = f'#/components/schemas/{patch["schema"]}'
        
        if not excluded_schemas: excluded_schemas = []
        for exclude in excluded_schemas:
            _ = openapi_schema['components']['schemas'].pop(exclude, None)
        
        if replace_patches:
            for patch in replace_patches:
                key, value = patch
                if callable(value): value = value()
                openapi_schema = json_replace(
                    schema = openapi_schema,
                    key = key,
                    value = value,
                    verbose = verbose,
                    key_start = replace_key_start,
                    key_end = replace_key_end,
                    sep_char = replace_sep_char,
                )

        if 'schemas' in openapi_schema['components']:
            openapi_schema['components']['schemas'] = dict(sorted(openapi_schema['components']['schemas'].items()))
        _openapi_schemas[module_name] = openapi_schema
    
    return _openapi_schemas[module_name]

def create_openapi_schema_patch(
    module_name: str,
    schemas_patches: Dict[str, Dict[str, str]],
    excluded_schemas: List[str],

    replace_patches: Optional[List[Tuple[str, Union[Callable, Optional[str]]]]] = None,
    replace_key_start: Optional[str] = KEY_START,
    replace_key_end: Optional[str] = KEY_END,
    replace_sep_char: Optional[str] = KEY_SEP,

) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """
    Create an openapi schema patch
    """
    def patch_openapi_schema_wrapper(
        openapi_schema: Dict[str, Any],
        overwrite: Optional[bool] = None, 
        verbose: Optional[bool] = True, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Patch the openapi schema wrapper
        """
        return patch_openapi_schema(
            openapi_schema = openapi_schema,
            schemas_patches = schemas_patches,
            excluded_schemas = excluded_schemas,
            module_name = module_name,
            overwrite = overwrite,
            verbose = verbose,
            replace_patches = replace_patches,
            replace_key_start = replace_key_start,
            replace_key_end = replace_key_end,
            replace_sep_char = replace_sep_char,
        )
    return patch_openapi_schema_wrapper

def get_openapi_schema(module_name: str) -> Dict[str, Any]:
    """
    Get the openapi schema
    """
    global _openapi_schemas
    return _openapi_schemas[module_name]

_server_domains: Dict[str, str] = {}

def get_server_domain(
    request: Optional['Request'] = None,
    module_domains: Optional[List[str]] = None,
    module_name: Optional[str] = None, # this will get injected
    verbose: Optional[bool] = True,
) -> Optional[str]:
    """
    Get the server domain that the app is hosted on
    """
    global _server_domains
    if not _server_domains.get(module_name):
        if request is None: return None
        if not module_domains: 
            module_domains = ['localhost', module_name]
        if any(
            domain in request.url.hostname for 
            domain in module_domains
        ):
            _server_domains[module_name] = f'{request.url.scheme}://{request.url.hostname}'
            if request.url.port and request.url.port not in {80, 443}:
                _server_domains[module_name] += f':{request.url.port}'
            if verbose: logger.info(f"[{module_name}] Setting Server Domain: {_server_domains[module_name]} from {request.url}")
    return _server_domains.get(module_name)


"""
Dynamic Patching of OpenAPI Specs by Role
"""

class OpenAPIRoleSpec(ABC):

    role: Optional[Union['UserRole', str]] = None
    
    included_paths: Optional[List[Union[str, Dict[str, str]]]] = []
    excluded_paths: Optional[List[Union[str, Dict[str, str]]]] = []

    included_tags: Optional[List[str]] = []
    excluded_tags: Optional[List[str]] = []

    included_schemas: Optional[List[str]] = []
    excluded_schemas: Optional[List[str]] = []

    openapi_schema: Optional[Dict[str, Any]] = None
    description_callable: Optional[Callable] = None

    def __init__(
        self, 
        role: Optional['UserRole'] = None,
        included_paths: Optional[List[str]] = None,
        excluded_paths: Optional[List[str]] = None,
        included_tags: Optional[List[str]] = None,
        excluded_tags: Optional[List[str]] = None,
        included_schemas: Optional[List[str]] = None,
        excluded_schemas: Optional[List[str]] = None,
        openapi_schema: Optional[Dict[str, Any]] = None,

        description_callable: Optional[Callable] = None,
        **kwargs
    ):
        self.role = role or UserRole.ANON
        self.included_paths = included_paths or []
        self.excluded_paths = excluded_paths or []
        self.included_tags = included_tags or []
        self.excluded_tags = excluded_tags or []
        self.included_schemas = included_schemas or []
        self.excluded_schemas = excluded_schemas or []
        self.openapi_schema = openapi_schema
        self.description_callable = description_callable
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def has_description_callable(self) -> bool:
        """
        Check if the role spec has a description callable
        """
        return self.description_callable is not None

    

_openapi_schemas_by_role: Dict[str, Dict[UserRole, OpenAPIRoleSpec]] = {}

def setup_new_module_schema(
    module_name: str,
    roles: List[OpenAPIRoleSpec],
):
    """
    Create a new module schema
    """
    global _openapi_schemas_by_role
    if module_name not in _openapi_schemas_by_role:
        _openapi_schemas_by_role[module_name] = {}
        for role in roles:
            _openapi_schemas_by_role[module_name][role.role] = role

def get_module_by_role_schema(module_name: str) -> Dict[UserRole, OpenAPIRoleSpec]:
    """
    Get the module by role schema
    """
    global _openapi_schemas_by_role
    return _openapi_schemas_by_role[module_name]

def extract_schemas_from_path_operation(
    spec: Dict[str, Dict[str, Any]],
) -> List[str]:
    """
    Extract the schemas from a path operation
    """
    schemas = []
    for response in spec['responses'].values():
        if 'content' not in response: continue
        for content in response['content'].values():
            if 'schema' not in content: continue
            if 'definitions' in content['schema']:
                schemas += content['schema']['definitions'].keys()
            if 'title' in content['schema']:
                schemas.append(content['schema']['title'])
            if '$ref' in content['schema']:
                schemas.append(content['schema']['$ref'].split('/')[-1])
    
    return schemas

def set_module_role_spec(
    module_name: str,
    role_spec: OpenAPIRoleSpec,
):
    """
    Set the module role spec
    """
    global _openapi_schemas_by_role
    _openapi_schemas_by_role[module_name][role_spec.role] = role_spec

def create_openapi_schema_by_role_function(
    module_name: str,
    roles: List[OpenAPIRoleSpec],
    module_domains: Optional[List[str]] = None,

    default_exclude_paths: Optional[List[str]] = None,

    replace_patches: Optional[List[Tuple[str, Union[Callable, Optional[str]]]]] = None,
    replace_key_start: Optional[str] = KEY_START,
    replace_key_end: Optional[str] = KEY_END,
    replace_sep_char: Optional[str] = KEY_SEP,
    verbose: Optional[bool] = True,
    **kwargs
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """
    Create an openapi schema by role
    """

    setup_new_module_schema(module_name = module_name, roles = roles)
    if not default_exclude_paths: default_exclude_paths = []

    def patch_openapi_description(
        role_spec: OpenAPIRoleSpec,
        schema: Dict[str, Union[Dict[str, Union[Dict[str, Any], Any]], Any]],
        request: Optional['Request'] = None,
    ) -> Dict[str, Any]:
        """
        Patch the openapi schema description
        """
        if domain_name := get_server_domain(request = request, module_name = module_name, module_domains = module_domains, verbose = verbose):
            schema['info']['description'] = schema['info']['description'].replace(
                '<<DOMAIN>>', domain_name
            ).replace('>>DOMAIN<<', domain_name)
            if role_spec.has_description_callable:
                schema['info']['description'] = role_spec.description_callable(
                    schema['info']['description'],
                    domain_name,
                    role_spec,
                )
        return schema
    

    def patch_openapi_paths(
        role_spec: OpenAPIRoleSpec,
        schema: Dict[str, Union[Dict[str, Union[Dict[str, Any], Any]], Any]],
    ) -> Dict[str, Any]:
        """
        Patch the openapi schema paths
        """
        
        # Remove tags
        for path, methods in schema['paths'].items():
            for method, spec in methods.items():
                if 'tags' in spec and any(tag in role_spec.excluded_tags for tag in spec['tags']):
                    role_spec.excluded_paths.append(path)
                    # schemas_to_remove += await _extract_schemas_from_path_operation(spec)

        for path in role_spec.excluded_paths:
            if isinstance(path, str):
                schema['paths'].pop(path, None)
            elif isinstance(path, dict):
                schema['paths'][path['path']].pop(path['method'], None)
        
        for path in default_exclude_paths:
            if path in role_spec.included_paths: continue
            if isinstance(path, str):
                schema['paths'].pop(path, None)
            elif isinstance(path, dict):
                schema['paths'][path['path']].pop(path['method'], None)
        
        # Remove schemas
        # Compile the schemas to remove
        if 'components' not in schema: return schema
        if 'schemas' not in schema['components']: return schema
        _schemas_to_remove = []
        for schema_name in role_spec.excluded_schemas:
            if '*' in schema_name:
                _schemas_to_remove += [
                    schema for schema in schema['components']['schemas'].keys() if
                    re.match(schema_name, schema)
                ]
            else:
                _schemas_to_remove.append(schema_name)
        _schemas_to_remove = list(set(_schemas_to_remove))
        for schema_name in _schemas_to_remove:
            schema['components']['schemas'].pop(schema_name, None)
        schema['components']['schemas'] = dict(sorted(schema['components']['schemas'].items()))
        return schema


    def get_openapi_schema_by_role(
        user_role: Optional[Union['UserRole', str]] = None,
        request: Optional['Request'] = None,
        app: Optional['FastAPI'] = None,
    ) -> Dict[str, Any]:
        """
        Get the openapi schema by role
        """

        module_schemas = get_module_by_role_schema(module_name = module_name)
        role = user_role or UserRole.ANON
        role_spec = module_schemas[role]
        if not role_spec.openapi_schema:
            if verbose: logger.info("Generating OpenAPI Schema", prefix = role)
            schema = copy.deepcopy(app.openapi()) if app else copy.deepcopy(get_openapi_schema(module_name))
            patch_openapi_description(
                role_spec = role_spec,
                schema = schema,
                request = request,
            )
            patch_openapi_paths(
                role_spec = role_spec,
                schema = schema,
            )
            if replace_patches:
                for patch in replace_patches:
                    key, value = patch
                    if callable(value): value = value()
                    schema = json_replace(
                        schema = schema,
                        key = key,
                        value = value,
                        key_start = replace_key_start,
                        key_end = replace_key_end,
                        sep_char = replace_sep_char,
                    )
            role_spec.openapi_schema = schema
            set_module_role_spec(
                module_name = module_name,
                role_spec = role_spec,
            )
        return role_spec.openapi_schema
    
    return get_openapi_schema_by_role

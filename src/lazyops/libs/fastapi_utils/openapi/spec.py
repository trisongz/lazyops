from __future__ import annotations

"""
Usage:



"""

import re
import json
import copy
import contextlib
import operator

from abc import ABC
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union, Callable, Tuple, TYPE_CHECKING
from lazyops.utils import logger
from lazyops.utils.lazy import lazy_import
from lazyops.libs.fastapi_utils.types.user_roles import UserRole

if TYPE_CHECKING:
    from fastapi import Request, FastAPI


KEY_START = '[x-repl-start]'
KEY_END = '[x-repl-end]'
KEY_SEP = '||'
DOMAIN_KEY = 'DOMAIN'

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
        if verbose: logger.info(f"Replaced `{segment}` -> `{src_value}`", colored = True, prefix = "|g|OpenAPI|e|")
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
    openapi_spec_map: Optional[Dict[str, Union[str, Tuple[str, int]]]] = None,

    # Extra Schemas
    enable_description_path_patch: Optional[bool] = None,
    **kwargs
) -> Dict[str, Any]:  # sourcery skip: low-code-quality
    """
    Patch the openapi schema

    Operations:

    1. If `openapi_spec_map` is provided, it will be used to replace the values in the openapi schema
      This operation uses JSON to repalce the string values by dumping/loading
    2. If `schemas_patches` is provided, it will be used to patch the openapi schema
    3. If `replace_patches` is provided, it will be used to replace the values in the openapi schema
    4. If `enable_description_path_patch` is provided, it will be used to patch the openapi schema
      This operation replaces any `CURRENT_OPENAPI_PATH` with the current path
    """
    global _openapi_schemas
    if module_name not in _openapi_schemas or overwrite:
        if verbose: logger.info(f"[|g|{module_name}|e|] Patching OpenAPI Schema", colored = True)
        if openapi_spec_map:
            _spec = json.dumps(openapi_schema)
            for key, value in openapi_spec_map.items():
                if isinstance(value, tuple):
                    _spec = _spec.replace(key, value[0], value[1])
                else:
                    _spec = _spec.replace(key, value)
            openapi_schema = json.loads(_spec)

        for path, patch in schemas_patches.items():
            with contextlib.suppress(Exception):
                patch_source = openapi_schema['components']['schemas'].pop(patch['source'], None)
                if patch_source is None: continue

                patch_source['title'] = patch['schema']
                openapi_schema['components']['schemas'][patch['schema']] = patch_source

                # Handle Paths
                openapi_schema['paths'][path]['post']['requestBody']['content']['multipart/form-data']['schema']['$ref'] = f'#/components/schemas/{patch["schema"]}'
        
        if enable_description_path_patch:
            with contextlib.suppress(Exception):
                for path in openapi_schema['paths']:
                    for method in openapi_schema['paths'][path]:
                        if 'description' in openapi_schema['paths'][path][method] and 'CURRENT_OPENAPI_PATH' in openapi_schema['paths'][path][method]['description']:
                            # logger.info(f"Patching Description Path: {path}", prefix = '|g|OpenAPI|e|', colored = True)
                            openapi_schema['paths'][path][method]['description'] = openapi_schema['paths'][path][method]['description'].replace('CURRENT_OPENAPI_PATH', path)


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

        if 'schemas' in openapi_schema.get('components', {}):
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
    replace_domain_key: Optional[str] = DOMAIN_KEY,
    openapi_spec_map: Optional[Dict[str, Union[str, Tuple[str, int]]]] = None,
    enable_description_path_patch: Optional[bool] = None,

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
            openapi_spec_map = openapi_spec_map,
            enable_description_path_patch = enable_description_path_patch,
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
    force_https: Optional[bool] = None,
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
            scheme = 'https' if (force_https or request.url.port == 443) else request.url.scheme
            # _server_domains[module_name] = f'{request.url.scheme}://{request.url.hostname}'
            _server_domains[module_name] = f'{scheme}://{request.url.hostname}'
            if request.url.port and request.url.port not in {80, 443}:
                _server_domains[module_name] += f':{request.url.port}'
            if verbose: logger.info(f"[|g|{module_name}|e|] Setting Server Domain: {_server_domains[module_name]} from {request.url}", colored = True)
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

    extra_schemas: Optional[List[Union[BaseModel, Dict[str, Any], str]]] = None

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
        extra_schemas: Optional[List[Union[BaseModel, Dict[str, Any], str]]] = None,
        extra_schema_prefix: Optional[str] = None,
        extra_schema_name_mapping: Optional[Dict[str, str]] = None,
        extra_schema_ref_template: Optional[str] = '#/components/schemas/{model}',
        extra_schema_example_mapping: Optional[Dict[str, Dict[str, Any]]] = None,
        extra_schema_example_callable: Optional[Callable] = None,
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
        if extra_schemas is not None:
            self.extra_schemas = extra_schemas
        self.extra_schema_prefix = extra_schema_prefix
        self.extra_schema_name_mapping = extra_schema_name_mapping
        self.extra_schemas_populated = False
        self.extra_schemas_data: Dict[str, Dict[str, Any]] = None
        self.extra_schema_ref_template = extra_schema_ref_template
        self.extra_schema_example_mapping = extra_schema_example_mapping
        self.extra_schema_example_callable = extra_schema_example_callable
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def has_description_callable(self) -> bool:
        """
        Check if the role spec has a description callable
        """
        return self.description_callable is not None
    
    def populate_extra_schemas(self):
        """
        Populate the extra schemas
        """
        if self.extra_schemas_populated: return
        if not self.extra_schemas: return
        self.extra_schemas_data = {}
        for schema in self.extra_schemas:
            if isinstance(schema, str):
                try:
                    schema = lazy_import(schema)
                except Exception as e:
                    logger.warning(f"Invalid Extra Schema: {schema}, {e}")
                    continue
            if isinstance(schema, type(BaseModel)):
                schema_name = schema.__name__
                try:
                    schema = schema.model_json_schema(
                        ref_template = self.extra_schema_ref_template
                    )
                except Exception as e:
                    logger.warning(f"Invalid Extra Schema: {schema}, {e}")
                    continue
            elif isinstance(schema, dict):
                if 'title' not in schema:
                    logger.warning(f"Invalid Extra Schema. Does not contain `title` in schema: {schema}")
                    continue
                schema_name = schema['title']
            else:
                logger.warning(f"Invalid Extra Schema: {schema}")
                continue
            if self.extra_schema_name_mapping and schema_name in self.extra_schema_name_mapping:
                schema['title'] = self.extra_schema_name_mapping[schema_name]
            elif self.extra_schema_prefix:
                schema['title'] = f'{self.extra_schema_prefix}{schema_name}'
            
            if self.extra_schema_example_callable:
                if schema_example := self.extra_schema_example_callable(schema = schema, schema_name = schema_name):
                    schema['example'] = schema_example
            elif self.extra_schema_example_mapping and schema_name in self.extra_schema_example_mapping:
                schema['example'] = self.extra_schema_example_mapping[schema_name]
            self.extra_schemas_data[schema_name] = schema
        self.extra_schemas_populated = True


    

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
    domain_name: Optional[str] = None,
    domain_name_force_https: Optional[bool] = None,

    default_exclude_paths: Optional[List[str]] = None,

    replace_patches: Optional[List[Tuple[str, Union[Callable, Optional[str]]]]] = None,
    replace_key_start: Optional[str] = KEY_START,
    replace_key_end: Optional[str] = KEY_END,
    replace_sep_char: Optional[str] = KEY_SEP,
    replace_domain_key: Optional[str] = DOMAIN_KEY,
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
        force_https: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Patch the openapi schema description
        """
        nonlocal domain_name
        if domain_name is None: domain_name = get_server_domain(
            request = request, 
            module_name = module_name, 
            module_domains = module_domains, 
            verbose = verbose,
            force_https = domain_name_force_https or force_https,
        )
        if domain_name:
            replace_domain_start = f'<<{replace_domain_key}>>'
            replace_domain_end = f'>>{replace_domain_key}<<'
            schema['info']['description'] = schema['info']['description'].replace(
                replace_domain_start, domain_name
            ).replace(replace_domain_end, domain_name)
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
        if role_spec.extra_schemas:
            role_spec.populate_extra_schemas()
            # if verbose:
            #     logger.info(f"Populating Extra Schemas for {role_spec.role}\n{list(role_spec.extra_schemas_data.keys())}", prefix = module_name)
            schema['components']['schemas'].update(role_spec.extra_schemas_data)
        schema['components']['schemas'] = dict(sorted(schema['components']['schemas'].items(), key = lambda x: operator.itemgetter('title')(x[1])))
        return schema


    def get_openapi_schema_by_role(
        user_role: Optional[Union['UserRole', str]] = None,
        request: Optional['Request'] = None,
        app: Optional['FastAPI'] = None,
        force_https: Optional[bool] = None,
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
                force_https = domain_name_force_https or force_https,
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

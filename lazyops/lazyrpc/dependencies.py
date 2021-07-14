from ._base import *
from .models import Params


def fix_query_dependencies(dependant: Dependant):
    dependant.body_params.extend(dependant.query_params)
    dependant.query_params = []

    for field in dependant.body_params:
        if not isinstance(field.field_info, Params):
            field.field_info.embed = True

    for sub_dependant in dependant.dependencies:
        fix_query_dependencies(sub_dependant)


def clone_dependant(dependant: Dependant) -> Dependant:
    new_dependant = Dependant()
    new_dependant.path_params = dependant.path_params
    new_dependant.query_params = dependant.query_params
    new_dependant.header_params = dependant.header_params
    new_dependant.cookie_params = dependant.cookie_params
    new_dependant.body_params = dependant.body_params
    new_dependant.dependencies = dependant.dependencies
    new_dependant.security_requirements = dependant.security_requirements
    new_dependant.request_param_name = dependant.request_param_name
    new_dependant.websocket_param_name = dependant.websocket_param_name
    new_dependant.response_param_name = dependant.response_param_name
    new_dependant.background_tasks_param_name = dependant.background_tasks_param_name
    new_dependant.security_scopes = dependant.security_scopes
    new_dependant.security_scopes_param_name = dependant.security_scopes_param_name
    new_dependant.name = dependant.name
    new_dependant.call = dependant.call
    new_dependant.use_cache = dependant.use_cache
    new_dependant.path = dependant.path
    new_dependant.cache_key = dependant.cache_key
    return new_dependant


def insert_dependencies(target: Dependant, dependencies: Sequence[Depends] = None):
    assert target.path
    if not dependencies:
        return
    for depends in dependencies[::-1]:
        target.dependencies.insert(
            0,
            get_parameterless_sub_dependant(depends=depends, path=target.path),
        )

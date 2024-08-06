from __future__ import annotations

"""
Env Var Helpers
"""

import os
import re
import json
from pathlib import Path
from lazyops.utils.helpers import build_dict_from_str
from typing import Any, Dict, List, Optional, Tuple, Union, Type, TypeVar, TYPE_CHECKING


EnvT = TypeVar('EnvT')

def parse_from_envvar(
    var: str,
    default: Optional[Any] = None,
    _type: Optional[Type[EnvT]] = str,
) -> EnvT:
    """
    Parse a value from an environment variable
    """
    val = os.getenv(var)
    if val is None: return default

    # Try to evaluate the value
    if _type is None: 
        # print('No type: ', val)
        return val
        # if val.startswith(('{', '[')):
        #     return json.loads(val)
        # return build_dict_from_str(val) if val.startswith('{') else val.split(',')
    if _type in {list, dict}:
        if val.startswith(('{', '[')):
            return json.loads(val)
        return build_dict_from_str(val) if _type is dict else val.split(',')

    if _type is Path:
        return Path(val)
    
    if _type is bool:
        return val.lower() in {'true', '1', 't', 'y', 'yes'}
    
    return _type(val)


def parse_envvars_from_text(
    text: str,
    values: Optional[Dict[str, Any]] = None,
    envvar_prefix: Optional[str] = 'env/',
) -> Tuple[str, Dict[str, Any]]:
    """
    Parse values from a text block

    Returns:
        Tuple[str, Dict[str, Any]]: The text with the envvars replaced and the parsed values
    """

    # Create a pattern that would match env/ENVVAR_NAME and capture the ENVVAR_NAME
    _prefix = envvar_prefix.replace('/', '\/')
    pattern = re.compile(rf'({_prefix}\w+)')

    # Find all
    values = values or {}
    matches = pattern.findall(text)
    for match in matches:
        # var = match[0]
        envvar = match.replace(envvar_prefix, '')
        # print(match, envvar)
        _default = values.get(envvar)
        if isinstance(_default, type):
            _type = _default
            _default = None
        else:
            _type = type(_default) if _default is not None else None
        val = parse_from_envvar(envvar, default=_default, _type=_type)
        # if val is not None:
        values[envvar] = val
        # print(match, val, values)
        text = text.replace(match, val if val is not None else '')

    return text, values



def load_env_vars(
    env_file: str,
    categories: Optional[Union[str, List[str]]] = None,
    target_app: Optional[str] = None,
    included_apps: Optional[Union[str, List[str]]] = None,
    excluded_apps: Optional[Union[str, List[str]]] = None,
    included_vars: Optional[Union[str, List[str]]] = None,
    excluded_vars: Optional[Union[str, List[str]]] = None,
    set_as_env: Optional[bool] = False,
    overwrite: Optional[bool] = True,
) -> Dict[str, str]:
    """
    Load Environment Variables from a YAML file

    """
    import yaml
    configs: List[Dict[str, Union[str, Dict[str, Any], List[str]]]] = yaml.safe_load(
        Path(env_file).read_text()
    )
    if included_vars and not isinstance(included_vars, list):
        included_vars = [included_vars]
    if excluded_vars and not isinstance(excluded_vars, list):
        excluded_vars = [excluded_vars]
    if included_apps and not isinstance(included_apps, list):
        included_apps = [included_apps]
    if excluded_apps and not isinstance(excluded_apps, list):
        excluded_apps = [excluded_apps]
    if categories and not isinstance(categories, list):
        categories = [categories]
    
    if target_app:
        if not included_apps: included_apps = []
        included_apps.append(target_app)
    
    envvars: Dict[str, str] = {}
    for config in configs:
        if config.get('disabled', False): continue
        if config.get('category') and categories and \
            all(cat not in config['category'] for cat in categories):
            continue
        if included_vars and config['name'] not in included_vars:
            continue
        if excluded_vars and config['name'] in excluded_vars:
            continue
        if config.get('apps'):
            if included_apps and all(app not in included_apps for app in config['apps']): 
                continue
            if excluded_apps and any(app in excluded_apps for app in config['apps']):
                continue
        for key, value in config['envs'].items():
            if not value: continue
            if isinstance(value, dict) and target_app:
                value = value.get(target_app)
            if isinstance(value, list):
                value = f'[{", ".join(value)}]'
            elif isinstance(value, dict):
                value = json.dumps(value)
            elif not isinstance(value, str):
                value = str(value)
            envvars[key] = value
            if set_as_env and (overwrite or key not in os.environ):
                os.environ[key] = value
    return envvars
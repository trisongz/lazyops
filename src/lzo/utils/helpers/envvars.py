from __future__ import annotations

"""
Env Var Helpers
"""

import os
import re
import json
import subprocess
import warnings
warnings.filterwarnings("ignore", message = "invalid escape sequence")
from pathlib import Path
from .formatting import build_dict_from_str
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

# _envvar_pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
# _envvar_pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\:[A-Za-z_][A-Za-z0-9_]*)*)\}")
# _envvar_pattern = re.compile(r"\$\{([A-Za-z_][\w\.]*(?:\:[A-Za-z_][\w]*)*)\}")
_envvar_pattern = re.compile(r"\$\{([^}]*)\}")
_envkey_getters = {
    'HOST': (lambda: os.uname().nodename), 
    'HOSTNAME': (lambda: os.uname().nodename),
}

def dummy_sample(t: str, *args) -> str:
    return f'{t}-1'

def get_cmd_output(cmd: str, *args) -> str:
    """
    Runs a command and returns the output
    """
    cmd = cmd.lstrip('$(').rstrip(')')
    with os.popen(cmd) as pipe:
        return pipe.read().strip()

        
def replace_envvars_in_text(
    text: str,
    enable_function_calls: Optional[bool | str] = 'auto',
    enable_shell_commands: Optional[bool | str] = 'auto',
) -> str:
    """
    Replaces all envvars in a text with their values

    All env vars need to be wrapped in ${} to be replaced.

    If `enable_function_calls` is True, then any envvars that are prefixed with
    `func:` will be treated as a function call and the result will be used as the value.

    If `enable_shell_commands` is True, then any envvars that are prefixed with
    `cmd:` will be treated as a shell command and the result will be used as the value.

    Example:
        >>> replace_envvars_in_text("Hello, ${NAME}!")
        "Hello, John!"

        >>> replace_envvars_in_text("Hello, ${func:get_name:John}!")
        "Hello, John!"

        >>> replace_envvars_in_text("Hello, ${cmd:$(echo 'John')}!")
        "Hello, John!"

    """
    from lzl.load import lazy_import
    if enable_function_calls == 'auto': enable_function_calls = '${func:' in text
    if enable_shell_commands == 'auto': enable_shell_commands = '${cmd:' in text
    for match in _envvar_pattern.finditer(text):
        envvar = match.group(1)
        _default = ''
        # print(envvar)
        if enable_function_calls and envvar.startswith('func:'):
            parts = envvar.split(':')
            args = parts[2:] or []
            func = lazy_import(parts[1])
            value = func(*args)
        elif enable_shell_commands and envvar.startswith('cmd:'):
            parts = envvar.split(':')
            args = parts[2:] or []
            value = get_cmd_output(parts[1], *args)
        elif envvar in _envkey_getters: value = _envkey_getters[envvar]()
        else: 
            if ':-' in envvar:
                envvar, _default = envvar.split(':-')
            value = os.getenv(envvar)
        value = value or _default
        text = text.replace(match.group(0), value)
    return text


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


_default_envkeys = [
    'IN_CI_ENV',
    'DOCKER_CI',
    'BUILDER_CI',
    'APP_ENV=CI',
    'BUILD_ENV=CI',
]

_is_in_ci: Optional[bool] = None

def is_in_ci_env(
    envkeys: Optional[List[str]] = _default_envkeys,
    enable_global_check: bool = True,
) -> bool:
    """
    Checks if the code is running in a CI environment
    """
    global _is_in_ci
    if _is_in_ci is not None and enable_global_check: 
        return _is_in_ci
    
    def _run_check():
        for key in envkeys:
            if '=' in key:
                key, value = key.split('=', 1)
                if os.getenv(key, '') == value:
                    return True
            elif os.getenv(key, '').lower() in {'true', '1', 't', 'y', 'yes'}:
                return True
        return False
    
    _is_in_ci = _run_check()
    return _is_in_ci
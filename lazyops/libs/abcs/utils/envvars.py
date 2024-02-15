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


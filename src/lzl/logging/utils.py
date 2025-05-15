from __future__ import annotations

import re
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

from .static import DEFAULT_STATUS_COLORS, COLORED_MESSAGE_MAP, RESET_COLOR, LOGLEVEL_MAPPING
from typing import Optional, Dict, Any, Union, Type, Callable, Set, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel
    from dataclasses import _DataclassT

    Primitives = Union[str, int, float, bool, tuple, List, type(None)]
    MsgItem = Union[BaseModel, _DataclassT, Dict[str, Any], Primitives]

def find_and_format_seps(msg: str) -> str:
    """
    Find any |a,b,c| and format them |a||b||c|

    ex:
      |em,b,u| -> |em||b||u|
      |em,b| -> |em||b|
      
    """
    # v2
    for sep_match in re.finditer('\|\w+,(\w+,*)+\|', msg):
        s = sep_match.group()
        if len(s) >= 10: continue
        msg = msg.replace(s, "||".join(s.split(",")))
    return msg

def extract_module_name(name: str) -> str:
    """
    Extracts the module name from a name
    """
    return name.split('.')[0]


def get_prefix_and_suffix(
    colored: Optional[bool] = False,
    level: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Gets the prefix and suffix for the message
    """
    prefix, suffix = '', ''
    if colored:
        if level:
            level = level.lower()
            prefix = DEFAULT_STATUS_COLORS.get(level, '|g|')
        suffix = '|e|'
    return prefix, suffix

def format_item(
    msg: 'MsgItem',
    max_length: Optional[int] = None,
    colored: Optional[bool] = False,
    level: Optional[str] = None,
    _is_part: Optional[bool] = False,
) -> str:  # sourcery skip: extract-duplicate-method, low-code-quality, split-or-ifs
    # Primitive Types
    if isinstance(msg, str): return msg[:max_length] if max_length else msg
    if isinstance(msg, (float, int, bool, type(None))): return str(msg)[:max_length] if max_length else str(msg)
    if isinstance(msg, (list, set)):
        _msg = str(msg) if _is_part else "\n" + "".join(f'- {item}\n' for item in msg)
        return _msg[:max_length] if max_length else _msg
    
    prefix, suffix = get_prefix_and_suffix(colored = colored, level = level)
    if isinstance(msg, dict):
        _msg = "\n"
        for key, value in msg.items():
            _value = f'{value}'
            if max_length and len(_value) > max_length:
                _value = f'{_value[:max_length]}...'
            _msg += f'- {prefix}{key}{suffix}: {_value}\n'
        return _msg.rstrip()
    
    if isinstance(msg, tuple):
        _msg = "".join(f'- {prefix}{key}{suffix}: {format_item(value, max_length = max_length, colored = colored, level = level,  _is_part = True)}\n' for key, value in zip(msg[0], msg[1]))
        return _msg[:max_length] if max_length else _msg

    # Test for FileIO
    if hasattr(msg, 'is_fsspec'):
        return format_item(repr(msg), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

    # Complex Types
    # Likely Pydantic Model v1
    if (hasattr(msg, 'dict') and hasattr(msg, 'Config')) or hasattr(msg, 'fields'):
        # Likely Pydantic Model
        _msg = f'{prefix}[{msg.__class__.__name__}]{suffix}'
        fields = msg.fields.keys() if hasattr(msg, 'fields') else msg.__fields__.keys()
        for field in fields:
            field_str = f'{prefix}{field}{suffix}'
            val_s = f'\n  {field_str}: {getattr(msg, field)!r}'
            if max_length is not None and len(val_s) > max_length:
                val_s = f'{val_s[:max_length]}...'
            _msg += val_s
        return _msg
    
    # Pydantic Model v2
    if hasattr(msg, 'model_dump'):
        return format_item(msg.model_dump(mode = 'json'), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

    if hasattr(msg, 'dict'):
        return format_item(msg.dict(), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

    if hasattr(msg, 'json'):
        return format_item(msg.json(), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

    if hasattr(msg, '__dict__'):
        return format_item(msg.__dict__, max_length = max_length, colored = colored, level = level, _is_part = _is_part)
    
    return str(msg)[:max_length] if max_length else str(msg)


def format_message(
    message: 'MsgItem', 
    *args,
    prefix: Optional[str] = None,
    max_length: Optional[int] = None,
    level: Optional[str] = None,
    colored: Optional[bool] = False,
) -> str:
    """
    Formats the message

    "example |b|msg|e|"
    -> "example <blue>msg</><reset>"
    """
    _message = ""
    if prefix: 
        if colored and '|' not in prefix: 
            base_color = '|g|'
            if level:
                level = level.lower()
                base_color = DEFAULT_STATUS_COLORS.get(level, '|g|')
            prefix = f'{base_color}{prefix}|e|'
        _message += f'[{prefix}] '
    _message += format_item(message, max_length = max_length, colored = colored, level = level)
    if args:
        for arg in args:
            _message += "\n"
            _message += format_item(arg, max_length = max_length, colored = colored, level = level)
    if colored:
        # Add escape characters to prevent errors
        _message = _message.replace("<fg", ">|fg")
        _message = _message.replace("<", "\</")
        _message = find_and_format_seps(_message)
        # print(_message)
        for key, value in COLORED_MESSAGE_MAP.items():
            _message = _message.replace(key, value)
        _message = _message.replace(">|fg", "<fg")
        _message = _message.replace("\</", "\<")
        _message += RESET_COLOR
    return _message


def get_logging_level(level: Union[str, int]) -> str:
    """
    Gets the logging level
    """
    if isinstance(level, str): level = level.upper()
    elif isinstance(level, int): level = LOGLEVEL_MAPPING.get(level, 'INFO')
    return level



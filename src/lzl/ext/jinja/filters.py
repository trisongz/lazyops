from __future__ import annotations

"""
Helpers
"""
import json
import yaml
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, TYPE_CHECKING

def to_yaml(data, indent: Optional[int] = None):
    return yaml.safe_dump(data, default_flow_style = False, indent = indent)

def to_json(data, indent: Optional[int] = None):
    return json.dumps(data, indent = indent)

def to_base64(data: Dict[str, str]):
    """
    Converts a dict to a base64 string
    """
    return {k: base64.b64encode(v.encode('utf-8')).decode('utf-8') for k, v in data.items()}

def get_http(url: str, headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None, **kwargs) -> str:
    """
    Returns the HTTP Response
    """
    from lzl.api import aiohttpx
    return aiohttpx.get(url, headers = headers, timeout = timeout, **kwargs).text

def load_file(path: str) -> str:
    """
    Loads a file
    """
    from lzl.io.file import File
    return File(path).read_text()

def to_title(text: str) -> str:
    """
    Converts a string to title case
    """
    return text.replace('_', ' ').title()

def normalize_value(value: str | list | Any) -> Any:
    """
    Normalizes a value
    """
    if isinstance(value, list): return ', '.join(value)
    return value.strip() if isinstance(value, str) else value


def normalize_ids_to_str(ids: List[str | int]) -> str:
    """
    Normalizes the ids to a string
    """
    if isinstance(ids[0], int): return ', '.join([str(id) for id in ids])
    return ', '.join([f"'{id}'" for id in ids])

autofilters = {
    'to_json': to_json,
    'to_yaml': to_yaml,
    'to_base64': to_base64,
    'get_http': get_http,
    'load_file': load_file,
    'to_title': to_title,
    'normalize_value': normalize_value,
    'normalize_ids_to_str': normalize_ids_to_str,
}
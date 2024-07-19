from __future__ import annotations

"""
Helpers
"""

import yaml
import base64
import jinja2
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING


def to_yaml(data):
    return yaml.safe_dump(data)


def to_base64(data: Dict[str, str]):
    """
    Converts a dict to a base64 string
    """
    return {k: base64.b64encode(v.encode('utf-8')).decode('utf-8') for k, v in data.items()}
    

def create_jinja_env(
    path: Path,
    **kwargs
) -> jinja2.Environment:
    """
    Creates a jinja2 environment that adds 
    filters and functions to the environment
    """
    templates = jinja2.Environment(
        loader = jinja2.FileSystemLoader(path),
        **kwargs
    )
    templates.filters['to_yaml'] = to_yaml
    templates.filters['to_base64'] = to_base64
    return templates

"""
Jinja2 Extension

- Unifies the Jinja2 Environment handle both sync and async
"""
from typing import TYPE_CHECKING
from .base import Environment, autofilters, FileSystemLoader

if TYPE_CHECKING:
    from jinja2.environment import Template
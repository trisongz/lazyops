"""
Support Lazy Loading of Modules

- Credit: https://github.com/kevdog824
"""

from .main import LazyLoad, lazy_load, load
from .wrappers import lazy_function_wrapper
from typing import TYPE_CHECKING
"""
Support Lazy Loading of Modules

- Credit: https://github.com/kevdog824

from lzl import load

if load.TYPE_CHECKING:
    import matplotlib
    import os
    import pandas as pd
    import aenum
else:
    matplotlib = load.LazyLoad("matplotlib")
    os = load.LazyLoad("os")
    pd = load.LazyLoad("pandas")
    # This will install the aenum library if it is not already installed
    aenum = load.LazyLoad("aenum", install_missing = True)


def sometimes_called():
    # if this function is not called pandas library is never loaded
    pd.show_versions()
    aenum.extend_enum()


print(os)                  # prints <Uninitialized module 'os'>
os.cpu_count()             # attribute access on LazyLoad object implicitly loads module
print(os)                  # prints <module 'os' (frozen)>


print(matplotlib)          # prints <Uninitialized module 'matplotlib'>
load.load(matplotlib)  # explicitly load the module backing this LazyLoad object
print(matplotlib)          # prints <module 'matplotlib' from '...'>


sometimes_called()
"""

from .main import LazyLoad, lazy_load, load
from .wrappers import lazy_function_wrapper
from .utils import lazy_import, lazy_function, is_coro_func, import_string, import_function, validate_callable, import_from_string
from typing import TYPE_CHECKING
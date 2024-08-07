"""
Support Lazy Loading of Modules

- Credit: https://github.com/kevdog824


from lazyops.libs import lazyload

if lazyload.TYPE_CHECKING:
    import matplotlib
    import os
    import pandas as pd
else:
    matplotlib = lazyload.LazyLoad("matplotlib")
    os = lazyload.LazyLoad("os")
    pd = lazyload.LazyLoad("pandas")


def sometimes_called():
    # if this function is not called pandas library is never loaded
    pd.show_versions()


print(os)                  # prints <Uninitialized module 'os'>
os.cpu_count()             # attribute access on LazyLoad object implicitly loads module
print(os)                  # prints <module 'os' (frozen)>


print(matplotlib)          # prints <Uninitialized module 'matplotlib'>
lazyload.load(matplotlib)  # explicitly load the module backing this LazyLoad object
print(matplotlib)          # prints <module 'matplotlib' from '...'>


sometimes_called()
"""

from .main import LazyLoad, lazy_load, load
from .wrappers import lazy_function_wrapper
from typing import TYPE_CHECKING
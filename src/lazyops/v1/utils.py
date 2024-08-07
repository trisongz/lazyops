import os
import sys
import asyncio
import threading
from uuid import uuid4
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from lazyops.models import LazyData
from lazyops.common import lazy_import, lazylibs
from lazyops.retry import retryable

def create_uuid(name=None, sep='-', strip=False):
    uid = str(uuid4())
    if name: uid = name + sep + uid
    if strip: uid.replace(sep, '').strip().replace('-', '').strip()
    return uid

def latest_tf_ckpt(model_path):
    ckpt_mtg = lazy_import('tensorflow.python.training.checkpoint_management')
    latest = ckpt_mtg.latest_checkpoint(model_path)
    ckpt_num = int(latest.split('/')[-1].split('-')[-1])
    return LazyData(string=f"Latest Checkpoint = Step {ckpt_num} @ {latest}", value={'step': ckpt_num, 'path': model_path, 'latest_ckpt': latest}, dtype="tfcheckpoint")

def build_chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def list_to_dict(items, delim='='):
    res = {}
    for item in items:
        i = item.split(delim, 1)
        res[i[0].strip()] = i[-1].strip()
    return res


def get_variable_separator():
    """
    Returns the environment variable separator for the current platform.
    :return: Environment variable separator
    """
    if sys.platform.startswith('win'):
        return ';'
    return ':'


def find_binary_in_path(filename):
    """
    Searches for a binary named `filename` in the current PATH. If an executable is found, its absolute path is returned
    else None.
    :param filename: Filename of the binary
    :return: Absolute path or None
    """
    if 'PATH' not in os.environ:
        return None
    for directory in os.environ['PATH'].split(get_variable_separator()):
        binary = os.path.abspath(os.path.join(directory, filename))
        if os.path.isfile(binary) and os.access(binary, os.X_OK):
            return binary
    return None



def timed_cache(seconds: int, maxsize: int = 128):
    def wrapper_cache(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = timedelta(seconds=seconds)
        func.expiration = datetime.utcnow() + func.lifetime
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if datetime.utcnow() >= func.expiration:
                func.cache_clear()
                func.expiration = datetime.utcnow() + func.lifetime
            return func(*args, **kwargs)
        return wrapped_func
    return wrapper_cache


def require_module(name, *args, **kwargs):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            submod = lazylibs.get_submodule(name)
            if not submod:
                submod = lazylibs.setup_submodule(name, *args, **kwargs)
            if not submod.has_initialized:
                submod.lazy_init()            
            return f(*args, **kwargs)
        return wrapper
    return decorator

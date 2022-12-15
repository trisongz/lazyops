
"""
Import Handler for `torch`
"""
import sys
import typing
from lazyops.utils.imports import resolve_missing_custom, require_missing_wrapper

try:
    import torch
    _torch_available = True
except ImportError:
    torch = object
    _torch_available = False

def resolve_torch(
    required: bool = False,
    version: typing.Optional[str] = None,
    cuda: typing.Optional[str] = None,
    rocm: typing.Optional[str] = None,
):
    """
    Ensures that `torch` is available

    :arg cuda: If `True`, will attempt to import `torch` with CUDA support. 
    If str will attempt to import `torch` with the specified CUDA version.
    :type cuda: `str` or `bool`
    """
    global torch, _torch_available
    if not _torch_available:
        pkg = 'torch'
        is_win = sys.platform.startswith('win')
        if version is not None:
            pkg += f'=={version}'
            if cuda is not None:
                pkg += f'+cu{cuda}'
            elif rocm is not None:
                pkg += f'+rocm{rocm}'
            elif is_win:
                pkg += '+cpu'
            
        pkg += ' --extra-index-url https://download.pytorch.org/whl/torch'
        resolve_missing_custom(pkg, required = required)
        import torch
        _torch_available = True


def require_torch(
    required: bool = False,
    version: typing.Optional[str] = None,
    cuda: typing.Union[str, bool] = False,
    rocm: typing.Optional[str] = None,
):
    """
    Wrapper for `resolve_torch` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_torch, 
            func = func, 
            required = required,
            version = version,
            cuda = cuda,
            rocm = rocm,
        )
    return decorator
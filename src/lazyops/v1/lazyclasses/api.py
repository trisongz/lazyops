from .core import _process_class


def lazyclass(cls=None):
    if cls is not None:
        return _process_class(cls)
    return _process_class

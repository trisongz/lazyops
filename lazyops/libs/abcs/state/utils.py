

_base_worker_index: int = None

def get_base_worker_index() -> int:
    """
    Gets the base worker index
    """
    global _base_worker_index
    if _base_worker_index is None:
        from lazyops.utils.system import is_in_kubernetes, get_host_name
        if is_in_kubernetes() and get_host_name()[-1].isdigit():
            _base_worker_index = int(get_host_name()[-1])
        else:
            _base_worker_index = 0
    return _base_worker_index

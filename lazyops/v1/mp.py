from functools import lru_cache, wraps
from typing import List, Optional, Dict
from asgiref.sync import async_to_sync
from .mp_utils import multiproc, _MAX_PROCS, lazy_parallelize


class LazyProc:
    def __init__(self, name, func, start=False, daemon=False, *args, **kwargs):
        self.name = name
        self.func = func
        self.start = start
        self.args = args
        self.kwargs = kwargs
        self.daemon = daemon
    
    @property
    def config(self):
        return {'target': self.func, 'daemon': self.daemon, 'args': self.args, 'kwargs': self.kwargs}


class LazyProcs:
    active = False
    active_procs: Dict[str, multiproc.Process] = {}
    inactive_procs: Dict[str, multiproc.Process] = {}

    @classmethod
    def set_state(cls):
        LazyProcs.active = bool(LazyProcs.num_active > 1)

    @classmethod
    def add_proc(cls, proc: LazyProc):
        process = multiproc.Process(**proc.config)
        if proc.start:
            process.start()
            LazyProcs.active_procs[proc.name] = process
        else:
            LazyProcs.inactive_procs[proc.name] = process
        LazyProcs.set_state()
        return process
    
    @classmethod
    def kill_proc(cls, name: str):
        if name in LazyProcs.active_procs:
            proc = LazyProcs.active_procs.pop(name)
            proc.terminate()
            LazyProcs.inactive_procs[name] = proc
            LazyProcs.set_state()
    
    @classmethod
    def killall(cls):
        for name in LazyProcs.active_procs:
            LazyProcs.kill_proc(name)
    
    @property
    def num_active(self):
        return len(self.active_procs)
    
    @property
    def num_inactive(self):
        return len(self.inactive_procs)

def lazyproc(name: str = 'lazyproc', start: bool = True, daemon: bool = False):
    def wrapper_proc(func):
        def wrapped_proc(*args, **kwargs):
            proc = LazyProc(name, start=start, daemon=daemon, *args, **kwargs)
            proc = LazyProcs.add_proc(proc)
            return proc
            #return func(*args, **kwargs)
        return wrapped_proc
    return wrapper_proc

def lazymultiproc(dataset = None, dataset_callable = None, dataset_var: str = None, num_procs: int = 10):
    def wrapper_multiproc(func):
        def wrapped_parallelize(*args, **kwargs):
            if dataset_callable:
                yield from lazy_parallelize(func, processes=num_procs, result=dataset_callable(*args, **kwargs), *args, **kwargs)
            else:
                datavar = dataset or kwargs.get(dataset_var)
                if datavar:
                    yield from lazy_parallelize(func, processes=num_procs, result=dataset, *args, **kwargs)
            return func(*args, **kwargs)
        return wrapped_parallelize
    return wrapper_multiproc

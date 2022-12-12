
import math
import fileio
import collections
import platform
import multiprocessing as multiproc
import random
from functools import reduce
from itertools import chain, count, islice, takewhile

from typing import List, Optional, Dict

_CPU_CORES = multiproc.cpu_count()
_MAX_PROCS = math.ceil(_CPU_CORES * 1.5)
_MAX_THREADS = math.ceil(_CPU_CORES * 2)

try:
    _SERIALIZER = fileio.src._pickler
except:
    _SERIALIZER = fileio.core.libs.PICKLE_FUNC
    
_PROTOCOL = _SERIALIZER.HIGHEST_PROTOCOL



def is_primitive(val):
    """
    :param val: value to check
    :return: True if value is a primitive, else False
    """
    return isinstance(val, (str, bool, float, complex, bytes, int))


def is_namedtuple(val):
    """
    Use Duck Typing to check if val is a named tuple. Checks that val is of type tuple and contains
    the attribute _fields which is defined for named tuples.
    :param val: value to check type of
    :return: True if val is a namedtuple
    """
    val_type = type(val)
    bases = val_type.__bases__
    if len(bases) != 1 or bases[0] != tuple:
        return False
    fields = getattr(val_type, "_fields", None)
    return all(isinstance(n, str) for n in fields)


def identity(arg):
    """
    Function which returns the argument. Used as a default lambda function.
    :param arg: object to take identity of
    :return: return arg
    """
    return arg


def is_iterable(val):
    """
    Check if val is not a list, but is a collections.Iterable type. This is used to determine
    when list() should be called on val
    :param val: value to check
    :return: True if it is not a list, but is a collections.Iterable
    """
    if isinstance(val, list):
        return False
    return isinstance(val, collections.abc.Iterable)


def is_tabulatable(val):
    if is_primitive(val):
        return False
    if is_iterable(val) or is_namedtuple(val) or isinstance(val, list):
        return True
    return False


def split_every(parts, iterable):
    """
    Split an iterable into parts of length parts
    :param iterable: iterable to split
    :param parts: number of chunks
    :return: return the iterable split in parts
    """
    return takewhile(bool, (list(islice(iterable, parts)) for _ in count()))


def unpack(packed):
    """
    Unpack the function and args then apply the function to the arguments and return result
    :param packed: input packed tuple of (func, args)
    :return: result of applying packed function on packed args
    """
    func, args = _SERIALIZER.loads(packed)
    result = func(*args)
    if isinstance(result, collections.abc.Iterable):
        return list(result)
    return None


def pack(func, args):
    """
    Pack a function and the args it should be applied to
    :param func: Function to apply
    :param args: Args to evaluate with
    :return: Packed (func, args) tuple
    """
    return _SERIALIZER.dumps((func, args), _PROTOCOL)


def parallelize(func, result, processes=None, partition_size=None):
    """
    Creates an iterable which is lazily computed in parallel from applying func on result
    :param func: Function to apply
    :param result: Data to apply to
    :param processes: Number of processes to use in parallel
    :param partition_size: Size of partitions for each parallel process
    :return: Iterable of applying func on result
    """
    parallel_iter = lazy_parallelize(
        func, result, processes=processes, partition_size=partition_size
    )
    return chain.from_iterable(parallel_iter)


def lazy_parallelize(func, result, processes=None, partition_size=None):
    """
    Lazily computes an iterable in parallel, and returns them in pool chunks
    :param func: Function to apply
    :param result: Data to apply to
    :param processes: Number of processes to use in parallel
    :param partition_size: Size of partitions for each parallel process
    :return: Iterable of chunks where each chunk as func applied to it
    """
    if processes is None or processes < 1:
        processes = _MAX_PROCS
    else:
        processes = min(processes, _CPU_CORES)
    partition_size = partition_size or compute_partition_size(result, processes)
    pool = multiproc.Pool(processes=processes)
    partitions = split_every(partition_size, iter(result))
    packed_partitions = (pack(func, (partition,)) for partition in partitions)
    yield from pool.imap(unpack, packed_partitions)
    pool.terminate()


def compute_partition_size(result, processes):
    """
    Attempts to compute the partition size to evenly distribute work across processes. Defaults to
    1 if the length of result cannot be determined.
    :param result: Result to compute on
    :param processes: Number of processes to use
    :return: Best partition size
    """
    try:
        return max(math.ceil(len(result) / processes), 1)
    except TypeError:
        return 1


def compose(*functions):
    """
    Compose all the function arguments together
    :param functions: Functions to compose
    :return: Single composed function
    """
    return reduce(lambda f, g: lambda x: f(g(x)), functions, lambda x: x)

if __name__ == '__main__':
    if platform.system() == "Darwin":
        n = multiproc.get_context()
        print(n)
        multiproc.set_start_method('spawn')
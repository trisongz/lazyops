from __future__ import annotations

"""
Batching Helpers
"""

import itertools
import typing
from typing import Callable, Dict, Any, Tuple, TypeVar, Generic, Iterable, List, Generator, TYPE_CHECKING

ItemT = TypeVar('ItemT')

def get_batches_from_generator(iterable: typing.Iterable[ItemT], n: int) -> typing.Generator[List[ItemT], None, None]:
    """
    Batch elements of an iterable into fixed-length chunks or blocks.
    """
    it = iter(iterable)
    while x := tuple(itertools.islice(it, n)):
        yield x


def split_into_batches(items: List[ItemT], n: int) -> typing.Iterable[typing.List[ItemT]]:
    """
    Splits the items into n amount of equal items

    >>> list(split_into_batches(range(11), 3))
    [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10]]
    """
    n = min(n, len(items))
    k, m = divmod(len(items), n)
    return (items[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

def split_into_batches_of_n(iterable: typing.Iterable[ItemT], n: int) -> typing.Iterable[typing.List[ItemT]]:
    """
    Splits the items into fixed-length chunks or blocks.

    >>> list(split_into_batches_of_n(range(11), 3))
    [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10]]
    """
    return list(get_batches_from_generator(iterable, n))


def split_into_n_batches(iterable: typing.Iterable[ItemT], size: int) -> typing.Iterable[typing.List[ItemT]]:
    """
    Splits the items into n amount of equal items

    >>> list(split_into_batches_of_size(range(11), 3))
    [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10]]
    """
    return split_into_batches(iterable, size)


def build_batches(iterable: typing.Iterable[ItemT], size: int, fixed_batch_size: bool = True) -> typing.Iterable[typing.List[ItemT]]:
    """
    Builds batches of a given size from an iterable.
    """
    if fixed_batch_size:
        return split_into_batches_of_n(iterable, size)
    return split_into_n_batches(iterable, size)


def split_into_batches_with_index(iterable: typing.Iterable[ItemT], n: int, start: typing.Optional[int] = None) -> typing.Iterable[typing.Tuple[int, List[ItemT]]]:
    """
    Splits the items into fixed-length chunks or blocks.

    >>> list(split_into_batches_of_n(range(11), 3))
    [(0, [0, 1, 2]), (1, [3, 4, 5]), (2, [6, 7, 8]), (3, [9, 10])]
    """
    return list(enumerate(get_batches_from_generator(iterable, n), start = start or 0))

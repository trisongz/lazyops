from .base import BaseStatefulBackend
from .local import LocalStatefulBackend
from .redis import RedisStatefulBackend
from .objstore import ObjStorageStatefulBackend
from .sqlite import SqliteStatefulBackend

from typing import Union

StatefulBackendT = Union[ObjStorageStatefulBackend, LocalStatefulBackend, RedisStatefulBackend, SqliteStatefulBackend, BaseStatefulBackend]
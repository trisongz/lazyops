from .base import BaseStatefulBackend
from .local import LocalStatefulBackend
from .redis import RedisStatefulBackend

from typing import Union

StatefulBackendT = Union[LocalStatefulBackend, RedisStatefulBackend, BaseStatefulBackend]
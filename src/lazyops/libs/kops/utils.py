# Utilities

import dill
import random
import signal
import anyio
from aiocache import cached
from aiocache.serializers import PickleSerializer, BaseSerializer
from anyio.abc import CancelScope
from typing import List, Union, Callable, Any
from lazyops.utils.logs import logger

class InfiniteBackoffsWithJitter:
    def __iter__(self):
        while True:
            yield 10 + random.randint(-5, +5)

class DillSerializerObject(BaseSerializer):
    """
    Transform data to bytes using Dill.dumps and Dill.loads to retrieve it back.
    """

    DEFAULT_ENCODING = None
    PROTOCOL = dill.HIGHEST_PROTOCOL

    def dumps(self, value):
        """
        Serialize the received value using ``Dill.dumps``.

        :param value: obj
        :returns: bytes
        """
        return dill.dumps(value, protocol = self.PROTOCOL)

    def loads(self, value):
        """
        Deserialize value using ``Dill.loads``.

        :param value: bytes
        :returns: obj
        """
        return None if value is None else dill.loads(value)

DillSerializer: DillSerializerObject = DillSerializerObject()


"""
Utility Methods

- include signal handler to handle SIGINT
borrowed from: https://github.com/gexcom/pgsync-controller/blob/main/core/main.py
"""


class SignalHandler:

    _watch: List[signal.Signals] = [signal.SIGINT, signal.SIGTERM, signal.SIGKILL, signal.SIGSTOP, signal.SIGQUIT] # Handle SigInt, SigTerm, SigKill, SigStop, SigQuit
    _exit_funcs: List[Callable[[Any, Any], Any]] = []

    @classmethod
    async def monitor(cls, exit_funcs: List[Callable] = [], **kwargs):
        """
        Monitor SIGINT, SIGTERM, SIGKILL, SIGSTOP, SIGQUIT
        When received, call runs all exit_funcs and cls._exit_funcs

        Don't know what to do after this part though.
        """
        
        _stop_event = anyio.Event()
        interrupted = False
        interrupt_signal = None
        
        async def _signal_handler(scope: CancelScope) -> None:
            nonlocal interrupted
            nonlocal interrupt_signal
            with anyio.open_signal_receiver(*cls._watch) as signals:
                async for s in signals:
                    interrupted = True
                    interrupt_signal = s
                    _stop_event.set()
                    scope.cancel()
                    break

        CancelledError = anyio.get_cancelled_exc_class()

        while True:
            logger.info('Starting Signal Handler')
            async with anyio.create_task_group() as tg:
                tg.start_soon(_signal_handler, tg.cancel_scope)
                


    def __init__(self, sig_num, handler):
        self.sig_num = sig_num
        self.handler = handler

    def __enter__(self):
        self.old_handler = signal.getsignal(self.sig_num)
        signal.signal(self.sig_num, self.handler)

    def __exit__(self, *args):
        signal.signal(self.sig_num, self.old_handler)
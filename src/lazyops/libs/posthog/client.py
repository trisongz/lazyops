from __future__ import annotations

"""
The PostHog Client

- Uses niquest 
"""

# WARNING: This is a WIP and not yet fully tested.


import abc
import time
import asyncio
import functools
from lazyops.imports._niquests import resolve_niquests
resolve_niquests(True)

import niquests
from lazyops.libs.pooler import ThreadPooler
from lazyops.utils.logs import logger, null_logger, Logger
from lazyops.utils.times import Timer
from typing import Optional, Dict, Any, List, Union, Type, Set, Tuple, Callable, TypeVar, TYPE_CHECKING

from .config import PostHogSettings
from .utils import get_posthog_settings, register_posthog_client, get_posthog_client, has_existing_posthog_client
from .types import PostHogAuth, PostHogEndpoint, EventQueue, EventT

if TYPE_CHECKING:
    from .config import PostHogSettings



RT = TypeVar('RT')



class PostHogClient(abc.ABC):
    """
    An Asyncronous PostHog Client that utilizes Intelligent Batching and Asynchronous Task Queues
    to send events to PostHog in a more efficient and scalable manner.

    This client is designed with the following features in mind:
    - Intelligent Batching: The client automatically batches events based on the configured batch size and sends them in batches once the batch size is reached or the maximum batch interval has been reached.
    - Asynchronous Task Queues: The client uses asynchronous task queues to handle the sending of events. This allows the client to send events in parallel and improves the overall performance of the client.
    - Context Manager: The client provides a context manager that can be used to force sending of events immediately after exiting the context rather than waiting for the batching logic to complete.
    - Non-Blocking: By utilizing asynchronous task queues and non-blocking requests, the client can handle a large number of events without blocking the main thread.
    - Lazily Initializes: The client lazily initializes the PostHog client and only initializes it when the first event is added.
    """

    settings: Optional['PostHogSettings'] = None

    def __init__(
        self,
        endpoint: Optional[str] = None,
        enabled: Optional[bool] = None,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        client_timeout: Optional[float] = None,
        batch_size: Optional[int] = None, # If the total events is greater than this, it will dispatch the batch
        batch_interval: Optional[float] = None, # if the wait duration is greater than this, it will dispatch the batch
        debug_enabled: Optional[bool] = None,
        default_retries: Optional[int] = None,
        batched: Optional[bool] = None,
        num_workers: Optional[int] = None,
        upkeep_interval: Optional[float] = 0.1,
        dryrun: Optional[bool] = None,
        **kwargs
    ):
        """
        Initializes the PostHog Client

        - `endpoint`: The endpoint to use for the PostHog API
        - `enabled`: Whether the client is enabled or not
        - `api_key`: The API key to use for authentication
        - `project_id`: The project ID to use for the PostHog API
        - `client_timeout`: The timeout to use for the client
        - `batch_size`: The maximum number of events to batch before sending
        - `batch_interval`: The maximum time to wait before sending the batch
        - `debug_enabled`: Whether to enable debug logging
        - `default_retries`: The number of retries to attempt before giving up
        - `batched`: Whether to batch events before sending
        - `num_workers`: The number of workers to use for the event queue
        - `upkeep_interval`: The interval to check for events and send them
        - `dryrun`: Whether to run in dryrun mode. This will not actually send any events to PostHog

        These parameters will override the values in the PosthogSettings
        """
        # Reuse the existing client if it exists
        # which will prevent multiple clients from being created
        self.settings = get_posthog_settings()
        # if has_existing_posthog_client():
        #     self = get_posthog_client(
        #         endpoint = endpoint,
        #         enabled = enabled,
        #         api_key = api_key,
        #         project_id = project_id,
        #         client_timeout = client_timeout,
        #         batch_size = batch_size,
        #         batch_interval = batch_interval,
        #         debug_enabled = debug_enabled,
        #         default_retries = default_retries,
        #         batched = batched,
        #         num_workers = num_workers,
        #         **kwargs
        #     )
        #     return
        self.upkeep_interval = upkeep_interval or 0.1
        self.dryrun = dryrun
        self._kwargs = kwargs
        self.configure(
            endpoint = endpoint,
            enabled = enabled,
            api_key = api_key,
            project_id = project_id,
            client_timeout = client_timeout,
            batch_size = batch_size,
            batch_interval = batch_interval,
            debug_enabled = debug_enabled,
            default_retries = default_retries,
            batched = batched,
            num_workers = num_workers,
        )

        self.endpoint = PostHogEndpoint(endpoint = self.settings.endpoint)
        self.auth = PostHogAuth(api_key = self.settings.api_key)

        self.logger = logger if (self.settings.debug_enabled is None or self.settings.debug_enabled) else null_logger
        self.pooler = ThreadPooler

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._session: Optional['niquests.Session'] = None
        self._asession: Optional['niquests.AsyncSession'] = None

        self.main_task: Optional[asyncio.Task] = None
        self.event: Optional[asyncio.Event] = None
        self.started_time: Optional[Timer] = None
        self.event_queue: Optional[EventQueue] = None
        self.events_sent: Optional[int] = 0
        self.send_duration: Optional[float] = 0.0
        self.should_send_ctx: Optional[bool] = None

        self.successful_events: Optional[int] = 0
        self.failed_events: Optional[int] = 0

        self.tasks: Optional[Set[asyncio.Task]] = set()
        self._task_queue: Optional[asyncio.Queue] = None

        self._lock: Optional[asyncio.Lock] = None
        self._kwargs = kwargs
        register_posthog_client(self, **kwargs)


    def configure(
        self,
        endpoint: Optional[str] = None,
        enabled: Optional[bool] = None,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        client_timeout: Optional[float] = None,
        batch_size: Optional[int] = None, # If the total events is greater than this, it will dispatch the batch
        batch_interval: Optional[float] = None, # if the wait duration is greater than this, it will dispatch the batch
        debug_enabled: Optional[bool] = None,
        default_retries: Optional[int] = None,
        batched: Optional[bool] = None,
        num_workers: Optional[int] = None,
        upkeep_interval: Optional[float] = 0.1,
        dryrun: Optional[bool] = None,
        **kwargs
    ):
        """
        Configures the PostHog Client
        """
        if endpoint is not None: self.settings.endpoint = endpoint
        if enabled is not None: self.settings.enabled = enabled
        if api_key is not None: self.settings.api_key = api_key
        if project_id is not None: self.settings.project_id = project_id
        if client_timeout is not None: self.settings.client_timeout = client_timeout
        if batch_size is not None: self.settings.batch_size = batch_size
        if batch_interval is not None: self.settings.batch_interval = batch_interval
        if debug_enabled is not None: self.settings.debug_enabled = debug_enabled
        if batched is not None: self.settings.batched = batched
        if num_workers is not None: self.settings.num_workers = num_workers
        if default_retries is not None: self.settings.default_retries = default_retries
        if upkeep_interval is not None: self.upkeep_interval = upkeep_interval
        if dryrun is not None: self.dryrun = dryrun
        if kwargs: self._kwargs.update(kwargs)
        self.settings.update_enabled()
        return self

    @property
    def autologger(self) -> 'Logger':
        """
        Returns the autologger
        """
        return logger if self.settings.debug_enabled else null_logger

    @property
    def started(self) -> bool:
        """
        Returns True if the client is started
        """
        return self.main_task is not None
    
    @property
    def enabled(self) -> bool:
        """
        Returns True if the client is enabled
        """
        return self.settings._enabled
    
    def get_session_kwargs(self, **kwargs) -> Dict[str, Any]:
        """
        Returns the session kwargs
        """
        return {
            'pool_connections': self._kwargs.get('pool_connections', 10),
            'pool_maxsize': self._kwargs.get('pool_maxsize', 10),
            'retries': self._kwargs.get('retries', self.settings.default_retries),
            'resolver': self._kwargs.get('resolver', 'doh+cloudflare://'),
            'multiplexed': True,
            **kwargs,
        }


    @property
    def session(self) -> 'niquests.Session':
        """
        Returns the Session
        """
        if self._session is None: self._session = niquests.Session(**self.get_session_kwargs())
        return self._session
    
    @property
    def asession(self) -> 'niquests.AsyncSession':
        """
        Returns the Async Session
        """
        if self._asession is None: self._asession = niquests.AsyncSession(**self.get_session_kwargs())
        return self._asession
    
    @property
    def task_queue(self) -> asyncio.Queue:
        """
        Returns the Task Queue
        """
        if self._task_queue is None: self._task_queue = asyncio.Queue()
        return self._task_queue
    
    @property
    def lock(self) -> asyncio.Lock:
        """
        Returns the Lock
        """
        if self._lock is None: self._lock = asyncio.Lock()
        return self._lock

    def reset_session(self):
        """
        Resets the session
        """
        if self._session is not None: self._session.close()
        self._session = None
    
    async def areset_session(self):
        """
        Resets the async session
        """
        if self._asession is not None: await self._asession.close()
        self._asession = None
        if self._session is not None:  self._session.close()
        self._session = None

    def add_event(self, event: Union[EventT, str], **kwargs):
        """
        Adds the event to the queue

        - `event`: The event to add to the queue
        - `kwargs`: The kwargs to add to the event

        The event can be a string or a PostHog event object.
        """
        if not self.enabled: return
        if not self.started: self.start_task_queue()
        
        self.task_queue.put_nowait((event, kwargs))

    async def send_events(
        self, 
        force: Optional[bool] = None,
        batched: Optional[bool] = None,
    ) -> Tuple[List[niquests.Response], int]:  # sourcery skip: move-assign
        """
        Sends the events
        """
        if not self.event_queue: 
            self.autologger.info('Empty Queue. Skipping Send', colored = True)
            return None, None
        if self.lock.locked() and not force: 
            self.autologger.info('Locked. Skipping Send', colored = True)
            return None, None
        responses = []
        sent = 0 
        batched = batched if batched is not None else self.settings.batched
        async with self.lock:
            async with self.asession as s:
                req_func = functools.partial(s.post, timeout = self.settings.client_timeout, auth = self.auth, stream = True)
                base_json = {'api_key': self.settings.api_key}
                if self.event_queue.capture_events:
                    events = self.event_queue.prepare_events(kind = 'capture', batched = batched, exclude_none = True, clear_after = True)
                    sent += len(events)
                    if batched: 
                        if self.dryrun:
                            self.autologger.info(f'[DRYRUN] (Force: {force}, In Context: {self.should_send_ctx}) Capture Batched Event: {events} ', prefix = f'{self.endpoint.batch}', colored = True)
                        else: responses.append(await req_func(self.endpoint.batch, json = {'batch': events, **base_json}))
                    else:
                        for event in events:
                            if self.dryrun:
                                self.autologger.info(f'[DRYRUN] (Force: {force}, In Context: {self.should_send_ctx}) Capture Event: {event}', prefix = f'{self.endpoint.capture}', colored = True)
                                continue
                            responses.append(await req_func(self.endpoint.capture, json = {**event, **base_json}))
                    
                
                # TODO: add identify ?
                await s.gather(*responses)
            self.event_queue.clear()
        self.events_sent += sent
        self.should_send_ctx = False
        return responses, sent

    async def handle_event(self, event, **kwargs):
        """
        Handles the event
        """
        self.event_queue.add_event(event, **kwargs)
        self.autologger.info(f'Added Event: {len(self.event_queue)}/{self.settings.batch_size}', prefix = 'PostHog', colored = True)


    async def should_send_events(self, ts: Optional[float] = None, force: Optional[bool] = None, **kwargs) -> bool:
        """
        Checks if the events should be sent
        """
        if force: return True
        if self.should_send_ctx: return True
        if ts and (elapsed_s := (time.monotonic() - ts)) > self.settings.batch_interval: 
            self.autologger.info(f'Sending Batch: {len(self.event_queue)} @ {elapsed_s:.2f}s', prefix = 'Max Interval')
            return True

        if self.settings.batch_size is None: return False
        if len(self.event_queue) >= self.settings.batch_size:
            self.autologger.info(f'Sending Batch: {len(self.event_queue)}/{self.settings.batch_size} ', prefix = 'Max Size')
            return True
        return False

    async def handle_responses(self, batch: Tuple[List[niquests.Response], int], t: Timer, worker_n: int):
        """
        Handles the responses
        """
        responses, sent_events = batch
        if sent_events: self.send_duration += t.duration
        if not responses: return
        for response in responses:
            if response.status_code != 200:
                self.failed_events += 1
                self.autologger.info(f'[{response.status_code}] Error Sending Event: |y|{await response.text}|e|', prefix = f'PostHog Worker: {worker_n}', colored = True) 
            else: self.successful_events += 1

    async def upkeep(self, worker_n: Optional[int] = None):
        """
        This is a background task to handle upkeep
        """
        
        self.autologger.info('Upkeep Started', prefix = f'PostHog Worker: {worker_n}', colored = True)
        wt = Timer()
        ts = time.monotonic()
        while not self.event.is_set():
            try:
                item = self.task_queue.get_nowait()
                event, kwargs = item
                await self.handle_event(event, **kwargs)
                if await self.should_send_events(ts):
                    tt = Timer(format_ms = True, format_short = 2)
                    response_batch = await self.send_events()
                    await self.handle_responses(response_batch, tt, worker_n)
                    ts = time.monotonic()
                self.task_queue.task_done()

            except asyncio.QueueEmpty: await asyncio.sleep(self.upkeep_interval)
            except (Exception, asyncio.CancelledError) as e:
                if self.event.is_set(): 
                    self.autologger.info(f'Event Set. Exiting after {wt.total_s} Uptime', prefix = f'PostHog Worker: {worker_n}', colored = True)
                    return
                self.autologger.info(f'Error in Upkeep: |r|{e}|e|. Exiting after {wt.total_s} Uptime', prefix = f'PostHog Worker: {worker_n}', colored = True)
                return
            
            

    async def run_task_queue(self, num_workers: Optional[int] = None):
        """
        Runs the Task Queue
        """
        self.event = asyncio.Event()
        num_workers = num_workers or self.settings.num_workers
        try:
            for n in range(num_workers):
                self.tasks.add(asyncio.create_task(self.upkeep(n)))
            await self.event.wait()
        except Exception as e:
            logger.error(f'Error in PostHog Client: {e}')
        finally:
            await self.stop_task_queue()
            self.tasks.remove(self.main_task)
            self.main_task = None

    def get_stat_message(self) -> str:
        """
        Returns the stat message
        """
        m = f'Total Uptime: |g|{self.started_time.total_s}|e|. Events Sent: |g|{self.events_sent}|e|. Total Request Duration: |g|{self.started_time.pformat_duration(self.send_duration, short = 2, include_ms = True)}|e|.'
        if self.send_duration: m += f' Avg |g|{self.events_sent / self.send_duration:.2f} events/s|e|'
        return m


    async def stop_task_queue(self):
        """
        Stops the Task Queue
        """
        if self.main_task is None: return
        self.autologger.info('Stopping PostHog Event Queue')
        self.event.set()
        await self.send_events(force = True)
        all_tasks = list(self.tasks)
        self.tasks.clear()
        for task in all_tasks:
            if not task.done(): task.cancel()
        await self.areset_session()
        self.autologger.info(f'Event Queue Stopped. {self.get_stat_message()}', prefix = 'PostHog', colored = True)
        if self.main_task: self.main_task.cancel()
        await asyncio.gather(*all_tasks, return_exceptions=True)

    def start_task_queue(self, num_workers: Optional[int] = None):
        """
        Starts the Task Queue
        """
        if self.started: return
        if not self.enabled: 
            self.logger.warning('PostHog is not enabled. Please set `POSTHOG_API_KEY` to enable PostHog')
            return
        num_workers = num_workers or self.settings.num_workers
        self.autologger.info(f'Starting PostHog Event Queue with |g|{num_workers}|e| Workers', colored = True)
        self.started_time = Timer()
        self.event_queue = EventQueue()
        self.main_task = asyncio.create_task(self.run_task_queue(num_workers = num_workers))
        
    def __enter__(self):
        """
        Context Manager for the PostHog Client

        This is used to ensure that any events that are added during the context manager are sent immediately
        """
        self.start_task_queue()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context Manager for the PostHog Client
        """
        self.should_send_ctx = True
    
    async def __aenter__(self):
        """
        Async Context Manager for the PostHog Client

        This is used to ensure that any events that are added during the context manager are sent immediately
        """
        self.start_task_queue()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async Context Manager for the PostHog Client
        """
        self.should_send_ctx = True
    

    def capture(
        self,
        event: Optional[str] = None,
        distinct_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        **_kwargs: Any, 
    ) -> Callable[..., RT]:
        """
        Creates a decorator that can be used to capture events
        """
        def decorator(func: Callable[..., RT]) -> Callable[..., RT]:
            nonlocal event, distinct_id, properties
            if event is None: event = func.__name__
            properties = properties or {}
            ph_ctx = {'event': event, 'distinct_id': distinct_id, 'properties': properties, **_kwargs}

            if ThreadPooler.is_coro(func):
                @functools.wraps(func)
                async def capture_decorator(*args, **kwargs):
                    result = await func(*args, ph_ctx = ph_ctx, **kwargs)
                    self.add_event(**ph_ctx)
                    return result
            else:
                @functools.wraps(func)
                def capture_decorator(*args, **kwargs):
                    result = func(*args, ph_ctx = ph_ctx, **kwargs)
                    self.add_event(**ph_ctx)
                    return result
            return capture_decorator
        
        return decorator
            

    def flush(self, force: Optional[bool] = True) -> None:
        """
        Flushes the events
        """
        self.tasks.add(
            asyncio.create_task(self.send_events(force = force))
        )

    async def aflush(self, force: Optional[bool] = True) -> None:
        """
        Flushes the events
        """
        await self.send_events(force = force)
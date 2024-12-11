import asyncio
import dataclasses
import signal
import threading
import typing as t 
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast
from temporalio import workflow
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import (
    SandboxedWorkflowRunner,
    SandboxRestrictions,
)
from lzl.load import import_from_string, lazy_import
from lzl.pool import ThreadPool
from ..utils import logger


if TYPE_CHECKING:
    from lzl.ext.temporal.configs import TemporalWorkerConfig, TemporalSettings
    from lzl.ext.temporal.loop.config import WorkerConfig, RuntimeConfig
    # from temporalloop.config import Config, WorkerConfig

WorkerFactoryType = TypeVar(  # pylint: disable=invalid-name
    "WorkerFactoryType", bound="WorkerFactory"
)


HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

# We always want to pass through external modules to the sandbox that we know
# are safe for workflow use
with workflow.unsafe.imports_passed_through():
    # import are not used, but listed
    _ = import_from_string("pydantic:BaseModel")
    _ = import_from_string("lzl.ext.temporal.io._pydantic:pydantic_data_converter")
    _ = import_from_string("lzl.ext.temporal.io._pydantic_json:pydantic_data_converter")
    _ = import_from_string("lzl.ext.temporal.io._serialized:serialized_data_converter")
    # _ = import_from_string("temporalloop.converters.pydantic:pydantic_data_converter")


def new_sandbox_runner() -> SandboxedWorkflowRunner:
    # TODO(cretz): Use with_child_unrestricted when https://github.com/temporalio/sdk-python/issues/254
    # is fixed and released
    invalid_module_member_children = dict(
        SandboxRestrictions.invalid_module_members_default.children
    )
    del invalid_module_member_children["datetime"]
    return SandboxedWorkflowRunner(
        restrictions=dataclasses.replace(
            SandboxRestrictions.default,
            invalid_module_members=dataclasses.replace(
                SandboxRestrictions.invalid_module_members_default,
                children=invalid_module_member_children,
            ),
        )
    )


class WorkerFactory:
    """
    The Worker Factory
    """
    def __init__(self, config: "RuntimeConfig", settings: "TemporalSettings"):
        self.config = config
        self.settings = settings
        self.new_runtime = None


    async def client(self, config: "WorkerConfig"):
        # if self.config.metric_bind_address:
        #     self.new_runtime = Runtime(telemetry=TelemetryConfig(metrics=PrometheusConfig(bind_address=self.config.metric_bind_address)))

        kwargs: dict[str, Any] = {"namespace": config.namespace}
        if self.new_runtime is not None: kwargs["runtime"] = self.new_runtime
        elif self.config.telemetry:
            logger.info(f"Building Telemetry Runtime: {self.config.telemetry}", prefix = "Worker", colored = True)
            kwargs["runtime"] = self.settings.build_runtime(telemetry = self.config.telemetry)
        if config.converter is not None: kwargs["data_converter"] = config.converter
        return await self.settings.client_cls.connect(config.host, **kwargs)

    async def execute_preinit(self, fn: list[Callable[..., Any]]) -> None:
        for x in fn:
            if isinstance(x, str):
                x = lazy_import(x)
            logger.info(f"{x}", prefix = "Execute][Pre-init", colored = True)
            if ThreadPool.is_coro(x): await x()
            else: x()

    async def new_worker(self, worker_config: "WorkerConfig") -> Worker:
        """
        Creates a new worker
        """
        config = worker_config
        await self.execute_preinit(config.pre_init)
        config_dict = dict(
            name = config.name,
            queue = config.queue,
            identity = config.identity,
            workflows = config.workflows,
            activities = config.activities,
            max_concurrent_workflow_tasks = config.max_concurrent_workflow_tasks,
            max_concurrent_activities = config.max_concurrent_activities,
            # metric_bind_address = config.metric_bind_address,
        )
        display_config = {k:v for k,v in config_dict.items() if v is not None}
        if display_config.get('activities'):
            display_config['activities'] = [f'{f.__module__}.{f.__qualname__}' for f in display_config['activities']]
        # if display_config.get('workflows'):
        #     display_config['workflows'] = [f'{f.__qualname__}' for f in display_config['workflows']]
        
        
        client = await self.client(config)
        display_config['namespace'] = client.namespace
        logger.info(display_config, prefix = "Worker Start", colored = True)
        # Run a worker for the workflow
        return Worker(
            client,
            task_queue = config.queue,
            identity = config.identity,
            workflows = config.workflows,
            activities=config.activities,
            disable_eager_activity_execution = config.disable_eager_activity_execution,
            max_concurrent_workflow_tasks = config.max_concurrent_workflow_tasks,
            max_concurrent_activities = config.max_concurrent_activities,
            interceptors=[x() for x in config.interceptors],
            activity_executor=ThreadPoolExecutor(
                max(config.max_concurrent_activities + 1, 10)
            ),
            workflow_runner = new_sandbox_runner(),
            graceful_shutdown_timeout=timedelta(seconds=10),
        )


class Looper:
    """
    The Looper
    """
    _pre_init_hooks: t.List[t.Callable[..., t.Any] | str] = []
    _run_init_hooks: t.List[t.Callable[..., t.Any] | str] = []

    @classmethod
    def add_pre_hook(cls, fn: t.Callable[..., t.Any] | str, stage: t.Literal['pre_init', 'run_init'] = 'pre_init'):
        """
        Adds a pre-hook
        """
        if stage == 'pre_init': cls._pre_init_hooks.append(fn)
        elif stage == 'run_init': cls._run_init_hooks.append(fn)
            
    def __init__(
        self, 
        config: t.Optional["RuntimeConfig"] = None, 
        pre_init: t.Optional[t.List[t.Callable[..., t.Any] | str]] = None,
        settings: t.Optional["TemporalSettings"] = None,
        # queue: t.Optional[str] = None,
        # namespace: t.Optional[str] = None,
        **kwargs
    ):
        if pre_init: self.execute_preinit(pre_init)
        if self._pre_init_hooks: self.execute_preinit(self._pre_init_hooks)
        if settings is None:
            from lzl.ext.temporal.configs import get_temporal_settings
            settings = get_temporal_settings()
        self.settings = settings
        if not config: config = settings.get_runtime_config(**kwargs)
        self.config = config
        self.workers: list[Worker] = []
        self.should_exit = False

    async def stop(self) -> None:
        """
        Stops the looper
        """
        logger.info("Worker shutdown requested")
        group = [asyncio.wait_for(x.shutdown(), 3)  for x in self.workers]
        await asyncio.gather(*group)
        return None

    @classmethod
    def execute_preinit(cls, fn: t.List[t.Callable[..., t.Any] | str]) -> None:
        for x in fn:
            logger.info(f"{x}", prefix = "Looper Pre-init", colored = True)
            if isinstance(x, str): x = lazy_import(x)
            x()

    async def aexecute_prerun(self, fn: t.List[t.Callable[..., t.Any] | str]) -> None:
        for x in fn:
            logger.info(f"{x}", prefix = "Looper Run-init", colored = True)
            if isinstance(x, str): x = lazy_import(x)
            if ThreadPool.is_coro(x): await x()
            else: x()


    async def run(self, run_init: t.Optional[t.List[t.Callable[..., t.Any] | str]] = None):
        """
        Runs the looper
        """
        self.install_signal_handlers()
        if run_init: await self.aexecute_prerun(run_init)
        if self._run_init_hooks: await self.aexecute_prerun(self._run_init_hooks)
        if not self.config.loaded: self.config.load()
        # logger.info(f"Config loaded {self.config.workers[0].converter}")
        logger.info(f"Connecting |g|{len(self.config.workers)}|e| Workers", colored = True)
        self.workers = await self.prepare_workers()
        logger.info(f"Starting |g|{len(self.config.workers)}|e| Workers", colored = True)
        await asyncio.gather(*[x.run() for x in self.workers])

    async def prepare_workers(self) -> list[Worker]:
        """
        Prepares the workers

        - Creates the workers
        - Starts the workers
        """
        group = [
            worker_config.factory(self.config, self.settings).new_worker(
                worker_config
            )
            for worker_config in self.config.workers
        ]
        res: list[Worker] = cast(list[Worker], await asyncio.gather(*group))
        return res

    # Start client
    def install_signal_handlers(self) -> None:
        """Install signal handlers for the signals we want to handle."""
        if threading.current_thread() is not threading.main_thread():
            # Signals can only be listened to from the main thread.
            return
        for sig in HANDLED_SIGNALS:
            asyncio.get_running_loop().add_signal_handler(
                sig, self.handle_exit, sig, None
            )

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        """Handle exit signals by setting the interrupt event."""
        _ = frame
        if sig in (signal.SIGTERM, signal.SIGINT):
            logger.warning(f"Received signal {sig}: stopping the workers")
            raise SystemExit(0)
        else:
            logger.info(f"Received Signal {sig}: ignored")
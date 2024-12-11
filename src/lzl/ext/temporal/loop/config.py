from __future__ import annotations

import sys
import typing as t
from typing import Any, Callable, Optional, Sequence, Type, Union, cast
from temporalio.converter import DataConverter
from temporalio.worker import Interceptor
from lzl.load.utils import import_from_string, ImportFromStringError
from ..utils import logger
from .worker import WorkerFactory, WorkerFactoryType

if t.TYPE_CHECKING:
    from lzl.ext.temporal.configs import TemporalWorkerConfig
    from temporalio.runtime import TelemetryConfig

class WorkerConfig:
    def __init__(
        self,
        *,
        name: str,
        factory: Union[Type[WorkerFactoryType], str] = "",
        queue: str = "default-queue",
        host: str = "",
        namespace: str = "",
        identity: t.Optional[str] = None,
        activities: Sequence[Union[Callable[..., Any], str]] = None,
        workflows: Sequence[Union[Type[Any], str]] = None,
        interceptors: Sequence[Union[Type[Interceptor], str]] = None,
        converter: Union[DataConverter, str, None] = None,
        pre_init: Sequence[Union[Callable[..., Any], str]] = None,
        behavior: str = "merge",
        max_concurrent_workflow_tasks: int = 0,
        max_concurrent_activities: int = 0,
        # metric_bind_address: str  = "",
        debug_mode: bool = False,
        disable_eager_activity_execution: bool = True,
        **kwargs,
    ) -> None:
        """
        Initializes the Worker Config

            Args:
                name (str): The name of the worker
                queue (str): The task queue to use
                host (str): The host to use
                namespace (str): The namespace to use
                identity (str): The identity to use
                activities (Sequence[Union[Callable[..., Any], str]]): The activities to use
                workflows (Sequence[Union[Type[Any], str]]): The workflows to use
                interceptors (Sequence[Union[Type[Interceptor], str]]): The interceptors to use
                converter (Union[DataConverter, str, None]): The converter to use
                pre_init (Sequence[Union[Callable[..., Any], str]]): The pre-init functions to run
                behavior (str): The behavior to use
                max_concurrent_workflow_tasks (int): The maximum concurrent workflow tasks
                max_concurrent_activities (int): The maximum concurrent activities
                metric_bind_address (str): The address to bind the metrics server to
                debug_mode (bool): If true, the worker will run in debug mode
                disable_eager_activity_execution (bool): If true, the worker will not eagerly execute activities
        """
        self.name = name
        self.host: str = host
        self.namespace: str = namespace
        self.factory = WorkerFactory
        self.identity = identity

        self._factory = factory
        self._workflows = workflows
        self._activities = activities or []
        self._interceptors = interceptors or []
        self._converter = converter
        self._pre_init = pre_init or []

        self.pre_init: list[Callable[..., Any]] = []
        self.converter: Optional[DataConverter] = None
        self.queue = queue
        self.workflows: Sequence[Type[Any]] = []
        self.interceptors: Sequence[Type[Interceptor]] = []
        self.activities: Sequence[Callable[..., Any]] = []
        self.loaded = False
        self.behavior = behavior
        self.max_concurrent_workflow_tasks = max_concurrent_workflow_tasks
        self.max_concurrent_activities = max_concurrent_activities
        self.debug_mode = debug_mode
        self.disable_eager_activity_execution = disable_eager_activity_execution
        # self.metric_bind_address = metric_bind_address

    def _merge(self, config: "RuntimeConfig") -> None:
        """
        Config Merging
        """
        if not self.host: self.host = config.host
        if not self.namespace: self.namespace = config.namespace
        if not self.identity and config.identity: self.identity = config.identity
        if not self._factory: self._factory = config.factory
        if not self._converter: self._converter = config.converter
        if not self._interceptors: self._interceptors = config.interceptors
        if not self._pre_init: self._pre_init = config.pre_init
        if not self.max_concurrent_workflow_tasks:
            self.max_concurrent_workflow_tasks = config.max_concurrent_workflow_tasks
        if not self.max_concurrent_activities: self.max_concurrent_activities = config.max_concurrent_activities
        # if not self.metric_bind_address:
        #     self.metric_bind_address = config.metric_bind_address


    def load(self, global_config: Optional["RuntimeConfig"] = None) -> None:
        """
        Loads the config
        """
        assert not self.loaded
        if self.behavior == "merge" and global_config is not None:
            self._merge(global_config)

        self.activities = self._load_activities(self._activities)
        self.workflows = self._load_functions(self._workflows)
        self.interceptors = self._load_functions(self._interceptors)
        
        if isinstance(self._converter, str): self.converter = cast(DataConverter, self._load_function(self._converter))
        else: self.converter = self._converter
        
        self.factory = self._load_function(self._factory)
        self.pre_init = self._load_function(self._pre_init)
        self.loaded = True

    def _load_functions(self, functions: Sequence[Any]) -> Sequence[Any]:
        """
        Loads the functions
        """
        return [self._load_function(f) for f in functions]

    def _load_function(self, function: Any) -> Any:
        """
        Loads the function
        """
        if isinstance(function, str):
            try:
                function = import_from_string(function)
            except ImportFromStringError as e:
                logger.error(e)
                sys.exit(1)
        return function

    def _load_activities(self, activities: Sequence[Union[Callable[..., Any], str]]) -> Sequence[Callable[..., Any]]:
        """
        Loads the activities
        """
        acts = []
        act_classes: t.Dict[str, t.Any] = {}
        for act in activities:
            if not isinstance(act, str):
                acts.append(act)
                continue
            # This is a class 
            if act.count(':') > 1:
                cls_name, func_name = act.rsplit(':', 1)
                if cls_name not in act_classes:
                    new_cls = import_from_string(cls_name)
                    act_classes[cls_name] = new_cls()
                acts.append(getattr(act_classes[cls_name], func_name))
                continue
            # This is a function
            acts.append(self._load_function(act))
        return acts

class RuntimeConfig:
    """
    The Runtime Config
    """
    def __init__(
        self,
        host: str = "localhost:7233",
        namespace: str = "default",
        factory: Union[Type[WorkerFactoryType], str] = WorkerFactory,
        interceptors: Sequence[Union[Type[Interceptor], str]] | None = None,
        converter: Union[DataConverter, str, None] = None,
        use_colors: Optional[bool] = None,
        workers: Sequence[Union[WorkerConfig, 'TemporalWorkerConfig', t.Dict[str, t.Any]]] | None = None,
        identity: t.Optional[str] = None,
        max_concurrent_activities: int = 100,
        max_concurrent_workflow_tasks: int = 100,
        # metric_bind_address: str = "0.0.0.0:9000",
        telemetry: t.Optional[t.Optional['TelemetryConfig']] = None,
        limit_concurrency: t.Optional[int] = None,
        pre_init: t.Optional[t.List[str]] = None,

    ):
        self.host = host
        self.namespace: str = namespace
        self.factory = factory
        self.use_colors = use_colors
        self.limit_concurrency = limit_concurrency
        self.interceptors = interceptors or []
        self.identity = identity
        self._workers = workers or []
        self.pre_init = pre_init or []
        self.workers: t.List[WorkerConfig] = []
        self.converter = converter
        self.max_concurrent_activities = max_concurrent_activities
        self.max_concurrent_workflow_tasks = max_concurrent_workflow_tasks
        self.telemetry = telemetry
        self.loaded = False
        # self.metric_bind_address = metric_bind_address


    def load(self) -> None:
        """
        Loads the config
        """
        assert not self.loaded
        for worker in self._workers:
            if hasattr(worker, 'model_dump'):
                worker = worker.__dict__
            if isinstance(worker, dict):
                worker = WorkerConfig(**worker)
            if isinstance(worker, WorkerConfig):
                worker.load(self)
            self.workers.append(worker)
        self.loaded = True
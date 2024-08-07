from __future__ import annotations

"""
Base Hatchet Client with Modifications
"""

import asyncio
from functools import wraps
from hatchet_sdk.rate_limit import RateLimit
from hatchet_sdk.workflows_pb2 import CreateStepRateLimit
from hatchet_sdk.client import ClientImpl
from hatchet_sdk.loader import ClientConfig, ConfigLoader
from hatchet_sdk.hatchet import Hatchet as BaseHatchet
from hatchet_sdk.workflow import WorkflowMeta
from pflow.configs import PFlowSettings, settings
from lazyops.libs.logging import logger
from pflow.utils.lazy import get_pflow_settings
from lazyops.libs.proxyobj import ProxyObject
from kvdb.utils.cron import validate_cron_schedule
from .worker import Worker
from .context import Context
from .utils import new_client
from typing import Any, Dict, List, Optional, Union, Callable, TYPE_CHECKING, ParamSpec, Type, TypeVar
from types import ModuleType

if TYPE_CHECKING:
    from lazyops.utils.logs import Logger
    from pflow.types.component.workflow.base import WorkflowT
    

# https://github.com/hatchet-dev/hatchet-python-quickstart/blob/main/simple-examples/src/genai/basicrag.py


RT = TypeVar('RT')
P = ParamSpec("P")

class HatchetClient(BaseHatchet):
    client: ClientImpl
    name: str = 'hatchet'
    kind: str = 'client'

    def __init__(self, debug: bool = False, config: Union[ClientConfig, Dict[str, Any]] = None):
        # initialize a client
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.ensure_loop()
        self.client = new_client(config)
        self.has_namespace = self.client.config.namespace is not None
        self.settings: PFlowSettings = get_pflow_settings()
        if not debug: logger.disable("hatchet_sdk")
        self.workers: Dict[str, Worker] = {}
        self.registered_workflows: Dict[str, WorkflowT] = {}
        self.bound_workflows: Dict[str, WorkflowT] = {}
        self.compiled_workflows: Dict[str, Type['WorkflowT']] = {}
        
        self.post_init()
        self.finalize_init()

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        """
        Returns the event loop
        """
        if self._event_loop is None:
            from .spawn import get_event_loop
            self._event_loop = get_event_loop()
        return self._event_loop
    
    def ensure_loop(self):
        """
        Ensures the event loop
        """
        if self._event_loop is None:
            from .spawn import get_event_loop
            self._event_loop = get_event_loop()

    @property
    def logger(self) -> 'Logger':
        """
        Gets the logger
        """
        return self.settings.logger
    
    @property
    def autologger(self) -> 'Logger':
        """
        Gets the autologger
        """
        return self.settings.autologger

    def post_init(self):
        """
        Hook for post init
        """
        pass

    def finalize_init(self):
        """
        Finalize the init
        """
        pass

    def _get_workflow(self, parent: str, source: str) -> Type['WorkflowT']:
        """
        Gets the workflow
        """
        from pflow.utils.lazy import get_source_component
        return get_source_component(parent = parent, source = source, kind = 'workflow')

    def worker(self, name: str, max_runs: int | None = None) -> Worker:
        """
        Creates a new worker
        """
        if name in self.workers: return self.workers[name]
        # self.autologger.info(f'Creating Worker: {name}', prefix = '|g|Hatchet|e|', colored = True)
        worker = Worker(name=name, max_runs=max_runs, config=self.client.config)
        self.workers[name] = worker
        return worker

    def workflow(
        self,
        name: str = "",
        on_events: List[str] = [],
        on_crons: list = [],
        version: str = "",
        timeout: str = "60m",
        schedule_timeout: str = "5m",
    ) -> Callable[..., Type['WorkflowT']]:
        """
        Creates a new workflow
        """
        # self.autologger.info(f'Creating Workflow: {name}', prefix = 'Workflow', colored = True)

        def inner(cls: WorkflowT) -> WorkflowT:
            """
            Inner Workflow
            """
            if on_events:
                for n, event in enumerate(on_events):
                    if 'pflow' not in event: on_events[n] = f'pflow.{cls.parent}.{cls.source}:{event}'
            
            if on_crons:
                for n, cron in enumerate(on_crons):
                    on_crons[n] = validate_cron_schedule(cron)

            cls.on_events = on_events
            cls.on_crons = on_crons
            cls.name = name or f'pflow.{cls.parent}.{cls.source}.{cls.__name__}'
            cls.client = self.client
            cls.version = version or self.settings.application_version
            cls.timeout = timeout
            cls.schedule_timeout = schedule_timeout
            if getattr(cls, 'workflow_concurrency', None):
                cls.bind(self.concurrency(max_runs = cls.workflow_concurrency)(cls.concurrency))
            if hasattr(cls, 'register_workflow_steps'):
                cls.register_workflow_steps(self)
            return WorkflowMeta(cls.name, cls.__bases__, dict(cls.__dict__))
        
        return inner
    

    def step(
        self,
        name: str = "",
        timeout: str = "",
        parents: List[str] = [],
        retries: int = 0,
        rate_limits: List[RateLimit] | None = None,
        trigger_name: Optional[str] = None,
    ) -> Callable[P, RT]:
        
        # self.autologger.info(f'Creating Step: {name}', prefix = 'Step', colored = True)
        
        def inner(func: Callable[P, RT]) -> Callable[P, RT]:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if asyncio.iscoroutinefunction(func):
                    # from lazyops.libs.pooler import ThreadPooler
                    # return ThreadPooler.run(func, *args, **kwargs)
                    # return asyncio.run(func(*args, **kwargs))
                    return self.event_loop.run_until_complete(func(*args, **kwargs))
                else:
                    return func(*args, **kwargs)

            limits = None
            if rate_limits:
                limits = [
                    CreateStepRateLimit(key=rate_limit.key, units=rate_limit.units)
                    for rate_limit in rate_limits or []
                ]

            wrapper._step_name = name or func.__name__
            wrapper._step_parents = parents
            wrapper._step_timeout = timeout
            wrapper._step_retries = retries
            wrapper._step_rate_limits = limits
            wrapper._step_trigger_name = f'{trigger_name}:{wrapper._step_name}' if trigger_name else wrapper._step_name
            return wrapper

        return inner
    

    def bind_step(
        self,
        obj: 'WorkflowT',
        func: Callable[P, RT],
        name: str = "",
        timeout: str = "60m",
        parents: List[str] = [],
        retries: int = 0,
        rate_limits: List[RateLimit] | None = None,
    ):  # sourcery skip: default-mutable-arg
        """
        Binds a step to a workflow
        """
        obj.bind(
            self.step(
                name = name,
                timeout = timeout,
                parents = parents,
                retries = retries,
                rate_limits = rate_limits,
                trigger_name = obj.trigger_name,
            )(func)
        )



    def patch_workflow(
        self,
        obj: Type['WorkflowT'],
        name: str = "",
        on_events: List[str] = [],
        on_crons: list = [],
        version: str = "",
        timeout: str = "60m",
        schedule_timeout: str = "5m",
    ) -> Type['WorkflowT']:  # sourcery skip: default-mutable-arg
        """
        Binds the workflow component to the workflow
        """
        if obj._hatchet_patched: return obj
        if on_events:
            for n, event in enumerate(on_events):
                if obj.parent not in event: on_events[n] = f'{obj.parent}.{obj.source}:{event}'
                if not name: name = f'{obj.parent}.{obj.source}.{event}'
        else:
            on_events = [f'{obj.parent}.{obj.source}:{obj.op_name}']
            if not name: name = f'{obj.parent}.{obj.source}.{obj.op_name}'

        if on_crons:
            for n, cron in enumerate(on_crons):
                on_crons[n] = validate_cron_schedule(cron)

        obj.on_events = on_events
        obj.on_crons = on_crons
        obj.name = name or f'{obj.parent}.{obj.source}.{obj.__name__}'
        obj.trigger_name = f'{self.client.config.namespace}{obj.name}' if self.has_namespace else obj.name
        obj.client = self.client
        obj.version = version or self.settings.application_version
        obj.timeout = timeout
        obj.schedule_timeout = schedule_timeout
        if getattr(obj, 'workflow_concurrency', None) and not hasattr(obj.concurrency, '_concurrency_fn_name'):
            obj.bind(
                self.concurrency(
                    name = f'{obj.parent}.{obj.source}.{obj.op_name}:concurrency',
                    max_runs = obj.workflow_concurrency
                )(obj.concurrency))
        if hasattr(obj, 'register_workflow_steps'):
            obj.register_workflow_steps(self)
        obj._hatchet_patched = True
        self.registered_workflows[obj.name] = obj
        return obj


    def bind_workflow(
        self,
        obj: 'WorkflowT',
        name: str = "",
        on_events: List[str] = [],
        on_crons: list = [],
        version: str = "",
        timeout: str = "60m",
        schedule_timeout: str = "5m",
    ) -> Type['WorkflowT']:  # sourcery skip: default-mutable-arg
        """
        Binds the workflow component to the workflow
        """
        self.patch_workflow(
            obj = obj,
            name = name,
            on_events = on_events,
            on_crons = on_crons,
            version = version,
            timeout = timeout,
            schedule_timeout = schedule_timeout,
        )
        return WorkflowMeta(obj.name, obj.__bases__, dict(obj.__dict__))
        # self.registered_workflows[obj.name] = new_obj
        # return new_obj

    def chain_workflow(
        self,
        ref: 'WorkflowT',
        with_meta: Optional[bool] = True,
        with_links: Optional[bool] = True,
        **kwargs
    ) -> 'WorkflowT':
        """
        Chains the workflow
        """
        for lname, lcls in ref.linked_workflows.items():
            if lcls.name in self.bound_workflows: continue
            self.autologger.info(f'Chaining Workflow: [{lname}] {lcls.name} (With Meta: {with_meta}, With Links: {with_links})', colored = True, prefix = 'Workflow')
            l_wkflow_cls = WorkflowMeta(lcls.name, lcls.__bases__, dict(lcls.__dict__)) if with_meta else lcls
            l_wkflow: 'WorkflowT' = l_wkflow_cls()
            l_wkflow.on_start(hatchet = self, **kwargs)
            ref.linked_workflows[lname] = l_wkflow
            self.bound_workflows[lcls.name] = l_wkflow
            if lcls.linked_workflows and with_links:
                self.chain_workflow(lcls, with_meta = with_meta, with_links = with_links, **kwargs)
        return ref
    
    def gather_workflow(
        self,
        ref: 'WorkflowT',
        with_meta: Optional[bool] = True,
        with_links: Optional[bool] = True,
        **kwargs
    ) -> 'WorkflowT':
        """
        Gathers the workflow
        """
        if ref.name in self.bound_workflows: return ref
        ref_cls = WorkflowMeta(ref.name, ref.__bases__, dict(ref.__dict__)) if with_meta else ref
        wkflow: 'WorkflowT' = ref_cls()
        wkflow.on_start(hatchet = self, **kwargs)
        if ref.linked_workflows and with_links:
            self.chain_workflow(wkflow, with_meta = with_meta, with_links = with_links, **kwargs)
        self.bound_workflows[ref.name] = wkflow
        return wkflow

    def gather_workflows(
        self,
        workflow_names: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, 'WorkflowT']:
        """
        Gathers the workflows for the registered workflows
        """
        workflow_names = workflow_names or self.registered_workflows.keys()
        include = include or []
        exclude = exclude or []
        # workflows: List['WorkflowT'] = []
        for workflow_name in workflow_names:
            if workflow_name in self.registered_workflows and (
                not include or workflow_name in include
            ) and (
                not exclude or workflow_name not in exclude
            ):
                if workflow_name in self.bound_workflows: continue
                ref = self.registered_workflows[workflow_name]
                self.gather_workflow(ref, **kwargs)
        return self.bound_workflows
    
    def gather_workers(
        self,
        workflow_names: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Worker]:
        """
        Gathers the workers for the registered workflows
        """
        workflows = self.gather_workflows(workflow_names = workflow_names, include = include, exclude = exclude, **kwargs)
        workers: Dict[str, Worker] = {}
        for workflow_name, workflow in workflows.items():
            self.autologger.info(f'Gathering Worker: {workflow_name}: {workflow}', prefix = 'Workflow', colored = True)
            worker = self.worker(workflow_name)
            worker.register_workflow(workflow)
            workers[workflow_name] = worker
            self.workers[workflow_name] = worker
        return workers
    

    """
    Compile Method
    """

    def compile_workflow(
        self,
        ref: Type['WorkflowT'],
        **kwargs
    ) -> 'WorkflowT': 
        """
        Compiles the workflow
        """
        if ref.name in self.compiled_workflows: return ref
        ref = WorkflowMeta(ref.name, ref.__bases__, dict(ref.__dict__))()
        self.compiled_workflows[ref.name] = ref
        ref.on_start(hatchet = self, **kwargs)
        return ref
    
    def delete_all_workflows(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ):
        """
        Deletes all workflows
        """
        include = include or []
        exclude = exclude or []
        deleted = []
        workflows = self.client.rest.workflow_list()
        for workflow in workflows.rows:
            workflow_id = workflow.metadata.id
            workflow_name = workflow.name
            if (
                include
                and all(name not in workflow_name for name in include)
            ): continue
            if (
                exclude
                and any(name in workflow_name for name in exclude)
            ): continue
            if exclude and workflow_name in exclude: continue
            self.autologger.info(f'Deleting Workflow: {workflow_name}', prefix = workflow_id, colored = True)
            self.client.rest.workflow_api.workflow_delete(workflow_id)
            deleted.append(workflow_name)
        self.autologger.info(f'Deleted {len(deleted)}/{len(workflows.rows)} Workflows', colored = True)
        return deleted


Hatchet: HatchetClient = ProxyObject(obj_cls = HatchetClient) 

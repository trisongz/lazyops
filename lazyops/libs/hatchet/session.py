from __future__ import annotations

"""
Hatchet Session with Modifications
"""

import asyncio
from hatchet_sdk.rate_limit import RateLimit
from hatchet_sdk.client import ClientImpl

from hatchet_sdk.hatchet import Hatchet as BaseHatchet
from hatchet_sdk.clients.rest.models.workflow_runs_cancel_request import (
    WorkflowRunsCancelRequest,
)
from hatchet_sdk.clients.rest.models import WorkflowRunStatus
from hatchet_sdk.clients.run_event_listener import StepRunEventType
from lazyops.libs.logging import logger
from kvdb.utils.cron import validate_cron_schedule
from .utils import new_session, get_hatchet_settings, set_hatchet_settings, set_hatchet_client
from typing import Any, Dict, List, Optional, Union, Callable, TYPE_CHECKING, ParamSpec, Type, TypeVar, Tuple, overload

if TYPE_CHECKING:
    from lazyops.utils.logs import Logger
    from lazyops.libs.hatchet.config import HatchetSettings
    from hatchet_sdk.clients.rest.models import WorkflowRun
    from hatchet_sdk.loader import ClientConfig
    from .workflow import WorkflowT
    from .state import GlobalHatchetContext
    from .worker import Worker

    

RT = TypeVar('RT')
P = ParamSpec("P")

class HatchetSession(BaseHatchet):
    client: ClientImpl
    name: str = 'hatchet_session'
    kind: str = 'client'


    def __init__(
        self, 
        debug: bool = False, 
        config: Union['ClientConfig', Dict[str, Any]] = None,
        settings: Optional['HatchetSettings'] = None,
        instance: Optional[str] = 'default',
        namespace: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        grpc_endpoint: Optional[str] = None,
        **kwargs,
    ):
        """
        Initializes the Hatchet Session
        """
        ...

    def __init__(
        self, 
        debug: bool = True, 
        config: Union[ClientConfig, Dict[str, Any]] = None,
        settings: Optional['HatchetSettings'] = None,
        instance: Optional[str] = None,
        _ctx: Optional['GlobalHatchetContext'] = None,
        **kwargs,
    ):
        # We do not check whether the hatchet session is already initialized.
        # initialize the session
        if instance is None: instance = 'default'
        self.instance = instance
        if _ctx is None: 
            from .state import GlobalHatchetContext
            _ctx = GlobalHatchetContext
        self.c = _ctx
        if settings is None: settings = get_hatchet_settings()
        else: set_hatchet_settings(settings)

        self.settings = settings
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.ensure_loop()
        self.client = new_session(
            defaults = config, 
            settings = self.settings, 
            instance = self.instance, 
            **kwargs
        )
        self.has_namespace = self.client.config.namespace is not None
        # if not debug: logger.disable("hatchet_sdk")
        # else: self.settings.debug_enabled = True

        self.workers: Dict[str, 'Worker'] = {}
        self.registered_workflows: Dict[str, 'WorkflowT'] = {}
        self.bound_workflows: Dict[str, 'WorkflowT'] = {}
        self.compiled_workflows: Dict[str, Type['WorkflowT']] = {}
        
        self.post_init()
        self.finalize_init()
        # set_hatchet_client(self)

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

    
    def _get_workflow(self, op_name: str, version: Optional[str] = None) -> Type['WorkflowT']:
        """
        Gets the workflow
        """
        raise NotImplementedError
    

    def get_worker(self, name: str, max_runs: int | None = None) -> 'Worker':
        """
        Creates a new worker
        """
        if self.settings.in_k8s:
            name += f'-{self.settings.host_name[-1]}'
        if name in self.workers: return self.workers[name]
        if max_runs is None: max_runs = self.settings.workflow_concurrency_limit
        worker = self.c.worker_class(
            name=name, 
            max_runs=max_runs, 
            config = self.client.config,
            session = self,
            context_class = self.c.context_class,
        )
        self.workers[name] = worker
        return worker
    

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
                # trigger_name = obj.trigger_name,
                # obj = obj,
            )(func)
        )

    def bind_failure_step(
        self,
        obj: 'WorkflowT',
        func: Callable[P, RT],
        name: str = "",
        timeout: str = "",
        retries: int = 0,
        rate_limits: List[RateLimit] | None = None,
    ):
        """
        Binds a step to a workflow
        """
        obj.bind(
            self.on_failure_step(
                name = name,
                timeout = timeout,
                retries = retries,
                rate_limits = rate_limits,
            )(func)
        )

    def build_workflow(
        self,
        obj: Type['WorkflowT'],
        name: str = "",
        on_events: List[str] = [],
        on_crons: list = [],
        version: str = "",
        timeout: str = "60m",
        schedule_timeout: str = "15m",
    ) -> Type['WorkflowT']:  # sourcery skip: default-mutable-arg
        """
        Binds the workflow component to the workflow
        """
        if obj._hatchet_patched: return obj
        obj.workflow_name = obj.op_name
        if self.settings.include_instance_name_in_workflow:
            obj.workflow_name = f'{self.instance}.{obj.workflow_name}'
        
        if obj.version: obj.workflow_name += f'.{obj.version}'
        if on_events:
            for n, event in enumerate(on_events):
                if obj.workflow_name not in event: on_events[n] = f'{obj.workflow_name}:{event}'
        else:
            on_events = [obj.op_name]

        if on_crons:
            for n, cron in enumerate(on_crons):
                on_crons[n] = validate_cron_schedule(cron)

        obj.on_events = on_events
        obj.on_crons = on_crons
        obj.name = name or obj.workflow_name
        obj.trigger_name = f'{self.client.config.namespace}{obj.name}' if self.has_namespace else obj.name
        obj.client = self.client
        obj.version = version or self.settings.version
        obj.timeout = timeout
        obj.schedule_timeout = schedule_timeout
        if getattr(obj, 'workflow_concurrency', None) and not hasattr(obj.concurrency, '_concurrency_fn_name'):
            obj.bind(
                self.concurrency(
                    # name = f'{obj.op_name}:concurrency',
                    max_runs = obj.workflow_concurrency,
                    limit_strategy = obj.workflow_concurrency_strategy,
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
        schedule_timeout: str = "15m",
    ) -> Type['WorkflowT']:  # sourcery skip: default-mutable-arg
        """
        Binds the workflow component to the workflow
        """
        self.build_workflow(
            obj = obj,
            name = name,
            on_events = on_events,
            on_crons = on_crons,
            version = version,
            timeout = timeout,
            schedule_timeout = schedule_timeout,
        )
        return self.c.workflow_meta_class(obj.name, obj.__bases__, dict(obj.__dict__))


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
            l_wkflow_cls = self.c.workflow_meta_class(lcls.name, lcls.__bases__, dict(lcls.__dict__)) if with_meta else lcls
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
        ref_cls = self.c.workflow_meta_class(ref.name, ref.__bases__, dict(ref.__dict__)) if with_meta else ref
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
    ) -> Dict[str, 'Worker']:
        """
        Gathers the workers for the registered workflows
        """
        workflows = self.gather_workflows(workflow_names = workflow_names, include = include, exclude = exclude, **kwargs)
        workers: Dict[str, 'Worker'] = {}
        for workflow_name, workflow in workflows.items():
            self.autologger.info(f'Gathering Worker: {workflow_name}: {workflow}', prefix = f'Workflow ({self.instance})', colored = True)
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
        # self.autologger.info(f'Compiling Workflow: {ref.name}: {ref}', prefix = 'Workflow', colored = True)
        ref = self.c.workflow_meta_class(ref.name, ref.__bases__, dict(ref.__dict__))()
        ref.on_start(hatchet = self, **kwargs)
        self.compiled_workflows[ref.name] = ref
        return ref
    
    def compile_workflows(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        extra_workflows: Optional[Dict[str, 'WorkflowT']] = None,
        include_crontasks: Optional[bool] = None,
        only_crontasks: Optional[bool] = None,
        **kwargs
    ) -> Dict[str, 'WorkflowT']:
        """
        Compiles the workflows
        """
        all_workflows: Dict[str, 'WorkflowT'] = {}
        workflows: Dict[str, Type['WorkflowT']] = self.c.gather_workflows(include = include, exclude = exclude, only_crontasks = only_crontasks, include_crontasks = include_crontasks, **kwargs)
        if extra_workflows: workflows.update(extra_workflows)
        for workflow_name, wkflow in workflows.items():
            wkflow = wkflow.register(self)
            wkflow = self.compile_workflow(wkflow, **kwargs)
            all_workflows[workflow_name] = wkflow
        # Link them together
        for workflow_name in all_workflows:
            all_workflows[workflow_name].linked_workflows = all_workflows
        return all_workflows


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

    async def retrieve_workflow_run(
        self,
        request_id: str,
        blocking: bool = None,
        raise_error: Optional[bool] = False,
        **kwargs,
    ) -> Optional['WorkflowRun']:
        """
        Retrieves the workflow run
        """
        try:
            workflow_ref = self.client.rest.workflow_run_get(request_id)
        except Exception as e:
            if not raise_error: return None
            self.autologger.error(f"Error Retrieving Workflow Run {request_id}: {e}")
            raise e
        if blocking and workflow_ref.status in {
            WorkflowRunStatus.QUEUED,
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.PENDING,
        }:
            await self.client.admin.get_workflow_run(request_id).result()
            workflow_ref = self.client.rest.workflow_run_get(request_id)
        return workflow_ref
    
    async def determine_if_workflow_is_active(
        self,
        request_id: str,
        raise_error: Optional[bool] = False,
        **kwargs,
    ) -> bool:
        """
        Determines if the workflow is active
        """
        try:
            workflow_ref = self.client.rest.workflow_run_get(request_id)
        except Exception as e:
            if not raise_error: return False
            self.autologger.error(f"Error Retrieving Workflow Run {request_id}: {e}")
            raise e
        return workflow_ref.status in {
            WorkflowRunStatus.QUEUED,
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.PENDING,
        }

    async def abort_workflow_run(
        self,
        request_id: str,
        raise_error: Optional[bool] = False,
        **kwargs,
    ) -> Optional['WorkflowRun']:
        """
        Aborts the workflow run
        """
        try:
            workflow_ref = self.client.rest.workflow_run_get(request_id)
        except Exception as e:
            if not raise_error: return None
            self.autologger.error(f"Error Retrieving Workflow Run {request_id}: {e}")
            raise e
        try:
            cancel_request = WorkflowRunsCancelRequest(
                workflowRunIds = [workflow_ref.metadata.id],
            )
            resp = self.client.rest.workflow_run_api.workflow_run_cancel(
                tenant = self.client.config.tenant_id,
                workflow_runs_cancel_request = cancel_request
            )
            self.autologger.info(f"Canceled Workflow Run {request_id}: {resp}", colored = True)
            workflow_ref = self.client.rest.workflow_run_get(request_id)

        except Exception as e:
            self.autologger.error(f"Error Cancelling Workflow Run {request_id}: {e}")
            if raise_error: raise e
        return workflow_ref


    async def poll_workflow_run(
        self,
        request_id: str,
        **kwargs,
    ) -> Tuple[bool, Union[Dict[str, Any], Any], 'WorkflowRun']:
        """
        Polls the workflow run
        """
        workflow = self.client.admin.get_workflow_run(request_id)
        listener = workflow.stream()
        async for event in listener:
            if event.type == StepRunEventType.STEP_RUN_EVENT_TYPE_COMPLETED:
                return True, event.payload, self.client.rest.workflow_run_get(request_id)
            
            if event.type in [StepRunEventType.STEP_RUN_EVENT_TYPE_FAILED, StepRunEventType.STEP_RUN_EVENT_TYPE_CANCELLED]:
                return False, event.payload, self.client.rest.workflow_run_get(request_id)


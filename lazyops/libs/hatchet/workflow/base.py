from __future__ import annotations

"""
The Workflow Component - Base
"""

import os
import abc
import asyncio
import functools
import datetime
import contextlib
from lazyops.utils.times import Timer
from typing import Any, Dict, List, Optional, TypeVar, Callable, Union, Generic, Tuple, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from kvdb import PersistentDict, AsyncLock, KVDBSession
    from lazyops.libs.logging import Logger
    from lazyops.libs.hatchet.config import HatchetSettings, TemporaryData
    from lazyops.libs.hatchet.session import HatchetSession
    
    from lazyops.libs.hatchet.worker import Worker
    from lazyops.libs.hatchet.context import Context
    from .ctx import WorkflowContext
    from hatchet_sdk.loader import ClientConfig
    from hatchet_sdk.workflows_pb2 import ConcurrencyLimitStrategy

WorkflowT = TypeVar('WorkflowT', bound = 'BaseWorkflow')

"""
CreateWorkflowVersionOpts:
    name: str
    description: str
    version: str
    event_triggers: _containers.RepeatedScalarFieldContainer[str]
    cron_triggers: _containers.RepeatedScalarFieldContainer[str]
    scheduled_triggers: _containers.RepeatedCompositeFieldContainer[_timestamp_pb2.Timestamp]
    jobs: _containers.RepeatedCompositeFieldContainer[CreateWorkflowJobOpts]
    concurrency: WorkflowConcurrencyOpts
    schedule_timeout: str
    cron_input: str
    on_failure_job: CreateWorkflowJobOpts

"""

class BaseWorkflow:
    """
    Base class for all Workflows
    """
    op_name: Optional[str] = None
    version: Optional[str] = None
    instance: Optional[str] = None
    workflow_name: Optional[str] = None
    workflow_concurrency: Optional[int] = None
    workflow_concurrency_strategy: Optional[Union[str, 'ConcurrencyLimitStrategy']] = 'GROUP_ROUND_ROBIN'
    workflow_overrides: Optional[Dict[str, Any]] = None

    workflow_steps: Dict[str, Dict[str, Any]] = {}
    workflow_config: Dict[str, Any] = {}
    linked_workflows: Dict[str, 'WorkflowT'] = {}
    on_failure_steps: Dict[str, Dict[str, Any]] = {}

    enable_hooks: Optional[bool] = None
    is_crontask: Optional[bool] = None
    only_production_env: Optional[bool] = None
    is_disabled: Optional[bool] = None

    workflow_context_class: Optional[Union[Type['WorkflowContext'], str]] = None
    
    _hatchet_settings: Optional['HatchetSettings'] = None
    _clients: Dict[str, Any] = {}
    _hatchet_patched: bool = None
    _extra: Dict[str, Any] = {}

    # These are added as part of the workflow
    name: str = None
    on_events: Optional[List[str]] = None
    trigger_name: Optional[str] = None
    timeout: Optional[str] = None


    def timer(self, **kwargs) -> Timer:
        """
        Returns a timer
        """
        return Timer(**kwargs)

    def on_start(self, hatchet: Optional['HatchetSession'] = None, **kwargs):
        """
        Initializes the Workflow Component
        """
        if hatchet is not None: self.hatchet = hatchet
        self.configure_ctx(**kwargs)
        self.configure_init(**kwargs)
        self.configure_pre_init(**kwargs)
        self.configure_post_init(**kwargs)
        self.display_config(**kwargs)
        if self.name not in self.hatchet.bound_workflows: self.hatchet.bound_workflows[self.name] = self


    async def step_start_hook(self, context: 'Context', **kwargs):
        """
        Step Start Hook
        """
        pass
        # self.logger.info(f'Step Start Hook: {self.name}', prefix = self.workflow_name, colored = True)

    async def step_end_hook(self, context: 'Context', **kwargs):
        """
        Step End Hook
        """
        pass
        # self.logger.info(f'Step End Hook: {self.name}', prefix = self.workflow_name, colored = True)

    async def step_result_hook(
        self, 
        context: 'Context', 
        result: Optional[Any] = None, 
        error: Optional[Exception] = None,
        **kwargs
    ):
        """
        Step Result Hook
        """
        pass
        # self.logger.info(f'Step Result Hook: {self.name}', prefix = self.workflow_name, colored = True)

    
    @contextlib.asynccontextmanager
    async def step_hook_context(self, context: 'Context', **kwargs):
        """
        Step Hook Context
        """
        try:
            await self.step_start_hook(context, **kwargs)
            yield
        except Exception as e:
            self.logger.error(f"[{self.workflow_name}] Error in step hook: {e}")
            await self.step_end_hook(context, error = e, **kwargs)
            raise e
        finally:
            await self.step_end_hook(context, **kwargs)


    def wrap_step_with_hook(
        self,
        name: str,
    ):
        """
        Wraps the step with the hook
        """
        func = getattr(self, name)
        @functools.wraps(func)
        async def wrapped_func(*args, **kwargs):
            """
            Wrapped Function
            """
            async with self.step_hook_context(*args, **kwargs):
                result = await func(*args, **kwargs)
                await self.step_result_hook(*args, result = result, **kwargs)
                return result
        self.logger.info(f'Wrapped Step: {name}', prefix = self.workflow_name, colored = True)
        setattr(self.__class__, name, wrapped_func)


    @property
    def hatchet_settings(self) -> 'HatchetSettings':
        """
        Gets the Hatchet Settings
        """
        if not self._hatchet_settings:
            from lazyops.libs.hatchet.utils import get_hatchet_settings
            self._hatchet_settings = get_hatchet_settings()
        return self._hatchet_settings
    
    @property
    def logger(self) -> 'Logger':
        """
        Gets the logger
        """
        return self.hatchet_settings.logger
    
    @property
    def autologger(self) -> 'Logger':
        """
        Gets the autologger
        """
        return self.hatchet_settings.autologger
    
    @property
    def workflow_trigger(self) -> str:
        """
        Returns the workflow trigger name
        """
        if self.trigger_name: return self.trigger_name
        if self.on_events: return f'{self.hatchet_settings.app_env.short_name}.{self.on_events[0]}'
        if 'workflow_trigger' not in self._extra:
            self._extra['workflow_trigger'] = f'{self.hatchet_settings.app_env.short_name}.{self.workflow_name}'
        return self._extra['workflow_trigger']
    
    @property
    def has_cron_schedule(self) -> bool:
        """
        Checks if the workflow has a cron schedule
        """
        return bool(self.workflow_config.get('on_crons'))
    

    def get_next_cron_run(
        self,
        schedule: Optional[str] = None,
        verbose: Optional[bool] = None,
        colored: Optional[bool] = None,
        ctx: Optional['Context'] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns the next cron run
        """
        if not schedule:
            if not self.has_cron_schedule: return None
            schedule = self.workflow_config['on_crons'][0]
        
        import croniter
        log_hook = ctx.log if ctx else None
        utc_date = datetime.datetime.now(tz = datetime.timezone.utc)
        next_date: datetime.datetime = croniter.croniter(schedule, utc_date).get_next(datetime.datetime)
        total_seconds = (next_date - utc_date).total_seconds()
        next_interval, next_unit = total_seconds, "secs"
        # Reverse the order
        if next_interval > (60 * 60 * 24):
            next_interval /= (60 * 60 * 24)
            next_unit = "days"
        elif next_interval > (60 * 60):
            next_interval /= (60 * 60)
            next_unit = "hrs"
        elif next_interval > 60:
            next_interval /= 60
            next_unit = "mins"
        # msg = f'Next Scheduled Run is `{next_date}` ({next_interval:.2f} {next_unit})'
        if colored:
            msg = f'Next Scheduled Run in |g|{next_interval:.2f} {next_unit}|e| at |g|{next_date}|e|'
        else:
            msg = f'Next Scheduled Run in {next_interval:.2f} {next_unit} at {next_date}'
        if verbose: self.logger.info(f'Next Scheduled Run in |g|{next_interval:.2f} {next_unit}|e| at |g|{next_date}|e| ({self.workflow_name})', colored = True, hook = log_hook)
        return {
            'next_date': next_date,
            'next_interval': next_interval,
            'next_unit': next_unit,
            'total_seconds': total_seconds,
            'message': msg,
        }
        
    @classmethod
    def preconfigure_limits_from_env(cls, h: 'HatchetSession', **kwargs):
        """
        Preconfigures the limits from the environment
        """
        pass


    @classmethod
    def preconfigure_workflow(cls, h: 'HatchetSession', *args, **kwargs):
        """
        Preconfigures the workflow
        """
        cls.preconfigure_limits_from_env(h, **kwargs)
        cls.preconfigure_init(h, *args, **kwargs)
        cls.preconfigure_pre_init(h, *args, **kwargs)
        cls.preconfigure_post_init(h, *args, **kwargs)

    @classmethod
    def preconfigure_init(cls, h: 'HatchetSession', *args, **kwargs):
        """
        Preconfigures the init
        """
        pass

    @classmethod
    def preconfigure_pre_init(cls, h: 'HatchetSession', *args, **kwargs):
        """
        Preconfigures the pre init
        """
        pass

    @classmethod
    def preconfigure_post_init(cls, h: 'HatchetSession', *args, **kwargs):
        """
        Preconfigures the post init
        """
        pass

    def configure_ctx(self, *args, **kwargs):
        """
        Configure the Workerflow Context Component
        """
        if self.workflow_context_class:
            if isinstance(self.workflow_context_class, str):
                from lazyops.utils.lazy import lazy_import
                self.workflow_context_class = lazy_import(self.workflow_context_class)
            self.ctx = self.workflow_context_class(self, **kwargs)
        else:
            self.ctx = self.hatchet.c.workflow_context_class(self, **kwargs)

    def configure_event_loop(self, *args, **kwargs):
        """
        Configure the Event Loop
        """
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)


    def configure_init(self, *args, **kwargs):
        """
        Configure the Workerflow Component
        """
        pass
    
    def configure_wrapped_steps(self, *args, **kwargs):
        """
        Configure the Wrapped Steps
        """
        if self.enable_hooks:
            for name in self.workflow_steps:
                self.wrap_step_with_hook(name)

    def configure_pre_init(self, *args, **kwargs):
        """
        Configure the Workerflow Component
        """
        pass

    def configure_post_init(self, *args, **kwargs):
        """
        Post Configure the Workerflow Component
        """
        pass

    def display_config(self, **kwargs):  # sourcery skip: use-join
        """
        Displays the configuration
        """
        if self.tmp_data.has_logged(f'{self.workflow_name}:init'): return
        msg = ""
        for step, config in self.workflow_steps.items():
            msg += f"[{step}] Timeout: {config.get('timeout', 'N/A')} "
        # if self.timeout:
        #     msg += f', Timeout: |g|{self.timeout}|e|'
        msg = msg.lstrip(', ').strip()
        # msg += f' [|lc|{self.op_name}|e|]'
        if self.has_cron_schedule: 
            schedule = self.get_next_cron_run(verbose = False, colored = True)
            if schedule:
                msg += f' - {schedule["message"]}'
        self.logger.info(msg, colored = True, prefix = self.workflow_name)
        # self.logger.info(msg, colored = True)
        

    @property
    def kdb(self) -> 'KVDBSession':
        """
        Gets the KVDB Session with JSON Encoder
        """
        return self.ctx.kdb
    
    @property
    def rkdb(self) -> 'KVDBSession':
        """
        Gets the Raw KVDB Session with Decoder Enabled
        """
        return self.ctx.rkdb
    
    
    @property
    def tmp_data(self) -> 'TemporaryData':
        """
        Gets the temporary data
        """
        return self.ctx.tmp_data
    
    @property
    def hatchet(self) -> 'HatchetSession':
        """
        Gets the Hatchet Client
        """
        if 'hatchet' not in self._clients:
            from lazyops.libs.hatchet.utils import get_hatchet_client
            self._clients['hatchet'] = get_hatchet_client()
        return self._clients['hatchet']
    
    @hatchet.setter
    def hatchet(self, value: 'HatchetSession'):
        """
        Sets the Hatchet Session
        """
        self._clients['hatchet'] = value
        if not self.instance: self.instance = value.instance
    

    def _import_client(self, client_name: str, key: Optional[str] = None):
        """
        Imports a client
        """
        raise NotImplementedError

    def concurrency(self, context) -> str:
        """
        Returns the concurrency key
        """
        return f"{self.workflow_name}:concurrency"

    @classmethod
    def register_workflow_steps(cls, hatchet: 'HatchetSession'):
        """
        Registers the steps for the workflow
        """
        for step, config in cls.workflow_steps.items():
            hatchet.bind_step(cls, getattr(cls, step), name = step, **config)
        for step, config in cls.on_failure_steps.items():
            hatchet.bind_failure_step(cls, getattr(cls, step), name = step, **config)

    @classmethod
    def chain_workflow(
        cls: 'WorkflowT', 
        hatchet: 'HatchetSession', 
        worker: Optional['Worker'] = None,
        **kwargs,
    ) -> 'Worker':
        """
        Chain together the workflow
        """
        if not worker: worker = hatchet.worker(name = cls.workflow_name)
        for lname, lcls in cls.linked_workflows.items():
            lcls.preconfigure_workflow(hatchet, **kwargs)
            l_wkflow = hatchet.bind_workflow(lcls, **lcls.workflow_config)()
            cls.linked_workflows[lname] = l_wkflow
            l_wkflow.on_start(hatchet = hatchet, **kwargs)
            worker.register_workflow(l_wkflow)
            if lcls.linked_workflows:
                lcls.chain_workflow(hatchet, worker, **kwargs)
        return worker

    
    @classmethod
    def start(cls: 'WorkflowT', instance: Optional[str] = None, **kwargs):
        """
        Starts the Workflow
        """
        kwargs, hatchet = cls._init_hatchet_session(instance = instance, **kwargs)
        cls.preconfigure_workflow(hatchet, **kwargs)
        wkflow = hatchet.bind_workflow(cls, **cls.workflow_config)()
        wkflow.on_start(hatchet = hatchet, **kwargs)
        worker = hatchet.worker(name = wkflow.workflow_name)        
        worker.register_workflow(wkflow)
        if cls.linked_workflows:
            cls.chain_workflow(hatchet, worker)
        worker.start()


    @classmethod
    def bind(cls, func: Callable):
        """
        Binds the function to the workflow
        """
        setattr(cls, func.__name__, func)


    @classmethod
    def register_chain_workflow(cls: 'WorkflowT', hatchet: 'HatchetSession', **kwargs) -> 'WorkflowT':
        """
        Registers the chain workflow
        """
        for lname, lcls in cls.linked_workflows.items():
            lcls.preconfigure_workflow(hatchet, **kwargs)
            cls.linked_workflows[lname] = hatchet.build_workflow(lcls, **lcls.workflow_config)
            if lcls.linked_workflows:
                lcls.register_chain_workflow(hatchet, **kwargs)
        return cls

    @classmethod
    def register(
        cls: 'WorkflowT', 
        hatchet: Optional['HatchetSession'] = None, 
        instance: Optional[str] = None, 
        **kwargs
    ) -> 'WorkflowT':
        """
        Registers the workflow
        """
        if hatchet is None:
            kwargs, hatchet = cls._init_hatchet_session(instance = instance, **kwargs)
        cls.preconfigure_workflow(hatchet, **kwargs)
        hatchet.build_workflow(cls, **cls.workflow_config)
        if cls.linked_workflows:
            cls.register_chain_workflow(hatchet, **kwargs)
        return cls


    @classmethod
    def gather_workflow(
        cls: 'WorkflowT', 
        hatchet: Optional['HatchetSession'] = None, 
        instance: Optional[str] = None,
        with_meta: Optional[bool] = True,
        with_links: Optional[bool] = True,
        **kwargs
    ) -> 'WorkflowT':
        """
        Builds the workflow
        """
        if hatchet is None:
            kwargs, hatchet = cls._init_hatchet_session(instance = instance, **kwargs)
        cls.register(hatchet, **kwargs)
        return hatchet.gather_workflow(cls, with_meta = with_meta, with_links = with_links, **kwargs)

    @classmethod
    def aggregate_linked(
        cls: 'WorkflowT',
    ) -> Dict[str, 'WorkflowT']:
        """
        Aggregates the linked workflows
        """
        wkflows = {}
        for lname, lcls in cls.linked_workflows.items():
            wkflows[lcls.op_name] = lcls
            if lcls.linked_workflows:
                wkflows.update(lcls.aggregate_linked())
        return wkflows

    @classmethod
    def compile_workflows(
        cls: 'WorkflowT', 
        hatchet: Optional['HatchetSession'] = None, 
        instance: Optional[str] = None,
        **kwargs
    ) -> Dict[str, 'WorkflowT']:
        """
        Builds the workflow
        """
        if hatchet is None:
            kwargs, hatchet = cls._init_hatchet_session(instance = instance, **kwargs)
        cls.register(hatchet, **kwargs)
        return {
            cls.op_name: cls,
            **cls.aggregate_linked(),
        }
    
    @classmethod
    def retrieve_linked_op_names(
        cls: 'WorkflowT',
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        **kwargs,
    ) -> List[str]:
        """
        Retrieves the linked workflows
        """
        names = []
        include = include or []
        exclude = exclude or []
        for lname, lcls in cls.linked_workflows.items():
            if lcls.op_name in names: continue
            if lcls.op_name not in exclude and (lcls.op_name in include or not include) and lcls.workflow_steps: names.append(lcls.op_name)
            if lcls.linked_workflows:
                names.extend(lcls.retrieve_linked_op_names(include = include, exclude = exclude))
        return names


    @classmethod
    def gather_op_names(
        cls: 'WorkflowT',
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        **kwargs,
    ) -> List[str]:
        """
        Gathers the workflows
        """
        names = []
        include = include or []
        exclude = exclude or []
        if cls.op_name not in exclude and (cls.op_name in include or not include) and cls.workflow_steps: names.append(cls.op_name)
        if cls.linked_workflows:
            names.extend(cls.retrieve_linked_op_names(include = include, exclude = exclude))
        return list(set(names))


    @classmethod
    def _init_hatchet_session(
        cls, 
        config: Union['ClientConfig', Dict[str, Any]] = None,
        settings: Optional['HatchetSettings'] = None,
        instance: Optional[str] = None,
        namespace: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        grpc_endpoint: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Dict[str, Any], 'HatchetSession']:
        """
        Initializes a Hatchet Session
        """
        from lazyops.libs.hatchet.client import HatchetClient
        return kwargs, HatchetClient.get_session(
            config = config,
            settings = settings,
            instance = instance,
            namespace = namespace,
            api_endpoint = api_endpoint,
            grpc_endpoint = grpc_endpoint,
            **kwargs,
        )

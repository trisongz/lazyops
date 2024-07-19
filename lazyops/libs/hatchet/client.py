from __future__ import annotations

"""
Base Hatchet Client with Modifications
"""
import abc
import contextlib
from lazyops.libs.logging import logger
from lazyops.libs.proxyobj import proxied
from .utils import get_hatchet_settings, set_hatchet_settings
from typing import Any, Dict, List, Optional, Union, Iterator, Callable, TYPE_CHECKING, ParamSpec, Type, TypeVar, Tuple, overload

if TYPE_CHECKING:
    from lazyops.utils.logs import Logger
    from lazyops.libs.hatchet.config import HatchetSettings
    from .worker import Worker
    from .context import Context
    from .session import HatchetSession
    from .workflow import WorkflowT
    from .workflow.ctx import WorkflowContext

    from hatchet_sdk.loader import ClientConfig
    from hatchet_sdk.workflow import WorkflowMeta
    from hatchet_sdk.rate_limit import RateLimit
    from hatchet_sdk.clients.rest.models import WorkflowRun


ResponseT = TypeVar('ResponseT')

RT = TypeVar('RT')
P = ParamSpec("P")

@proxied
class HatchetClient(abc.ABC):
    """
    The Hatchet Client that proxies and manages multiple Hatchet Sessions
    """
    name: str = 'hatchet'
    kind: str = 'client'

    @overload
    def __init__(
        self,
        settings: Optional['HatchetSettings'] = None,
        grpc_endpoint: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        session_class: Optional[Union[Type['HatchetSession'], str]] = None,
        context_class: Optional[Union[Type['Context'], str]] = None,
        worker_class: Optional[Union[Type['Worker'], str]] = None,
        workflow_meta_class: Optional[Union[Type['WorkflowMeta'], str]] = None,
        workflow_context_class: Optional[Union[Type['WorkflowContext'], str]] = None,
        **kwargs,
    ):
        """
        Initializes the Hatchet Client
        """
        ...

    def __init__(
        self,
        settings: Optional['HatchetSettings'] = None,
        **kwargs,
    ):
        """
        Initializes the Hatchet Client
        """
        if settings is None: settings = get_hatchet_settings()
        else: set_hatchet_settings(settings)
        self.settings = settings
        from .state import GlobalHatchetContext
        self.c: GlobalHatchetContext = GlobalHatchetContext
        self.configure_classes(**kwargs)
        self.sessions = self.c.sessions
        self.settings.configure(**kwargs)

    def configure_classes(
        self,
        worker_class: Optional[Union[Type['Worker'], str]] = None,
        context_class: Optional[Union[Type['Context'], str]] = None,
        session_class: Optional[Union[Type['HatchetSession'], str]] = None,
        workflow_meta_class: Optional[Union[Type['WorkflowMeta'], str]] = None,
        workflow_context_class: Optional[Union[Type['WorkflowContext'], str]] = None,
        **kwargs,
    ):
        """
        Configures the global classes that are used to initialize the Hatchet Sessions
        """
        return self.c.configure_classes(
            worker_class = worker_class,
            context_class = context_class,
            session_class = session_class,
            workflow_meta_class = workflow_meta_class,
            workflow_context_class = workflow_context_class,
            **kwargs,
        )
        
    
    def register_workflow(
        self,
        workflow_name: Optional[str] = None,
        workflow_obj: Optional[Union[str, Type['WorkflowT']]] = None,
        workflow_mapping: Optional[Dict[str, Union[str, Type['WorkflowT']]]] = None,
        instance: Optional[str] = None,
        overwrite: Optional[bool] = None,
        **kwargs,
    ):
        """
        Registers workflows to the global context
        """
        return self.c.register_workflow(
            workflow_name = workflow_name,
            workflow_obj = workflow_obj,
            workflow_mapping = workflow_mapping,
            instance = instance,
            overwrite = overwrite,
            **kwargs,
        )
    
    def configure(
        self,
        overwrite: Optional[bool] = None,
        **kwargs,
    ):
        """
        Configures the global settings
        """
        self.settings.configure(**kwargs)
        if overwrite is True: self.init_session(overwrite = overwrite, **kwargs)

    @property
    def worker_class(self) -> Type['Worker']:
        """
        Returns the worker class
        """
        return self.c.worker_class
    
    @property
    def context_class(self) -> Type['Context']:
        """
        Returns the context class
        """
        return self.c.context_class
    
    @property
    def session_class(self) -> Type['HatchetSession']:
        """
        Returns the session class
        """
        return self.c.session_class
    
    @property
    def workflow_meta_class(self) -> Type['WorkflowMeta']:
        """
        Returns the workflow meta class
        """
        return self.c.workflow_meta_class

    """
    Session Management
    """

    def create_session(
        self,
        instance: Optional[str] = 'default',
        config: Union['ClientConfig', Dict[str, Any]] = None,
        settings: Optional['HatchetSettings'] = None,
        **kwargs,
    ) -> 'HatchetSession':
        """
        Returns a new Hatchet Session

        - Does not perform validation with the current contexts
        """
        settings = settings or self.settings
        return self.session_class(
            instance = instance,
            config = config,
            settings = settings,
            _ctx = self.c,
            **kwargs,
        )

    def session(
        self,
        instance: Optional[str] = 'default',
        config: Union['ClientConfig', Dict[str, Any]] = None,
        settings: Optional['HatchetSettings'] = None,
        set_as_ctx: Optional[bool] = None,
        overwrite: Optional[bool] = None,
        **kwargs,
    ) -> 'HatchetSession':
        """
        Initializes a Hatchet Session that is managed by the Hatchet Session Manager
        """
        if instance in self.sessions and overwrite is not True:
            if set_as_ctx is True: self.c.set_ctx(instance = instance)
            return self.sessions[instance]
    
        session = self.create_session(instance = instance, config = config, settings = settings, **kwargs)
        if set_as_ctx is None: set_as_ctx = not len(self.sessions)
        self.sessions[instance] = session
        if set_as_ctx is True: self.c.set_ctx(instance = instance)
        return session

    def init_session(
        self,
        instance: Optional[str] = 'default',
        config: Union['ClientConfig', Dict[str, Any]] = None,
        settings: Optional['HatchetSettings'] = None,
        set_as_ctx: Optional[bool] = None,
        overwrite: Optional[bool] = None,
        **kwargs,
    ) -> 'HatchetSession':
        """
        Initializes a Hatchet Session that is managed by the Hatchet Session Manager

        - Raises an error if the session already exists
        """
        if instance in self.sessions and overwrite is not True:
            raise ValueError(f'Session {instance} already exists. Set `overwrite` to True to overwrite')
        return self.session(instance = instance, config = config, settings = settings, set_as_ctx = set_as_ctx, **kwargs)
    
    def get_session(
        self,
        instance: Optional[str] = None,
        **kwargs,
    ) -> 'HatchetSession':
        """
        Returns the Hatchet Session with the given name
        """
        if instance is None: instance = self.c.current
        if instance is None: instance = 'default'
        if instance not in self.sessions:
            return self.session(instance = instance, **kwargs)
        return self.sessions[instance]


    def set_session(
        self,
        instance: str,
        **kwargs,
    ):
        """
        Set the current Hatchet Session
        """
        if instance not in self.sessions: raise ValueError(f'Invalid session instance: {instance}')
        self.c.set_ctx(instance = instance)    


    def add_session(
        self,
        session: 'HatchetSession',
        overwrite: Optional[bool] = None,
        set_as_ctx: Optional[bool] = None,
        **kwargs,
    ):
        """
        Adds a Hatchet Session to the Hatchet Session Manager
        """
        if not isinstance(session, self.session_class): raise ValueError(f'Invalid session type: {type(session)}')
        if session.instance in self.sessions and overwrite is not True:
            raise ValueError(f'The session with instance {session.instance} already exists. Use overwrite = True to overwrite the session')
        if set_as_ctx is None: set_as_ctx = not len(self.sessions)
        self.sessions[session.instance] = session
        if set_as_ctx is True: self.c.set_ctx(instance = session.instance)

    """
    Properties
    """

    @property
    def ctx(self) -> 'HatchetSession':
        """
        Returns the current session
        """
        if not self.c.ctx:
            self.session()
        return self.c.ctx
    
    @property
    def current(self) -> Optional[str]:
        """
        Returns the current session
        """
        return self.c.current or 'default'
    
    @contextlib.contextmanager
    def with_session(self, instance: str) -> Iterator['HatchetSession']:
        """
        Returns the session with the given name as the current session
        """
        if instance not in self.sessions: 
            raise ValueError(f'Invalid session instance: `{instance}`. Initialize the session first using `session` or `init_session`')
        yield self.sessions[instance]

    """
    Session Wrap Methods
    """
    def _session_function(self, *args, _function: Optional[str] = None, session_ctx: Optional[str] = None, **kwargs) -> Union[ResponseT, Awaitable[ResponseT]]:
        """
        Wraps the session function
        """
        if session_ctx is None: session_ctx = self.current
        with self.with_session(session_ctx) as session:
            return getattr(session, _function)(*args, **kwargs)
    
    """
    Misc Properties
    """

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
    
    """
    Passthrough Methods
    """


    def _get_workflow(self, op_name: str, version: Optional[str] = None) -> Type['WorkflowT']:
        """
        Gets the workflow
        """
        return self.ctx._get_workflow(op_name = op_name, version = version)


    def get_worker(self, name: str, max_runs: int | None = None) -> Worker:
        """
        Creates a new worker
        """
        return self.ctx.get_worker(name = name, max_runs = max_runs)
    

    def bind_step(
        self,
        obj: 'WorkflowT',
        func: Callable[P, RT],
        name: str = "",
        timeout: str = "60m",
        parents: List[str] = [],
        retries: int = 0,
        rate_limits: List['RateLimit'] | None = None,
    ):  # sourcery skip: default-mutable-arg
        """
        Binds a step to a workflow
        """
        return self.ctx.bind_step(
            obj = obj,
            func = func,
            name = name,
            timeout = timeout,
            parents = parents,
            retries = retries,
            rate_limits = rate_limits,
        )

    def bind_failure_step(
        self,
        obj: 'WorkflowT',
        func: Callable[P, RT],
        name: str = "",
        timeout: str = "",
        retries: int = 0,
        rate_limits: List['RateLimit'] | None = None,
    ):
        """
        Binds a step to a workflow
        """
        return self.ctx.bind_failure_step(
            obj = obj,
            func = func,
            name = name,
            timeout = timeout,
            retries = retries,
            rate_limits = rate_limits,
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
        return self.ctx.build_workflow(
            obj = obj,
            name = name,
            on_events = on_events,
            on_crons = on_crons,
            version = version,
            timeout = timeout,
            schedule_timeout = schedule_timeout,
        )


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
        return self.ctx.bind_workflow(
            obj = obj,
            name = name,
            on_events = on_events,
            on_crons = on_crons,
            version = version,
            timeout = timeout,
            schedule_timeout = schedule_timeout,
        )


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
        return self.ctx.chain_workflow(ref = ref, with_meta = with_meta, with_links = with_links, **kwargs)
    
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
        return self.ctx.gather_workflow(ref = ref, with_meta = with_meta, with_links = with_links, **kwargs)

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
        return self.ctx.gather_workflows(workflow_names = workflow_names, include = include, exclude = exclude, **kwargs)
    
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
        return self.ctx.gather_workers(workflow_names = workflow_names, include = include, exclude = exclude, **kwargs)
    

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
        return self.ctx.compile_workflow(ref = ref, **kwargs)
    
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
        return self.ctx.compile_workflows(include = include, exclude = exclude, extra_workflows = extra_workflows, include_crontasks = include_crontasks, only_crontasks = only_crontasks, **kwargs)


    def delete_all_workflows(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ):
        """
        Deletes all workflows
        """
        return self.ctx.delete_all_workflows(include = include, exclude = exclude)

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
        return await self.ctx.retrieve_workflow_run(request_id = request_id, blocking = blocking, raise_error = raise_error, **kwargs)
    
    async def determine_if_workflow_is_active(
        self,
        request_id: str,
        raise_error: Optional[bool] = False,
        **kwargs,
    ) -> bool:
        """
        Determines if the workflow is active
        """
        return await self.ctx.determine_if_workflow_is_active(request_id = request_id, raise_error = raise_error, **kwargs)

    async def abort_workflow_run(
        self,
        request_id: str,
        raise_error: Optional[bool] = False,
        **kwargs,
    ) -> Optional['WorkflowRun']:
        """
        Aborts the workflow run
        """
        return await self.ctx.abort_workflow_run(request_id = request_id, raise_error = raise_error, **kwargs)


    async def poll_workflow_run(
        self,
        request_id: str,
        **kwargs,
    ) -> Tuple[bool, Union[Dict[str, Any], Any], 'WorkflowRun']:
        """
        Polls the workflow run
        """
        return await self.ctx.poll_workflow_run(request_id = request_id, **kwargs)
    



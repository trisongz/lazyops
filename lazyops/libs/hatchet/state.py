from __future__ import annotations

"""
Manages the Hatchet State
"""
import abc
from lazyops.libs.proxyobj import proxied
from lazyops.utils import lazy_import
from typing import Optional, Dict, Any, List, Union, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import HatchetClient
    from .session import HatchetSession
    from .worker import Worker
    from .context import Context
    from .workflow.ctx import WorkflowContext
    from .workflow import WorkflowT
    from hatchet_sdk.workflow import WorkflowMeta

    HatchetObjClasses = Type[Union[
        HatchetSession,
        Context,
        Worker,
        WorkflowMeta,
    ]]



@proxied
class GlobalHatchetContext(abc.ABC):
    """
    The Hatchet Context for the Global Hatchet Instance
    """

    ctx: Optional['HatchetSession'] = None
    sessions: Dict[str, 'HatchetSession'] = {}
    classes: Dict[str, 'HatchetObjClasses'] = {}
    workflows: Dict[str, Dict[str, Union[str, 'WorkflowT']]] = {}

    def set_ctx(
        self,
        instance: Optional[str] = None,
        session: Optional['HatchetSession'] = None,
    ):
        """
        Sets the context
        """
        if not instance and not session: raise ValueError('Either instance or session must be provided')
        if instance:
            if instance not in self.sessions: raise ValueError(f'Invalid session instance: {instance}')
            session = self.sessions[instance]
        self.ctx = session

    @property
    def current(self) -> Optional[str]:
        """
        Returns the current session
        """
        return self.ctx.instance if self.ctx else None
    
    @property
    def worker_class(self) -> Type['Worker']:
        """
        Returns the worker class
        """
        return self.classes.get('worker')
    
    @worker_class.setter
    def worker_class(self, value: Type['Worker']):
        """
        Sets the worker class
        """
        self.classes['worker'] = value

    @property
    def context_class(self) -> Type['Context']:
        """
        Returns the context class
        """
        return self.classes.get('context')
    
    @context_class.setter
    def context_class(self, value: Type['Context']):
        """
        Sets the context class
        """
        self.classes['context'] = value

    @property
    def workflow_context_class(self) -> Type['WorkflowContext']:
        """
        Returns the workflow context class
        """
        return self.classes.get('workflow_context')
    
    @workflow_context_class.setter
    def workflow_context_class(self, value: Type['WorkflowContext']):
        """
        Sets the workflow context class
        """
        self.classes['workflow_context'] = value


    @property
    def session_class(self) -> Type['HatchetSession']:
        """
        Returns the session class
        """
        return self.classes.get('session')
    
    @session_class.setter
    def session_class(self, value: Type['HatchetSession']):
        """
        Sets the session class
        """
        self.classes['session'] = value

    @property
    def workflow_meta_class(self) -> Type['WorkflowMeta']:
        """
        Returns the workflow meta class
        """
        return self.classes.get('workflow_meta')
    
    @workflow_meta_class.setter
    def workflow_meta_class(self, value: Type['WorkflowMeta']):
        """
        Sets the workflow meta class
        """
        self.classes['workflow_meta'] = value


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
        from lazyops.utils import lazy_import
        if context_class:
            if isinstance(context_class, str): context_class = lazy_import(context_class)
            self.context_class = context_class
        elif self.context_class is None:
            from .context import Context
            self.context_class = Context
        if session_class:
            if isinstance(session_class, str): session_class = lazy_import(session_class)
            self.session_class = session_class
        elif self.session_class is None:
            from .session import HatchetSession
            self.session_class = HatchetSession
        if worker_class:
            if isinstance(worker_class, str): worker_class = lazy_import(worker_class)
            self.worker_class = worker_class
        elif self.worker_class is None:
            from .worker import Worker
            self.worker_class = Worker
        if workflow_meta_class:
            if isinstance(workflow_meta_class, str): workflow_meta_class = lazy_import(workflow_meta_class)
            self.workflow_meta_class = workflow_meta_class
        elif self.workflow_meta_class is None:
            from hatchet_sdk.workflow import WorkflowMeta
            self.workflow_meta_class = WorkflowMeta
        if workflow_context_class:
            if isinstance(workflow_context_class, str): workflow_context_class = lazy_import(workflow_context_class)
            self.workflow_context_class = workflow_context_class
        elif self.workflow_context_class is None:
            from .workflow.ctx import WorkflowContext
            self.workflow_context_class = WorkflowContext

    def get_workflow(
        self,
        name: str,
        version: Optional[str] = None,
        instance: Optional[str] = None,
    ) -> 'WorkflowT':
        """
        Gets the workflow
        """
        if not instance: instance = self.current or 'default'
        if version: name += f'.{version}'
        if name not in self.workflows.get(instance, {}):
            raise KeyError(f"Invalid Workflow Name: ({instance}) {name} as it is not registered or an importable name")
        if isinstance(self.workflows[instance][name], str):
            self.workflows[instance][name] = lazy_import(self.workflows[instance][name])
        return self.workflows[instance][name]

    def register_workflow(
        self,
        workflow_name: Optional[str] = None,
        workflow_obj: Optional[Union[str, Type['WorkflowT']]] = None,
        workflow_mapping: Optional[Dict[str, Union[str, Type['WorkflowT']]]] = None,
        instance: Optional[str] = None,
        overwrite: Optional[bool] = None,
    ):
        """
        Registers workflows to the global context
        """
        if not instance: instance = self.current or 'default'
        if instance not in self.workflows: self.workflows[instance] = {}
        if workflow_obj:
            if not workflow_name: 
                workflow_name = workflow_obj if isinstance(workflow_obj, str) else workflow_obj.__name__
            if workflow_name in self.workflows[instance] and not overwrite:
                raise ValueError(f"Workflow {workflow_name} already registered for instance {instance}")
            self.workflows[instance][workflow_name] = workflow_obj
        elif workflow_mapping:
            self.workflows[instance].update(workflow_mapping)
        


    def _workflow_register(
        self,
        workflow: 'WorkflowT',
        instance: Optional[str] = None,
    ):
        """
        Registers the workflow

        - this is a private method that is used to register a workflow
        """
        if not instance: instance = self.current or 'default'
        if instance not in self.workflows: self.workflows[instance] = {}
        self.workflows[instance][workflow.workflow_name] = workflow

        
    def gather_workflows(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        include_crontasks: Optional[bool] = None,
        only_crontasks: Optional[bool] = None,
        instance: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Type['WorkflowT']]:
        """
        Gathers the workflows
        """
        if not instance: instance = self.current or 'default'
        workflows: Dict[str, 'WorkflowT'] = {}
        include = include or []
        exclude = exclude or []
        if only_crontasks and not include_crontasks: include_crontasks = True
        workflow_items = self.workflows.get(instance, {})
        for workflow_name, ref in workflow_items.items():
            if include and workflow_name not in include: continue
            if exclude and workflow_name in exclude: continue
            wf_ref = self.get_workflow(workflow_name, instance = instance)
            if not include_crontasks and wf_ref.is_crontask: continue
            if only_crontasks and not wf_ref.is_crontask: continue
            workflows[workflow_name] = wf_ref
        return workflows

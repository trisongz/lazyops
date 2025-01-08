from __future__ import annotations

"""
Temporal Workflow Mixins: Dispatch
"""

import typing as t
from lzl.types import eproperty

from .base import BaseTemporalMixin, MixinKinds

if t.TYPE_CHECKING:
    from temporalio.types import ParamType, ReturnType, SelfType
    from lzl.ext.temporal.patches import WorkflowHandle
    # from temporalio.client import WorkflowHandle


ParamT = t.TypeVar('ParamT')
ReturnT = t.TypeVar('ReturnT')

class TemporalDispatchMixin(BaseTemporalMixin, t.Generic[ParamT, ReturnT]):
    """
    [Temporal] Dispatch Mixin that will automatically registered
    """

    workflow_name: t.Optional[str] = None
    mixin_kind: t.Optional[MixinKinds] = 'dispatch'
    _is_subclass_: t.Optional[bool] = True

    input_type: t.Optional[t.Type[ParamT] | str] = None
    result_type: t.Optional[t.Type[ReturnT] | str] = None

    # task_queue: t.Optional[str] = 'default'

    @eproperty
    def workflow_func_name(self) -> str:
        """
        Returns the workflow function name
        `task.function` -> `task_function`
        """
        return self.workflow_name.replace('.', '_').replace('-', '_')
            
    
    async def _precall_hook_(self, *args, **kwargs):
        """
        Runs the dispatch hook
        """
        if self.client is None: 
            self.client = await self.registry.get_client(namespace = self.namespace)
        if not hasattr(self, 'client_func_kws'):
            self.client_func_kws = {
                'execute_workflow': list(
                    self.client.execute_workflow.__code__.co_varnames
                ),
                'start_workflow': list(
                    self.client.start_workflow.__code__.co_varnames
                ),
                'create_schedule': list(
                    self.client.create_schedule.__code__.co_varnames
                ),
            }

    def _extract_func_kwargs_(self, func: str, kwargs: t.Dict[str, t.Any]) -> t.Tuple[t.Dict[str, t.Any], t.Dict[str, t.Any]]:
        """
        Extracts the function kwargs
        """
        func_kws = self.client_func_kws[func]
        return {
            k: v for k, v in kwargs.items() if k not in func_kws
        }, {
            k: v for k, v in kwargs.items() if k in func_kws
        }
        
    async def _validate_input_(self, param: 'ParamT', kwargs: t.Dict[str, t.Any]) -> 'ParamT':
        """
        Validates the input

        - if Arguments are provided, it will return the first argument
        - if no arguments are provided, it will return the kwargs
        """
        p = param[0] if param else kwargs
        return self.input_type(**p) if isinstance(p, dict) and self.input_type else p

    async def _validate_output_(self, result: 'ReturnType') -> 'ReturnType':
        """
        Validates the output
        """
        if isinstance(result, dict) and self.result_type:
            return self.result_type(**result)
        return result
    
    async def _finalize_params_(self, params: 'ParamT', id: str, kwargs: t.Dict[str, t.Any]) -> 'ParamT':
        """
        Finalizes the params
        """
        return params
    
    async def _execute_(
        self, 
        *param: 'ParamT',
        id: t.Optional[str] = None,
        task_queue: t.Optional[str] = None,
        workflow: t.Optional[str] = None,
        **kwargs,
    ) -> 'ReturnT':  # sourcery skip: avoid-builtin-shadow
        """
        Executes the Workflow
        """
        await self._precall_hook_()
        params, kwargs = self._extract_func_kwargs_('execute_workflow', kwargs)
        params = await self._validate_input_(param, params)
        if workflow is None: workflow = self.workflow_name
        if task_queue is None: task_queue = self.task_queue
        if id is None: id = self.generate_id(params)
        params = await self._finalize_params_(params, id, kwargs)
        result = await self.client.execute_workflow(
            workflow,
            params,
            id = id,
            task_queue = task_queue,
            **kwargs,
        )
        return await self._validate_output_(result)

    async def _execute_async_(
        self, 
        *param: 'ParamT',
        id: t.Optional[str] = None,
        task_queue: t.Optional[str] = None,
        workflow: t.Optional[str] = None,
        **kwargs,
    ) -> 'WorkflowHandle[SelfType, ReturnT]':  # sourcery skip: avoid-builtin-shadow
        """
        Executes the Workflow Asyncronously and Returns the Workflow Handle
        """
        await self._precall_hook_()
        params, kwargs = self._extract_func_kwargs_('start_workflow', kwargs)
        params = await self._validate_input_(param, params)
        # print(f'params: {params} ({type(params)}), kwargs: {kwargs}')
        if workflow is None: workflow = self.workflow_name
        if task_queue is None: task_queue = self.task_queue
        if id is None: id = self.generate_id(params)
        params = await self._finalize_params_(params, id, kwargs)
        wf: WorkflowHandle = await self.client.start_workflow(
            workflow,
            params,
            id = id,
            task_queue = task_queue,
            **kwargs,
        )
        wf.set_validator(self._validate_output_)
        return wf

    async def run(
        self, 
        *param: 'ParamT',
        id: t.Optional[str] = None,
        task_queue: t.Optional[str] = None,
        workflow: t.Optional[str] = None,
        **kwargs,
    ) -> 'ReturnT':  # sourcery skip: avoid-builtin-shadow
        """
        Executes the Workflow
        """
        return await self._execute_(*param, id = id, task_queue = task_queue, workflow = workflow, **kwargs)

    async def arun(
        self, 
        *param: 'ParamT',
        id: t.Optional[str] = None,
        task_queue: t.Optional[str] = None,
        workflow: t.Optional[str] = None,
        **kwargs,
    ) -> 'WorkflowHandle[SelfType, ReturnT]':  # sourcery skip: avoid-builtin-shadow
        """
        Executes the Workflow Asyncronously and Returns the Workflow Handle
        """
        return await self._execute_async_(*param, id = id, task_queue = task_queue, workflow = workflow, **kwargs)

    @classmethod
    def _on_preregister_hook_(cls):
        """
        Runs the dispatch pre-register hook
        """
        pass

    @classmethod
    def _on_register_hook_(cls):
        """
        Runs the dispatch hook
        """
        pass

    def _on_init_hook_(self):
        """
        Runs the dispatch init hook
        """
        pass
    

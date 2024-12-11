from __future__ import annotations

"""
Temporal Registry Methods
"""
import copy
import functools
import dataclasses
import typing as t
from temporalio import workflow
from temporalio import activity
from ..utils import logger

if t.TYPE_CHECKING:
    from ..mixins import (
        BaseTemporalMixin, TemporalWorkflowMixin, TemporalActivityMixin,
        TemporalMixinT, TemporalWorkflowT, TemporalActivityT, TemporalDispatchT,
        MixinKinds
    )


@dataclasses.dataclass
class WorkflowConfigState:
    set_run: t.Optional[bool] = False
    set_signal: t.Optional[bool] = False
    set_query: t.Optional[bool] = False

    skip_set_signal: t.Optional[bool] = False
    skip_set_query: t.Optional[bool] = False


def configure_workflow_from_config(
    obj: t.Type['TemporalWorkflowT'],
    state: WorkflowConfigState,
    **kwargs,
):
    # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
    """
    Configures the Workflow from config
    """
    if obj.config.get('run'):
        state.set_run = True
        run_func = getattr(obj, obj.config['run'])
        run_func = workflow.run(run_func)
        setattr(obj, obj.config['run'], run_func)
    
    if obj.config.get('signal'):
        state.set_signal = True
        sig_config = obj.config['signal']
        if isinstance(sig_config, str):
            sig_func_name = sig_config
            sig_func = getattr(obj, sig_config)
            sig_config = {}
        elif isinstance(sig_config, dict):
            # Single Function
            if sig_config.get('func'):
                sig_func_name = sig_config.pop('func')
                sig_func = getattr(obj, sig_func_name)
            
            # Multiple Functions
            else:
                state.skip_set_signal = True
                for sig_func_name, func_config in sig_config.items():
                    sig_func = getattr(obj, sig_func_name)
                    if func_config.get('unfinished_policy') and isinstance(func_config['unfinished_policy'], str):
                        func_config['unfinished_policy'] = workflow.HandlerUnfinishedPolicy[func_config['unfinished_policy']]
                    sig_func = workflow.signal(sig_func, **func_config)
                    setattr(obj, sig_func_name, sig_func)

        # Support Tuple and Lists later
        else:
            logger.warning(f'Unsupported Signal Config Type: {sig_config} ({type(sig_config)})', prefix = 'Temporal', colored = True)
            state.skip_set_signal = True
        
        if not state.skip_set_signal:
            if sig_config.get('unfinished_policy') and isinstance(sig_config['unfinished_policy'], str):
                sig_config['unfinished_policy'] = workflow.HandlerUnfinishedPolicy[sig_config['unfinished_policy']]
            sig_func = workflow.signal(sig_func, **sig_config)
            setattr(obj, sig_func_name, sig_func)

    if obj.config.get('query'):
        state.set_query = True
        query_config = obj.config['query']
        if isinstance(query_config, str):
            query_func_name = query_config
            query_func = getattr(obj, query_config)
            query_config = {}
        
        elif isinstance(query_config, dict):
            # Single Function
            if query_config.get('func'):
                query_func_name = query_config.pop('func')
                query_func = getattr(obj, query_func_name)
            
            # Multiple Functions
            else:
                state.skip_set_query = True
                for query_func_name, func_config in query_config.items():
                    query_func = getattr(obj, query_func_name)
                    query_func = workflow.query(query_func, **func_config)
                    setattr(obj, query_func_name, query_func)
        
        # Support Tuple and Lists later
        else:
            logger.warning(f'Unsupported Query Config Type: {query_config} ({type(query_config)})', prefix = 'Temporal', colored = True)
            state.skip_set_query = True
        
        if not state.skip_set_query:
            query_func = workflow.query(query_func, **query_config)
            setattr(obj, query_func_name, query_func)

def create_run_wrapper(
    obj: t.Type['TemporalWorkflowT'],
    run_func: t.Callable[..., t.Any],
) -> t.Callable[..., t.Any]:
    """
    Creates a run wrapper
    """
    @functools.wraps(run_func)
    def wrapper(*args, **kwargs):
        """
        Runs the run function
        """
        return run_func(*args, **kwargs)
    
    # Clone the method into the child object
    if obj.__qualname__ not in run_func.__qualname__:
        wrapper.__qualname__ = f'{obj.__qualname__}.run'
        setattr(obj, 'run', wrapper)
    return wrapper

def configure_workflow(
    obj: t.Type['TemporalWorkflowT'],
    **kwargs,
):
    # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
    """
    Configures the Workflow
    """
    if obj.enable_init:
        init_func = getattr(obj, '__init__')
        init_func = workflow.init(init_func)
        setattr(obj, '__init__', init_func)
    
    state = WorkflowConfigState()
    obj._configure_cls_()
    obj._configure_display_name_()
    obj._configure_gen_id_()
    if obj.config: configure_workflow_from_config(obj, state)
    if not state.set_run and hasattr(obj, 'run'):
        # if obj.__qualname__ not in getattr(obj, 'run').__qualname__:
        #     # import types
        #     # Clone the method into the child object
        #     # obj.run = types.MethodType(obj.run, obj) 
        #     obj.run = create_run_wrapper(obj, obj.run)

            # f = getattr(obj, 'run')
            # f.__qualname__ = f'{obj.__qualname__}.run'
            # setattr(obj, 'run', f)

        run_func = getattr(obj, 'run')
        # Clone the method into the child object
        # if obj.__qualname__ not in run_func.__qualname__:
        # logger.info(f'Running Workflow: {run_func} - {run_func.__qualname__} - {obj.__qualname__}')
        run_func = workflow.run(run_func)
        setattr(obj, 'run', run_func)

    if not state.set_signal and hasattr(obj, 'signal'):
        sig_func = getattr(obj, 'signal')
        sig_func = workflow.signal(sig_func)
        setattr(obj, 'signal', sig_func)
    
    if not state.set_query and hasattr(obj, 'query'):
        query_func = getattr(obj, 'query')
        query_func = workflow.query(query_func)
        setattr(obj, 'query', query_func)
    
    obj._on_register_hook_()



@dataclasses.dataclass
class ActivityConfigState:
    set_funcs: t.Optional[bool] = False


def configure_activity_from_config(
    obj: t.Type['TemporalActivityT'],
    state: ActivityConfigState,
    **kwargs,
):
    # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
    """
    Configures the Activity from config
    """
    from .main import activity_defn
    if obj.config.get('func'):
        state.set_funcs = True
        func = obj.config['func']
        if isinstance(func, str):
            func_name = func
            act_func = getattr(obj, func)
            act_conf = {}
        else:
            # It's a dict
            func_name = list(func.keys())[0]
            act_func = getattr(obj, func_name)
            act_conf = dict(func.values())

        act_func = activity_defn(obj, act_func, **act_conf)
        setattr(obj, func_name, act_func)
    
    elif obj.config.get('funcs'):
        state.set_funcs = True
        funcs = obj.config['funcs']
        for func_name, func_conf in funcs.items():
            act_func = getattr(obj, func_name)
            act_func = activity_defn(obj, act_func, **func_conf)
            setattr(obj, func_name, act_func)
    
def configure_activity(
    obj: t.Type['TemporalActivityT'],
    **kwargs,
):
    # sourcery skip: extract-method, inline-immediately-returned-variable, move-assign-in-block
    """
    Configures the Activity
    """
    state = ActivityConfigState()
    obj._configure_cls_()
    obj._configure_display_name_()
    obj._configure_gen_id_()
    if obj.config: configure_activity_from_config(obj, state)

    if not state.set_funcs:
        from .main import activity_defn
        # Detect all functions
        for name in dir(obj):
            # logger.info(name, prefix = obj.display_name, colored = True)
            if name.startswith('_') or name.endswith('_') or name in {'configure_registered', 'get_next_cron_run', 'generate_id'}: continue
            if obj.include_funcs and name not in obj.include_funcs: continue
            if obj.exclude_funcs and name in obj.exclude_funcs: continue
            func = getattr(obj, name)
            if not callable(func): continue
            logger.info(f'Registered: `|g|{obj.display_name}|e|:{name}`', prefix = 'Temporal', colored = True)
            act_func = activity_defn(obj, func)
            setattr(obj, name, act_func)
    
    obj._on_register_hook_()

def configure_dispatch(
    obj: t.Type['TemporalDispatchT'],
    **kwargs,
):
    """
    Configure the Dispatch
    """
    obj._configure_cls_()
    obj._on_preregister_hook_()
    from lzl.load import lazy_import
    if obj.input_type and isinstance(obj.input_type, str):
        obj.input_type = lazy_import(obj.input_type)
    if obj.result_type and isinstance(obj.result_type, str):
        obj.result_type = lazy_import(obj.result_type)
    obj._on_register_hook_()




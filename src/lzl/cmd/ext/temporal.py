from __future__ import annotations

import signal
import asyncio
import typer
import typing as t

cmd = typer.Typer(no_args_is_help = True, help = "Temporal Commands")
worker_cmd = typer.Typer(name = "Temporal Worker", invoke_without_command = True, help = "Temporal Worker Commands")

"""
Can be defined by a yaml file:

```yaml
# For Multiple Workers
workers:
  - name: worker1
    task_queue: task-queue-1
    workflows:
    - lib.module.workflow.Workflow1
    - lib.module.workflow.Workflow2
    - lib.module.workflow.Workflow3
    activities:
    - activity1
    max_concurrent_activities: 10
    max_concurrent_workflows: 10
    max_workflow_tasks_per_execution: 10
    retention: 10d
    polling_interval: 10s
    visibility_interval: 10s
    heartbeat_interval: 10s
    ...

# For Single Worker
name: worker1
task_queue: task-queue-1
workflows:
- lib.module.workflow.Workflow1
- lib.module.workflow.Workflow2
- lib.module.workflow.Workflow3
activities:
- activity1
max_concurrent_activities: 10
...
```
"""

if t.TYPE_CHECKING:
    from temporalio.worker import Worker
    from lzl.ext.temporal.client import TemporalClient


event = asyncio.Event()

async def build_single_temporal_worker(
    client: 'TemporalClient',
    name: t.Optional[str] = None,
    task_queue: t.Optional[str] = None,
    workflows: t.Optional[t.List[str]] = None,
    activities: t.Optional[t.List[str]] = None,
    config_file: t.Optional[str] = None,
    **kwargs,
) -> 'Worker':
    """
    Builds a single Temporal Worker
    """
    import yaml
    from lzl.load import lazy_import
    from lzl.ext.temporal.utils import logger
    if config_file:
        from lzl.io import File
        config_file_ = File(config_file)
        config: t.Dict[str, t.List[t.Dict[str, t.Any]] | t.Dict[str, t.Any] | t.Any] = yaml.safe_load(await config_file_.aread_text())
        if config.get('workers'):
            if name: 
                for worker in config['workers']:
                    if worker.get('name') == name:
                        config = worker
                        break
            else:
                config = config['workers'][0]
        elif config.get('worker'):
            config = config['worker']
        if not name: name = config.pop('name')
        elif config.get('name'): _ = config.pop('name')
        if not task_queue: task_queue = config.pop('task_queue')
        if not workflows: workflows = config.pop('workflows')
        elif config.get('workflows'): workflows = list(set(workflows + config.pop('workflows')))
        if not activities: activities = config.pop('activities')
        elif config.get('activities'): activities = list(set(activities + config.pop('activities')))
        kwargs.update(config)
        # typer.echo(f'[{name}] Loaded Temporal Worker from Config File: `{config_file}`')
        logger.info(f'Loaded Temporal Worker from Config File: `{config_file}`', prefix = name)
    
    if not workflows and not activities:
        raise ValueError('Must provide either `workflows` or `activities`')
    if activities:
        activity_modules = {}
        for n, activity in enumerate(activities):
            if isinstance(activity, str): 
                if '.' in activity:
                    module, activity = activity.rsplit('.', 1)
                    if module not in activity_modules:
                        try:
                            activity_modules[module] = lazy_import(module, allow_module = True)
                        except Exception:
                            activity_modules[module] = lazy_import(module, allow_module = True, is_module = True)
                    activities[n] = getattr(activity_modules[module], activity)
                else:
                    activities[n] = lazy_import(activity, allow_module = True)
                # activities[n] = lazy_import(activity, allow_module = True)
    if workflows:
        for n, workflow in enumerate(workflows):
            if isinstance(workflow, str): workflows[n] = lazy_import(workflow, allow_module = True)
    
    # TODO - add support for executors, etc
    task_queue = task_queue or client.tmprl_config.default_task_queue
    from temporalio.worker import Worker
    return Worker(
        client,
        task_queue = task_queue,
        workflows = workflows,
        activities = activities,
        identity = name,
        **kwargs,
    )

async def run_single_temporal_worker(
    name: t.Optional[str] = None,
    task_queue: t.Optional[str] = None,
    workflows: t.Optional[t.List[str]] = None,
    activities: t.Optional[t.List[str]] = None,
    config_file: t.Optional[str] = None,
    **kwargs,
):
    """
    Runs a single Temporal Worker
    """
    from lzl.ext.temporal.client import TemporalClient
    client = await TemporalClient.connect(
        default_task_queue = task_queue,
    )
    worker = await build_single_temporal_worker(
        client = client,
        name = name,
        task_queue = task_queue,
        workflows = workflows,
        activities = activities,
        config_file = config_file,
        **kwargs,
    )
    return await client.run_worker(worker, event = event, **kwargs)
    # client.run_worker(worker, event = event)

def spawn_single_temporal_worker(
    name: t.Optional[str] = None,
    task_queue: t.Optional[str] = None,
    workflows: t.Optional[t.List[str]] = None,
    activities: t.Optional[t.List[str]] = None,
    config_file: t.Optional[str] = None,
    **kwargs,
):
    """
    Spawns a single Temporal Worker
    """
    loop = asyncio.get_event_loop()
    # from lzl.ext.temporal.utils import logger
    try:
        loop.run_until_complete(run_single_temporal_worker(
            name = name,
            task_queue = task_queue,
            workflows = workflows,
            activities = activities,
            config_file = config_file,
            **kwargs,
        ))
    except KeyboardInterrupt:
        # event.set()
        # loop.run_until_complete(loop.shutdown_asyncgens())
        typer.echo('Interrupt Received. Shutting Down Temporal Worker')
    except Exception as e:
        # event.set()
        # loop.run_until_complete(loop.shutdown_asyncgens())
        typer.echo(f'Error Running Temporal Worker: {e}', err = True)
    finally:
        event.set()
        loop.run_until_complete(loop.shutdown_asyncgens())
        
    

@worker_cmd.command("start")
def start_temporal_worker(
    name: str = typer.Option(None, "-n", "--name", help = "The name of the worker"),
    task_queue: str = typer.Option(None, "-q", "--queue", help = "The task queue to use"),
    workflows: t.List[str] = typer.Option(None, "-w", "--workflow", help = "The workflows to use"),
    activities: t.List[str] = typer.Option(None, "-a", "--activity", help = "The activities to use"),
    env_file: t.Optional[str] = typer.Option(None, "-e", "--env", help = "The env file to use"),
    config_file: t.Optional[str] = typer.Option(None, "-c", "--config", help = "The config file to use"),
):
    """
    Starts a Single Temporal Worker
    """
    if env_file:
        if env_file.endswith('.yaml'):
            import os
            import yaml, pathlib
            data = yaml.safe_load(pathlib.Path(env_file).read_text())
            for k, v in data.items():
                os.environ[k] = str(v)
        else:
            import dotenv
            dotenv.load_dotenv(dotenv_path = env_file, override = True)
    
    import sys
    sys.path.append(os.getcwd())
    spawn_single_temporal_worker(
        name = name,
        task_queue = task_queue,
        workflows = workflows,
        activities = activities,
        config_file = config_file,
    )
    # typer.echo(f"Python Path: {sys.executable}")
    # event = asyncio.Event()
    # asyncio.run(run_single_temporal_worker(
    #     name = name,
    #     task_queue = task_queue,
    #     workflows = workflows,
    #     activities = activities,
    #     config_file = config_file,
    #     event = event,
    # ))
    
    


cmd.add_typer(worker_cmd, name = "worker")
from __future__ import annotations

import asyncio
import typing as t
import typer
from pathlib import Path
from lzl.load import lazy_import
from lzl.ext.temporal.loop.worker import Looper

try:
    import anyio
    _default_rt = 'anyio'
except ImportError:
    _default_rt = 'asyncio'

if t.TYPE_CHECKING:
    from lzl.ext.temporal.configs import TemporalSettings
    from lzl.ext.temporal.loop.config import RuntimeConfig

def run(
    pre_init: t.Optional[t.List[t.Callable[..., t.Any] | str]] = None,
    settings: t.Optional["TemporalSettings"] = None,
    run_init: t.Optional[t.List[t.Callable[..., t.Any] | str]] = None,
    async_runtime: t.Optional[t.Literal['asyncio', 'anyio'] | str] = None,
    config: t.Optional["RuntimeConfig"] = None,
    **kwargs,
) -> None:
    """
    The entrypoint for the Temporal Looper
    """
    if async_runtime is None: async_runtime = _default_rt
    looper = Looper(config=config, pre_init=pre_init, settings=settings, **kwargs)
    if async_runtime == 'anyio':
        return anyio.run(looper.run, run_init)
    if async_runtime == 'asyncio':
        return asyncio.run(looper.run(run_init))
    # It must be a custom runtime
    rt: t.Callable[..., t.Any] = lazy_import(async_runtime)
    return rt(looper.run(run_init))


cmd = typer.Typer(name = "Temporal Worker Runtime", invoke_without_command = True, help = "Temporal Runtime")
@cmd.command("run")
def run_cmd(
    config_file: t.Optional[Path] = typer.Option(None, "-c", "--config", help = "The config file to load the settings from", envvar = "TEMPORAL_WORKER_CONFIG_FILE", show_envvar = True),
    pre_init: t.Optional[t.List[str]] = typer.Option(None, "-p", "--pre-init", help = "The pre-init functions to run. These should be in the form of `module.function`", envvar = "TEMPORAL_WORKER_PRE_INIT", show_envvar = True),
    run_init: t.Optional[t.List[str]] = typer.Option(None, "-r", "--run-init", help = "The run-init functions to run. These should be in the form of `module.function`", envvar = "TEMPORAL_WORKER_RUN_INIT", show_envvar = True),
    settings: t.Optional[str] = typer.Option(None, "-s", "--settings", help = "The settings to use. This should be in the form of a function such as `module.get_settings`", envvar = "TEMPORAL_WORKER_SETTINGS", show_envvar = True),
    namespace: t.Optional[str] = typer.Option(None, "-n", "--namespace", help = "The namespace to use for the client", envvar = "TEMPORAL_WORKER_NAMESPACE", show_envvar = True),
    identity: t.Optional[str] = typer.Option(None, "-i", "--identity", help = "The identity to use for the client", envvar = "TEMPORAL_WORKER_IDENTITY", show_envvar = True),
    host: t.Optional[str] = typer.Option(None, "-h", "--host", help = "The host to use for the client", envvar = "TEMPORAL_WORKER_HOST", show_envvar = True),
    queue: t.Optional[str] = typer.Option(None, "-q", "--queue", help = "The queue to use for the worker", envvar = "TEMPORAL_WORKER_QUEUE", show_envvar = True),
    workflows: t.Optional[t.List[str]] = typer.Option(None, "-w", "-wf", "--workflow", help = "The workflows to use for the worker", envvar = "TEMPORAL_WORKER_WORKFLOWS", show_envvar = True),
    activities: t.Optional[t.List[str]] = typer.Option(None, "-a", "-act", "--activity", help = "The activities to use for the worker", envvar = "TEMPORAL_WORKER_ACTIVITIES", show_envvar = True),
    converter: t.Optional[str] = typer.Option(None, "-conv", "--converter", help = "The converter to use for the worker", envvar = "TEMPORAL_WORKER_CONVERTER", show_envvar = True),
    interceptors: t.Optional[t.List[str]] = typer.Option(None, "-i", "--interceptor", help = "The interceptors to use for the worker", envvar = "TEMPORAL_WORKER_INTERCEPTORS", show_envvar = True),
    env_file: t.Optional[str] = typer.Option(None, "-e", "--env-file", help = "The env file to load the settings from", envvar = "TEMPORAL_WORKER_ENV_FILE", show_envvar = True),
    async_runtime: t.Optional[str] = typer.Option(_default_rt, "-rt", "--runtime", help = "The async runtime to use. Defaults to `asyncio` or `anyio`", envvar = "TEMPORAL_WORKER_RUNTIME", show_envvar = True),
):
    """
    Runs the Temporal Looper

    Args:
        config_file (str, optional): The config file to load the settings from. Defaults to None.
        pre_init (List[str], optional): The pre-init functions to run. These should be in the form of `module.function`. Defaults to None.
        run_init (List[str], optional): The run-init functions to run. These should be in the form of `module.function`. Defaults to None.
        settings (str, optional): The settings to use. This should be in the form of a function such as `module.get_settings`. Defaults to None.
        async_runtime (str, optional): The async runtime to use. Defaults to `asyncio` or `anyio`. Defaults to None.
    """
    import sys, os
    sys.path.append(os.getcwd())
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
    if settings is not None: 
        settings = lazy_import(settings)
        if callable(settings): settings = settings()
        if not hasattr(settings, 'get_runtime_config'): 
            settings = None
    run(
        pre_init = pre_init,
        settings = settings,
        run_init = run_init,
        async_runtime = async_runtime,
        config_file = config_file,
        namespace = namespace,
        identity = identity,
        host = host,
        queue = queue,
        workflows = workflows,
        activities = activities,
        converter = converter,
        interceptors = interceptors,
    )



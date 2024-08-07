from __future__ import annotations

"""
Server CLI ABC
"""

import os
import sys
import typer
from typing import Optional, List, Dict, Any, Union, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from lazyops.libs.abcs.configs.base import AppSettings


cmd = typer.Typer(no_args_is_help = True)

def build_server_cmd(
    cli_module: str,
    settings: 'AppSettings',
    host: Optional[str] = None,
    port: Optional[int] = None,
    num_server_workers: Optional[int] = 1,
    server_backend: Optional[str] = 'uvicorn',
    server_class: Optional[str] = 'uvloop',
    reload_enabled: Optional[bool] = False,
) -> str:
    """
    Prepare the Server Command
    """
    if not host: host = "0.0.0.0"
    if not port: port = 8080
    server_cmd = f"{server_backend} "

    # settings.server.app_host = host
    os.environ['APP_HOST'] = host
    # settings.server.app_port = port
    os.environ['APP_PORT'] = str(port)

    if server_backend == "uvicorn":
        server_cmd += f"{cli_module} --host {host} --port {port} --workers {num_server_workers} --h11-max-incomplete-event-size 524288"
        if reload_enabled: server_cmd += f" --reload --reload-dir {settings.module_path.as_posix()}"
        if server_class and server_class in {"auto", "asyncio", "uvloop"}: server_cmd += f" --loop {server_class}"

    elif server_backend == "hypercorn":
        server_cmd += f"{cli_module} --bind {host}:{port} --workers {num_server_workers}"
        if reload_enabled: server_cmd += " --reload"
        if server_class and server_class in {"asyncio", "uvloop", "trio"}: server_cmd += f" --worker-class {server_class}"

    elif server_backend == "gunicorn":
        server_cmd += f"--bind {host}:{port} --threads {num_server_workers}" #  --logger-class 'scout.utils.logs.StubbedGunicornLogger'"
        if reload_enabled: server_cmd += " --reload"
        if server_class:
            if server_class == "uvicorn":
                server_cmd += " --worker-class uvicorn.workers.UvicornWorker"
            elif server_class in {"sync", "eventlet", "gevent", "tornado", "gthread", "gaiohttp"}: server_cmd += f" --worker-class {server_class}"

        server_cmd += f" --pid {settings.global_ctx.state.server_process_id_path.as_posix()}"
        server_cmd += f" {cli_module}"

    else:
        typer.echo(f"Backend Server {server_backend} not supported")
        sys.exit(1)
    
    return server_cmd
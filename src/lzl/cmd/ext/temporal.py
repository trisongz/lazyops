from __future__ import annotations

import typer
import typing as t
from lzl.ext.temporal.loop.main import cmd as worker_cmd

cmd = typer.Typer(no_args_is_help = True, help = "Temporal Commands")
cmd.add_typer(worker_cmd, name = "worker")


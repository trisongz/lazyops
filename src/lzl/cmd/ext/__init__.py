
import typer
from . import temporal

cmd = typer.Typer(no_args_is_help = True, help = "Extension Commands")
cmd.add_typer(temporal.cmd, name = "temporal")
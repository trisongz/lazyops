from __future__ import annotations

"""
LazyOps Commands

A collection of useful commands to streamline your workflow and improve productivity.
"""

import typer
from . import keygen

cmd = typer.Typer(no_args_is_help = True, help = "LZO CLI")
cmd.add_typer(keygen.cmd, name="kg", help = "Key Generation Commands")

def main():
    cmd()

if __name__ == '__main__':
    main()

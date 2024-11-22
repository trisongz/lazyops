from __future__ import annotations


import os
import typer
import subprocess
from pathlib import Path
from .static import COLOR
from typing import Optional, List, Any


def build_aliases(name: str, additional_names: Optional[List[str]] = None) -> List[str]:
    """
    Create the aliases for a given service name
    """
    aliases = [name]
    if '.' not in name:
        if '-' in name: aliases.append(name.replace('-', '.'))
        elif '_' in name: aliases.append(name.replace('_', '.'))
    if '-' not in name:
        if '.' in name: aliases.append(name.replace('.', '-'))
        elif '_' in name: aliases.append(name.replace('_', '-'))
    if '_' not in name:
        if '.' in name: aliases.append(name.replace('.', '_'))
        elif '-' in name: aliases.append(name.replace('-', '_'))
    if additional_names: aliases.extend(additional_names)
    return list(set(aliases))


def add_to_env(
    envvar: str,
    envval: Any,
    envpath: Optional[str] = '~/.bashrc',
):
    """
    Helper for adding to the environment variable
    """
    envval = str(envval)
    if ' ' in envval: envval = f'"{envval}"'
    os.system(f"echo 'export {envvar}={envval}' >> {envpath}")
    os.environ[envvar] = envval


def parse_text_file(path: Path) -> List[str]:
    """
    Parses a text file
    """
    text_lines = path.read_text().split('\n')
    return [line.strip() for line in text_lines if ('#' not in line[:5] and line.strip())]

def echo(message: str):
    """ 
    Helper for printing a message
    """
    typer.echo(message, color = True)

def run_cmd(cmdstr: str):
    """
    Helper for running a command
    """
    try:
        data = subprocess.check_output(cmdstr, shell=True, text=True, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        if data[-1:] == '\n': data = data[:-1]
        echo(data)

    except subprocess.CalledProcessError as e:
        echo(f'{COLOR.RED}Failed to run command: {cmdstr}{COLOR.END}')
        echo(f'{COLOR.RED}Error: {e.stderr}{COLOR.END}')
        raise e


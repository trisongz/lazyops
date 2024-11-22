import typer
from . import ext

cmd = typer.Typer(no_args_is_help = True, help = "Lazyops Command Line Interface")
cmd.add_typer(ext.cmd, name = "ext", help = "Extension Commands")

def main():
    cmd()

if __name__ == '__main__':
    main()

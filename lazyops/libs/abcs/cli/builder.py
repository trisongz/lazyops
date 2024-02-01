"""
Build Script Helper

Usage:

Run a Build Step

$ lazyops-build run <step>[1-4]

Run a Pip Hotfix

$ lazyops-build hotfix <file>

Update the Build Config

$ lazyops-build config <path>

Break the Cache

$ lazyops-build breakcache

Patch the SSL Config

$ lazyops-build patchssl
"""

import os
os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

import yaml
import typer
import contextlib
import subprocess
import concurrent.futures
from pathlib import Path
from pydantic import model_validator
from lazyops.types.models import BaseModel
from lazyops.libs.proxyobj import ProxyObject
from typing import Optional, List, Any, Dict, Union

class COLOR:
    """
    Color Constants
    """
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Constants / Env Vars
# BUILDS_ENABLED_SERVICES: List[str] = os.environ.get('BUILDS_ENABLED_SERVICES', 'server').split(',')
GITHUB_TOKEN: str = os.environ.get('GH_TOKEN', os.getenv('GITHUB_TOKEN', ''))

# Paths
TEMP_PATH = os.getenv('TEMP_PATH', '/tmp')
BUILD_CONFIG_PATH = Path(os.getenv('BUILD_CONFIG_PATH', f'{TEMP_PATH}/build_config.yaml'))

_HERE = Path(__file__).parent
DEFAULT_CONFIG_PATH = _HERE.joinpath('default_build_config.yaml')

APP_HOME = os.getenv('APP_HOME', '/app')
APP_PATH = Path(APP_HOME)

REQUIREMENTS_PATH = Path(os.getenv('REQUIREMENTS_PATH', '/tmp/requirements'))
PKGS_PATH = REQUIREMENTS_PATH.joinpath('pkgs')

# APP_NAME = os.getenv('APP_NAME', "App")

def echo(message: str):
    """ 
    Helper for printing a message
    """
    typer.echo(message, color = True)

# The Build Config Variables
class BuildConfig(BaseModel):
    """
    Build Config
    """
    app_name: Optional[str] = None
    builds: Optional[Dict[str, Union[str, List[str], Dict[str, Union[List[str], Dict, Any]]]]] = {}
    custom_installers: Optional[Dict[str, List[str]]] = {}
    custom_commands: Optional[Dict[str, List[str]]] = {}
    enabled_build_services: Optional[List[str]] = None
    kinds: Optional[Dict[str, Dict[str, Union[List[str], Dict[str, List[str]]]]]] = None

    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'BuildConfig':
        """
        Load the build config
        """
        if path is None:
            path = BUILD_CONFIG_PATH if BUILD_CONFIG_PATH.exists() else DEFAULT_CONFIG_PATH
        return cls.parse_obj(yaml.safe_load(path.read_text()))
    
    @model_validator(mode = 'after')
    def validate_app_env(self):
        """
        Validates the app environment
        """
        if self.app_name is None: self.app_name = os.getenv('APP_NAME', "App")
        if self.enabled_build_services is None:
            if services := os.getenv('BUILDS_ENABLED_SERVICES'):
                self.enabled_build_services = services.split(',')
            else: self.enabled_build_services = list(self.builds.keys())
        if self.kinds is None:
            self.kinds = {}
            for t, conf in self.builds.items():
                if conf.get('kind'):
                    if conf['kind'] not in self.kinds:
                        self.kinds[conf['kind']] = {}
                    if t not in self.kinds[conf['kind']]:
                        self.kinds[conf['kind']][t] = []
                    if conf.get('names'):
                        self.kinds[conf['kind']][t].extend(conf['names'])
                    self.kinds[conf['kind']][t] = list(set(self.kinds[conf['kind']][t]))
        return self

    def show_env(self, step: str):
        """
        Show the environment
        """
        echo(f"Starting Step: {COLOR.GREEN}{step}{COLOR.END}\n")
        echo(f"[Enabled Builds]: {COLOR.BLUE}{self.enabled_build_services}{COLOR.END}")

    def update_config(self, path: Optional[Path] = None, **config: Any):
        """
        Update the build config
        """
        data = self.model_dump()
        if path: 
            update_data = yaml.safe_load(path.read_text())
            data.update(update_data)
        if config: data.update(config)
        BUILD_CONFIG_PATH.write_text(yaml.dump(data, default_flow_style = False))
    
    def has_service(self, service: str, fixed: Optional[bool] = True) -> bool:
        """
        Helper for checking whether the service is enabled
        """
        if not fixed:
            return any((name in service or service in name) for name in self.enabled_build_services)
        return any(
            name in self.enabled_build_services 
            for name in self.builds.get(service, {}).get('names', [])
        )
    
    @property
    def kinds(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Get the kinds
        """
        return self.builds

    

cmd = typer.Typer(no_args_is_help = True)

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

# service_names: Dict[str, List[str]] = {}
# kinds: Dict[str, Dict[str, List[str]]] = {}

config: BuildConfig = ProxyObject(obj_getter = BuildConfig.load)

def add_to_env(
    envvar: str,
    envval: Any
):
    """
    Helper for adding to the environment variable
    """
    envval = str(envval)
    if ' ' in envval: envval = f'"{envval}"'
    os.system(f"echo 'export {envvar}={envval}' >> ~/.bashrc")
    os.environ[envvar] = envval


def parse_text_file(path: Path) -> List[str]:
    """
    Parses a text file
    """
    text_lines = path.read_text().split('\n')
    return [line.strip() for line in text_lines if ('#' not in line[:5] and line.strip())]

def get_apt_packages(kind: str, name: str) -> List[str]:
    """
    Helper for getting the apt packages for a given service/builder
    """
    # pkg_dir = PKGS_PATH.joinpath(kind)
    pkg_dir = PKGS_PATH
    for alias in config.kinds[kind].get(name, []):
        pkg_file = pkg_dir.joinpath(f'{alias}.txt')
        if pkg_file.exists():
            return parse_text_file(pkg_file)
    return []



def get_pip_requirements(kind: str, name: str) -> Optional[str]:
    """
    Helper for getting the pip requirements file for a given service/builder
    """
    pkg_dir = REQUIREMENTS_PATH.joinpath(kind)
    for alias in config.kinds[kind].get(name, []):
        req_file = pkg_dir.joinpath(f'{alias}.txt')
        if req_file.exists():
            req_file.write_text(req_file.read_text().replace('GITHUB_TOKEN', GITHUB_TOKEN))
            return req_file.as_posix()
        req_file = pkg_dir.joinpath(f'requirements.{alias}.txt')
        if req_file.exists():
            return req_file.as_posix()
    return None


"""
Step 1: Install Apt Packages
"""

APT_PKGS = []

def add_to_apt_pkgs(*pkg: str):
    """
    Helper for adding to the apt packages
    """
    global APT_PKGS
    APT_PKGS.extend(pkg)


def run_apt_install():
    """
    Helper for running apt install
    """
    if not APT_PKGS: return
    _pkgs = ' '.join(list(set(APT_PKGS)))
    echo(f"Installing Apt Packages: {COLOR.BLUE}{_pkgs}{COLOR.END}")
    os.system(f"apt-get update && apt-get -yq install --no-install-recommends {_pkgs}")

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


def get_apt_pkg_requirements():
    """
    Helper for getting the apt package requirements
    """
    for service in config.builds:
        if config.has_service(service):
            if service_pkgs := get_apt_packages(config.builds[service]['kind'], service):
            # if service_pkgs := get_apt_packages(service):
                echo(f'{COLOR.BLUE}[{config.builds[service]['kind']}]{COLOR.END} Adding {COLOR.BOLD}{service}{COLOR.END} requirements\n\n - {COLOR.BOLD}{service_pkgs}{COLOR.END}\n')
                add_to_apt_pkgs(*service_pkgs)



# Custom Requirements for Services / Builders

def run_custom_install_requirements(
    name: str,
):
    """
    Helper for running the custom install requirements
    """
    if custom_installers := config.builds.get(name, {}).get('custom_install'):
        echo(f'{COLOR.BLUE}[{name}]{COLOR.END} Running {COLOR.BOLD}Custom Installers{COLOR.END}')
        for custom in custom_installers:
            if custom_install := config.custom_installers.get(custom):
                echo(f'{COLOR.BLUE}[{name}]{COLOR.END} Running {COLOR.BOLD}{custom}{COLOR.END}')
                for cmdstr in custom_install:                    
                    os.system(cmdstr)


def run_step_one():
    """
    Step 1: Install Apt Packages
    """
    config.show_env(f'Step 1: {config.app_name} Package Installations')
    get_apt_pkg_requirements()
    run_apt_install()
    for service in config.enabled_build_services:
        run_custom_install_requirements(service)
    echo(f"{COLOR.GREEN}Step 1: {config.app_name} Package Installations Complete{COLOR.END}\n\n")


"""
END Step 1: Install Apt Packages
"""


"""
START Step 2: Install Pip Requirements
"""

def run_step_two():
    """
    Function for installing stage two requirements
    """
    config.show_env(f'Step 2: {config.app_name} Pip Installations')
    service_names = config.enabled_build_services
    for service in service_names:
        kind = config.builds[service]['kind']
        echo(f'{COLOR.BLUE}[{kind}]{COLOR.END} Installing {COLOR.BOLD}{service}{COLOR.END} requirements')
        if req_file := get_pip_requirements(kind, service):
            os.system(f"pip install -r {req_file}")
            if 'custom_commands' in config.builds[service]:
                for custom in config.builds[service]['custom_commands']:
                    if custom_cmd := config.custom_commands.get(custom):
                        echo(f'{COLOR.BLUE}[{kind}]{COLOR.END} Running {COLOR.BOLD}{custom}{COLOR.END}')
                        for cmdstr in custom_cmd:
                            os.system(cmdstr)

    echo(f"{COLOR.GREEN}Step 2: {config.app_name} Pip Installations Complete{COLOR.END}\n\n")

"""
END Step 2: Install Pip Requirements
"""

"""
START Step 3: Run Post-Installation Requirements
"""

def init_build_service(
    name: str,
):
    """
    Helper for initializing the build service
    """
    enabled = config.has_service(name)
    kind = config.builds[name]['kind']
    if enabled:
        echo(f'{COLOR.BLUE}[{kind}]{COLOR.END} Initializing {COLOR.BOLD}{name}{COLOR.END}')
        if config.builds[name].get('init'):
            init_cmd = config.builds[name]['init']
            from lazyops.utils.lazy import lazy_import
            init_func = lazy_import(init_cmd)
            init_func()
        elif name == 'server':
            with contextlib.suppress(Exception):
                from lazyops.utils.lazy import lazy_import
                init_func = lazy_import(f'{config.app_name}.app.main.init_build')
                init_func()
        echo(f'{COLOR.BLUE}[{kind}]{COLOR.END} Completed {COLOR.BOLD}{name}{COLOR.END} Initialization')
        add_to_env(f'{name.upper()}_{kind.upper()}_ENABLED', True)
    else:
        add_to_env(f'{name.upper()}_{kind.upper()}_ENABLED', False)


def init_build_deps():  # sourcery skip: extract-method
    """
    Initialize the worker dependencies

    - Do this multi-threaded later
    """
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(init_build_service, name) for name in config.enabled_build_services
        ]
        for future in concurrent.futures.as_completed(futures):
            _ = future.result()
    

def run_step_three():
    """
    Function for running the third step
    """
    config.show_env(f'Step 3: {config.app_name} Post-Installations')
    init_build_deps()
    echo(f"{COLOR.GREEN}Step 3: {config.app_name} Post-Installations Complete{COLOR.END}\n\n")

"""
END Step 3: Run Post-Installation Requirements
"""

"""
START Step 4: Finalize and Test
"""

def run_validate_step(
    name: str,
):
    """
    Helper for running the validation step
    """
    kind = config.builds[name]['kind']
    echo(f'{COLOR.BLUE}[{kind}]{COLOR.END} Validating {COLOR.BOLD}{name}{COLOR.END}')
    if config.builds[name].get('validate'):
        validate_cmd = config.builds[name]['validate']
        from lazyops.utils.lazy import lazy_import
        validate_func = lazy_import(validate_cmd)
        validate_func()
    elif name == 'server':
        with contextlib.suppress(Exception):
            from lazyops.utils.lazy import lazy_import
            validate_func = lazy_import(f'{config.app_name}.app.main.validate_build')
            validate_func()

    echo(f'{COLOR.BLUE}[{kind}]{COLOR.END} Completed {COLOR.BOLD}{config.app_name}{COLOR.END} Validation')


def run_step_four():
    """
    Function for running the fourth step
    """
    config.show_env(f'Step 4: {config.app_name} Installation & Validation')
    os.system(f'pip install {APP_PATH}')
    Path('/data').mkdir(exist_ok = True)
    add_to_env(f'{config.app_name.upper()}_DATA_DIR', '/data')
    
    import time
    add_to_env(f'{config.app_name.upper()}_BUILD_DATE', int(time.time()))

    for t in config.enabled_build_services:
        names = config.builds[t].get('names', [t])
        for name in names:
            if config.has_service(name):
                run_validate_step(name, fixed = name == 'server')
    echo(f"{COLOR.GREEN}Step 4: {config.app_name} Validation Complete{COLOR.END}\n\n")


@cmd.command("run")
def run_build(
    step: int = typer.Argument(1, help = "Step to Run", show_default = True, min = 1, max = 4),
):
    """
    Usage:

    Run a Scout Build Step
    $ run <step>
    """
    if step == 1:
        run_step_one()
    elif step == 2:
        run_step_two()
    elif step == 3:
        run_step_three()
    elif step == 4:
        run_step_four()
    else:
        typer.echo(f"Invalid Step: {step}")
    
@cmd.command("hotfix")
def run_pip_hotfix(
    file: Path = typer.Argument(..., help = "Filename to Hotfix", resolve_path = True),
):
    """
    Runs hotfix for pip requirements
    """
    if not file.exists():
        echo(f'{COLOR.RED}File does not exist: {file.as_posix()}{COLOR.END}')
        raise ValueError(f'File does not exist: {file.as_posix()}')
    
    echo(f'{COLOR.BLUE}Running Hotfix for {file.as_posix()}{COLOR.END}')
    reqs = parse_text_file(file)
    for req in reqs:
        echo(f'{COLOR.BLUE}Installing: {req}{COLOR.END}')
        if 'GITHUB_TOKEN' in req:
            req = req.replace('GITHUB_TOKEN', GITHUB_TOKEN)
        os.system(f'pip install --upgrade --no-deps --force-reinstall "{req}"')
    

@cmd.command("config")
def run_update_build_config(
    path: Path = typer.Argument(BUILD_CONFIG_PATH, help = "Path to Build Config", resolve_path = True),
):
    """
    Runs the build config
    """
    if not path.exists():
        echo(f'{COLOR.RED}File does not exist: {path.as_posix()}{COLOR.END}')
        raise ValueError(f'File does not exist: {path.as_posix()}')
    echo(f'{COLOR.BLUE}Updating Build Config: {path.as_posix()}{COLOR.END}')
    config.update_config(path)


@cmd.command("breakcache")
def run_break_cache():
    """
    Runs the break cache command
    """
    os.system('echo "Breaking Cache: $(date)" > /tmp/.breakcache')

@cmd.command("patchssl")
def run_patch_ssl():
    """
    Patch the OpenSSL Config for Python
    """
    openssl_path = APP_PATH.joinpath('openssl.cnf')
    echo(f'{COLOR.BLUE}Patching OpenSSL Config: {openssl_path.as_posix()}{COLOR.END}')
    openssl_path.write_text("""
openssl_conf = openssl_init

[openssl_init]
ssl_conf = ssl_sect

[ssl_sect]
system_default = system_default_sect

[system_default_sect]
Options = UnsafeLegacyRenegotiation
""".strip())
    add_to_env('OPENSSL_CONF', openssl_path.as_posix())

def main():
    """
    Main Function
    """
    cmd()

if __name__ == "__main__":
    main()

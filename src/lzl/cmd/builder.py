from __future__ import annotations

"""
Lazy Docker Builder Helper
"""

import os

os.environ['APP_ENV'] = 'cicd'
os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

import yaml
import typer
import contextlib
import subprocess
import concurrent.futures
from pathlib import Path
from pydantic import BaseModel, model_validator, Field, PrivateAttr
from lzl.proxied import ProxyObject
from .envvars import (
    GITHUB_TOKEN,
    ASSETS_PATH,
    APP_PATH,
    REQUIREMENTS_PATH,
    PKGS_PATH,
    TEMP_PATH,
)
from .utils import (
    parse_text_file,
    run_cmd,
    add_to_env,
    build_aliases,
    echo,
)
from .static import COLOR
from typing import List, Optional, Dict, Any

BUILDS_ENABLED_REFS: List[str] = os.environ.get('BUILDS_ENABLED_REFS', 'server').split(',')
ENABLE_DEFAULT_INSTALLERS: bool = os.environ.get('ENABLE_DEFAULT_INSTALLERS', 'true').lower() in {'true', '1', 't', 'y', 'yes'}
BUILD_CONFIG_PATH = Path(os.getenv('BUILD_CONFIG_PATH', f'{TEMP_PATH}/build_config.yaml'))
DEFAULT_CONFIG_PATH = ASSETS_PATH.joinpath('default_builder.yaml')
STATE_PATH = Path(os.getenv('STATEFUL_PATH', f'{TEMP_PATH}/builder_state.yaml'))

class CustomInstaller(BaseModel):
    """
    Custom Installer

    These run during the stage 1 of the builder
    """
    name: str = Field(None, description = "The name of the custom installer")
    cmds: List[str] = Field(default_factory = list, description = "The commands to run")

    @classmethod
    def load_defaults(cls) -> List[CustomInstaller]:
        """
        Loads the default installers
        """
        default_file = ASSETS_PATH.joinpath('default_installers.yaml')
        if not default_file.exists(): return []
        data = yaml.safe_load(default_file.read_text())
        return [CustomInstaller.model_validate(item) for item in data]

    def run(self):
        """
        Runs the custom installer
        """
        echo(f'Running Custom Installer: {COLOR.BLUE}{self.name}{COLOR.END}')
        for cmdstr in self.cmds:
            os.system(cmdstr)


class CustomCommand(BaseModel):
    """
    Custom Command

    These run during the stage 2 of the builder
    """
    name: str = Field(None, description = "The name of the custom command")
    cmds: List[str] = Field(default_factory = list, description = "The commands to run")

    def run(self):
        """
        Runs the custom command
        """
        echo(f'Running Custom Command: {COLOR.BLUE}{self.name}{COLOR.END}')
        for cmdstr in self.cmds:
            os.system(cmdstr)


class BuildRef(BaseModel):
    """
    Build Ref
    """
    name: str = Field('server', description = "The name of the build reference")
    refs: List[str] = Field(default_factory = list, description = "The names of the build reference")
    enabled: Optional[bool] = Field(None, description = "Whether the build reference is enabled")
    custom_install: List[str] = Field(default_factory = list, description = "Custom Install Commands")
    custom_commands: List[str] = Field(default_factory = list, description = "Custom Commands")

class BuilderConfig(BaseModel):
    """
    Builder Config
    """
    app_name: Optional[str] = Field(os.getenv('APP_NAME'), description="The name of the app")
    refs: List[BuildRef] = Field(default_factory = list, description = "The build references")
    custom_installers: List[CustomInstaller] = Field(default_factory = list, description = "Custom Installers")
    custom_commands: List[CustomCommand] = Field(default_factory = list, description = "Custom Commands")
    enabled_refs: List[str] = Field(BUILDS_ENABLED_REFS, description = "The enabled build references")

    extra: Dict[str, Any] = Field(default_factory = dict)

    @model_validator(mode = 'after')
    def validate_refs(self):
        """
        Validate the build references
        """
        if self.extra.get('validated'): return
        for ref in self.refs:
            if ref.enabled is None:
                ref.enabled = ref.name in self.enabled_refs
        
        if ENABLE_DEFAULT_INSTALLERS:
            existing = [c.name for c in self.custom_installers]
            default_installers = CustomInstaller.load_defaults()
            for installer in default_installers:
                if installer.name not in existing:
                    self.custom_installers.append(installer)
        
        self.extra['validated'] = True
        return self

    @property
    def builds(self) -> Dict[str, BuildRef]:
        """
        Returns the build references
        """
        return {
            ref.name: ref
            for ref in self.refs if ref.enabled
        }
    
    @property
    def enabled_builds(self) -> List[str]:
        """
        Returns the enabled build services
        """
        return [ref.name for ref in self.refs if ref.enabled]

    @property
    def installers(self) -> Dict[str, CustomInstaller]:
        """
        Returns the custom installers
        """
        return {
            installer.name: installer
            for installer in self.custom_installers
        }
    
    @property
    def commands(self) -> Dict[str, CustomCommand]:
        """
        Returns the custom commands
        """
        return {
            command.name: command
            for command in self.custom_commands
        }
    
    @property
    def stage(self) -> int:
        """
        Returns the stage
        """
        return self.extra.get('stage', 0)
    
    @stage.setter
    def stage(self, value: int):
        """
        Sets the stage
        """
        self.extra['stage'] = value
        self.save()

    def show_env(self, step: str):
        """
        Show the environment
        """
        echo(f"Starting Step: {COLOR.GREEN}{step}{COLOR.END}\n")
        echo(f"[Enabled Builds]: {COLOR.BLUE}{self.enabled_builds}{COLOR.END}")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'BuilderConfig':
        """
        Load the build config
        """
        if path is None:
            path = BUILD_CONFIG_PATH if BUILD_CONFIG_PATH.exists() else DEFAULT_CONFIG_PATH
        return cls.model_validate(yaml.safe_load(path.read_text()))
    
    def save(self):
        """
        Save the build config
        """
        BUILD_CONFIG_PATH.write_text(yaml.dump(self.model_dump(), default_flow_style = False))

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
    

    def get_apt_packages(self, ref: str) -> List[str]:
        """
        Helper for getting the apt packages for a given ref name
        """
        pkg_dir = PKGS_PATH
        if ref not in self.builds: return []
        for alias in self.builds[ref].refs:
            pkg_file = pkg_dir.joinpath(f'{alias}.txt')
            if pkg_file.exists():
                return parse_text_file(pkg_file)
        return []


    def get_pip_requirements(self, ref: str) -> Optional[str]:
        """
        Helper for getting the pip requirements file for a given ref name
        """
        pkg_dir = REQUIREMENTS_PATH.joinpath(ref)
        if ref not in self.builds: return None
        for alias in self.builds[ref].refs:
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

    @property
    def apt_pkgs(self) -> List[str]:
        """
        Returns the apt packages
        """
        if 'apt_pkgs' not in self.extra:
            self.extra['apt_pkgs'] = []
        return self.extra['apt_pkgs']


    def add_to_apt_pkgs(self, *pkg: str):
        """
        Helper for adding to the apt packages
        """
        self.apt_pkgs.extend(pkg)

    def run_apt_install(self):
        """
        Helper for running apt install
        """
        if not self.apt_pkgs: return
        _pkgs = ' '.join(list(set(self.apt_pkgs)))
        echo(f"Installing Apt Packages: {COLOR.BLUE}{_pkgs}{COLOR.END}")
        os.system(f"apt-get update && apt-get -yq install --no-install-recommends {_pkgs}")

    def get_apt_pkg_requirements(self):
        """
        Helper for getting the apt package requirements
        """
        for ref in self.enabled_builds:
            if service_pkgs := self.get_apt_packages(ref):
                echo(f'{COLOR.BLUE}[{ref}]{COLOR.END} Adding {COLOR.BOLD}{ref}{COLOR.END} requirements\n\n - {COLOR.BOLD}{service_pkgs}{COLOR.END}\n')
                self.add_to_apt_pkgs(*service_pkgs)
        self.save()
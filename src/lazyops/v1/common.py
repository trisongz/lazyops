from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import subprocess
import importlib
import pkg_resources
import threading
from subprocess import check_output
from dataclasses import dataclass
from typing import Optional
from fileio import File, PathIO, PathIOLike
try:
    from fileio.src import get_pathlike, autojson, read_json, read_jsonlines
except ImportError:
    from fileio import get_pathlike, read_json, read_jsonlines, autojson

from lazyops.envs import logger
from lazyops.envs import LazyEnv



def lazy_import(name):
    if name in sys.modules:
        return sys.modules[name]
    sys.modules[name] = importlib.import_module(name)
    return sys.modules[name]

def exec_command(cmd):
    out = check_output(cmd, shell=True)
    if isinstance(out, bytes): out = out.decode('utf8')
    return out.strip()

def run_cmd(cmd):
    return exec_command(cmd)

def lazy_check(req):
    try:
        _ = pkg_resources.get_distribution(req)
        return True
    except pkg_resources.DistributionNotFound:
        return False


def lazy_install(req, force=False, latest=False, verbose=False):
    req_base = req.split('=')[0].replace('>','').replace('<','').strip()
    if lazy_check(req_base) and not force:
        return
    python = sys.executable
    pip_exec = [python, '-m', 'pip', 'install']
    if '=' not in req or latest:
        pip_exec.append('--upgrade')
    pip_exec.append(req)
    subprocess.check_call(pip_exec, stdout=subprocess.DEVNULL)
    if verbose:
        logger.info(f'{req} installed successfully.')

def lazy_init(name, lib_name=None, force=False, latest=False, verbose=False):
    lazy_install(name, force=force, latest=latest, verbose=verbose)
    return lazy_import(lib_name or name)


def clone_repo(repo, path=None, absl=False, add_to_syspath=True):
    path = path or ('/content' if LazyEnv.is_colab else File.curdir())
    if isinstance(repo, str): repo = repo.split(',')
    assert isinstance(repo, list), f'Repo must be a list or string: {type(repo)}'
    logger.info(f'Cloning Repo(s): {repo} into {path}')
    for r in repo:
        if 'github.com' not in r:
            r = f'https://github.com/{r}'
        clonepath = File.join(path, File.base(r)) if not absl else path
        try:
            run_cmd(f'git clone {r} {clonepath}')
        except Exception as e:
            logger.error(f'Error Cloning {r}: {str(e)}')
        if add_to_syspath:
            sys.path.append(clonepath)


@dataclass
class LazySubmodule:
    name: str # 'models'
    repo: Optional[str] = None
    module: Optional[str] = None # 'libname'
    module_path: Optional[str] = None # 'libname.nested' = 'libname.nested.models'
    init: Optional[bool] = False

    @property
    def main_module(self):
        return importlib.util.find_spec(self.name)
    
    @property
    def main_module_path(self):
        if not self.main_module:
            return None
        return self.main_module.submodule_search_locations[0]

    @property
    def submodule_name(self):
        if not self.module:
            return self.name
        if not self.module_path:
            return self.module + '.' + self.name
        if self.name in self.module_path:
            return self.module_path
        return self.module_path + '.' + self.name
    
    @property
    def submodule_namepath(self):
        return '/'.join(self.submodule_name.split('.'))

    @property
    def submodule_path(self):
        if not self.main_module_path:
            return None
        return File.join(self.main_module_path, self.submodule_namepath)
    
    @property
    def has_initialized(self):
        return bool(self.submodule_name in sys.modules)

    def lazy_import(self):
        if self.submodule_name and self.has_initialized:
            return
        if not File.exists(self.submodule_path) and self.repo and self.init:
            clone_repo(self.repo, path=self.submodule_path, abls=True)
        if File.exists(self.submodule_path):
            sys.modules[self.submodule_name] = importlib.import_module(self.submodule_name)
            logger.info(f'Initialized Submodule: {self.submodule_name}')
        else:
            logger.warn(f'Failed to Initilize Submodule: {self.submodule_name}')



class LazyImporter:
    libs = {}
    submodules = {}
    def __init__(self):
        self.lock = threading.RLock()
    
    @property
    def imports(self):
        return LazyImporter.libs
    
    def has_submodule(name, *args, **kwargs):
        bool(LazyImporter.get_submodule(name)) 

    def get_submodule(name, *args, **kwargs):
        return LazyImporter.submodules.get(name, None)

    def setup_submodule(self, name, *args, **kwargs):
        self.lock.acquire()
        with self.lock:
            if name not in LazyImporter.submodules:
                LazyImporter.submodules[name] = LazySubmodule(name=name, *args, **kwargs)
                LazyImporter.submodules[name].lazy_init()
            return LazyImporter.submodules[name]

    def setup_lib(self, name, lib_name=None, force=False, latest=False, verbose=False):
        self.lock.acquire()
        with self.lock:
            if name not in LazyImporter.libs:
                LazyImporter.libs[name] = lazy_init(name, lib_name, force, latest, verbose)
            return LazyImporter.libs[name]
    
    def has_lib(self, name, lib_name=None):
        return bool(self.get_lib(name, lib_name))

    def get_lib(self, name, lib_name=None):
        return LazyImporter.libs.get(name, LazyImporter.libs.get(lib_name, None))

    def __call__(self, name, lib_name=None, *args, **kwargs):
        if self.has_lib(name, lib_name):
            return self.get_lib(name, lib_name)
        return self.setup_lib(name, lib_name=lib_name, *args, **kwargs)

lazylibs = LazyImporter()



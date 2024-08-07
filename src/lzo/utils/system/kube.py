from __future__ import annotations

import os

from typing import Union, Optional, Dict, Any, List, TYPE_CHECKING
from functools import lru_cache

# Stateful Variables
_is_in_kubernetes: Optional[bool] = None
_k8s_namespace: Optional[str] = None
_k8s_kubeconfig: Optional[str] = None
_kubeconfig_dir: Optional[str] = None


@lru_cache()
def is_in_kubernetes() -> bool:
    """
    Check if we are running in a kubernetes cluster.
    """
    global _is_in_kubernetes
    if _is_in_kubernetes is None:
        _is_in_kubernetes = os.path.isdir('/var/run/secrets/kubernetes.io/')
    return _is_in_kubernetes


@lru_cache()
def get_k8s_namespace(
    env_var: str = 'NAMESPACE',
    default: str = 'default'
) -> str:
    """
    Get the kubernetes namespace.
    """
    global _k8s_namespace
    if _k8s_namespace is None:
        if is_in_kubernetes():
            with open('/var/run/secrets/kubernetes.io/serviceaccount/namespace') as f:
                _k8s_namespace = f.read().strip()
        else:
            _k8s_namespace = os.getenv(env_var, default)
    return _k8s_namespace

@lru_cache()
def get_k8s_kubeconfig(
    env_var: str = 'KUBECONFIG',
    default: str = None,
) -> str:
    """
    Get the kubernetes kubeconfig.
    """
    global _k8s_kubeconfig
    if _k8s_kubeconfig is None:
        if is_in_kubernetes():
            _k8s_kubeconfig = '/var/run/secrets/kubernetes.io/serviceaccount/token'
        else:
            _k8s_kubeconfig = os.getenv(env_var, default)
            if _k8s_kubeconfig is None:
                _k8s_kubeconfig = os.path.expanduser('~/.kube/config')
    return _k8s_kubeconfig


# Local K8s
def get_local_kubeconfig_dir(
    env_var: str = 'KUBECONFIG_DIR',
    default: str = None,
) -> str:
    """
    Get the local kubernetes kubeconfig.
    """
    global _kubeconfig_dir
    if _kubeconfig_dir is None:
        _kubeconfig_dir = os.getenv(env_var, default) or os.path.expanduser('~/.kube')
    return _kubeconfig_dir

@lru_cache()
def get_local_kubeconfig(
    name: Optional[str] = None,
    set_as_envval: bool = False,
) -> str:
    """
    Get the local kubernetes kubeconfig
    - this assumes that it's not the default one.
    """
    if name is None: return get_k8s_kubeconfig()
    p = os.path.join(get_local_kubeconfig_dir(), name)
    for stem in ('', '-cluster', '-admin-config', '-config', '-kubeconfig'):
        for ext in ('', '.yaml', '.yml'):
            if os.path.isfile(p + stem + ext): 
                px = os.path.abspath(p + stem + ext)
                if set_as_envval:
                    os.environ['KUBECONFIG'] = px
                return px
    raise FileNotFoundError(f'Could not find kubeconfig file: {name} @ {p}')


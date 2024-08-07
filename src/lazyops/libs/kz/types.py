from __future__ import annotations

"""
Type Checking Support 
"""
import abc
import kr8s
from kr8s import objects
from kr8s.asyncio import objects as aobjects
from typing import Optional, Dict, Any, List, Union, overload, TYPE_CHECKING

if TYPE_CHECKING:
    ObjectT = Union[
        objects.Pod,
        objects.Service,
        objects.Deployment,
        objects.StatefulSet,
        objects.ConfigMap,
        objects.Secret,
        objects.PersistentVolume,
        objects.PersistentVolumeClaim,
        objects.Namespace,
        objects.Node,
        objects.Event,
        objects.Endpoints,
        objects.Ingress,
        objects.ServiceAccount,
        objects.Role,
        objects.RoleBinding,
        objects.ClusterRole,
        objects.APIObject,
    ]
    ObjectListT = List[ObjectT]
    aObjectT = Union[
        aobjects.Pod,
        aobjects.Service,
        aobjects.Deployment,
        aobjects.StatefulSet,
        aobjects.ConfigMap,
        aobjects.Secret,
        aobjects.PersistentVolume,
        aobjects.PersistentVolumeClaim,
        aobjects.Namespace,
        aobjects.Node,
        aobjects.Event,
        aobjects.Endpoints,
        aobjects.Ingress,
        aobjects.ServiceAccount,
        aobjects.Role,
        aobjects.RoleBinding,
        aobjects.ClusterRole,
        aobjects.APIObject,
    ]
    aObjectListT = List[aObjectT]


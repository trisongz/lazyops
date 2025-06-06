from __future__ import annotations

"""
Type Checking Support 
"""

import typing as t
from lzl import load

if load.TYPE_CHECKING:
    import kr8s
else:
    kr8s = load.LazyLoad("kr8s", install_missing=True)

if t.TYPE_CHECKING:
    from kr8s import objects
    from kr8s.asyncio import objects as aobjects
    ObjectT = t.Union[
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
    ObjectListT = t.List[ObjectT]
    aObjectT = t.Union[
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
    aObjectListT = t.List[aObjectT]


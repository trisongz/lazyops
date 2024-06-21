from __future__ import annotations

from typing import Iterator, Type, Tuple, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel
    from .resources import Resource


class ResourceNotFoundError(Exception):
    pass



class ResourceRegistry():
    __versions: Dict[str, Dict[str, Type['Resource']]] = {}
    __resources: Dict[Tuple[str, str], Type['Resource']] = {}


    @classmethod
    def add(cls, resource_class: Type['Resource']):
        # To get all versions of a resource.
        cls.__versions.setdefault(resource_class.__fqname__, {})
        cls.__versions[resource_class.__fqname__][resource_class.__version__] = resource_class
        # For easy access via (apiVersion, kind) tuple.
        key = (resource_class.__api_version__, resource_class.__kind__)
        cls.__resources[key] = resource_class

    @classmethod
    def get(cls, api_version: str, kind: str) -> Type['Resource']:
        key = (api_version, kind)
        try:
            return cls.__resources[key]
        except KeyError as e:
            msg = f'Could not find resource class for: {key}'
            raise ResourceNotFoundError(msg) from e


    @classmethod
    def get_version(cls, fqname: str, version: str) -> Type['Resource']:
        try:
            return cls.__versions[fqname][version]
        except KeyError as e:
            msg = f'Could not find resource class for: {fqname}, {version}'
            raise ResourceNotFoundError(msg) from e


    @classmethod
    def iter_versions(cls, resource_class: Type['Resource']) -> Iterator[Tuple[str, Type['Resource']]]:
        try:
            return iter(cls.__versions[resource_class.__fqname__].items())
        except KeyError as e:
            msg = f'Could not find resource classes for: {getattr(resource_class, "__fqname__", resource_class)}'
            raise ResourceNotFoundError(msg) from e


    @classmethod
    def iter_resources(cls) -> Iterator[Type['Resource']]:
        return iter(cls.__resources.values())
from __future__ import annotations

"""
Attributes
"""
import contextlib
import collections
from pydantic import BaseModel, Field
from kvdb.io.serializers import get_serializer
from typing import Optional, List, Dict, Any, Union, TypeVar, MutableMapping, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from lazyops.libs.kinde.client import KindeApiClient

serializer = get_serializer('json')

class Organization(BaseModel):
    """
    Organization
    """
    id: str = Field(None, description="The organization ID")
    name: str = Field(None, description="The organization name")


class BaseAttribute(BaseModel):
    """
    Base Attribute
    """
    id: str = Field(None, description="The attribute ID")
    key: str = Field(None, description="The attribute key")
    name: str = Field(None, description="The attribute name")
    description: str = Field(None, description="The attribute description")

CRUD_VALUES = ['read', 'create', 'update', 'delete']

class Permission(BaseAttribute):
    """
    Permission

    - This is a base class for permissions that handles comparisons

    Comparisons using CRUD:
      create:x
      read:x
      update:x
      delete:x

      read < create < update < delete 

    Example:

        >>> permission = Permission(key='read:users')
        >>> 'read:users' in permission
        True
        >>> 'read:users' == permission
        True
        >>> 'read:users' > permission
        False
    """

    @property
    def crud_value(self) -> str:
        """
        Returns the CRUD Value
        """
        return self.key.split(':')[0]
    
    @property
    def resource_value(self) -> str:
        """
        Returns the Resource Value
        """
        return self.key.split(':')[1]
    
    @property
    def attribute_value(self) -> Optional[str]:
        """
        Returns the Attribute Value
        """
        split = self.key.split(':', 2)
        return split[2] if len(split) == 3 else None

    
    def __eq__(self, other: Union[str, 'Permission']) -> bool:
        """
        Checks if the permission is equal to the other
        """
        return self.key == other if isinstance(other, str) else self.key == other.key
    
    def __gt__(self, other: Union[str, 'Permission']) -> bool:
        """
        Checks if the permission is greater than the other

        - This is used to determine the order of permissions

        Example:

            >>> permission = Permission(key='read:users')
            >>> 'read:users' > permission
            False
            >>> 'create:users' > permission
            True
            >>> 'update:users' > permission
            True
            >>> 'read:something' > permission
            False
        """
        if isinstance(other, str): 
            if self.resource_value not in other: return False
            crud_value = other.split(':')[0]
            return CRUD_VALUES.index(crud_value) > CRUD_VALUES.index(self.crud_value)
        if self.resource_value not in other.resource_value: return False
        crud_value = other.crud_value
        return CRUD_VALUES.index(crud_value) > CRUD_VALUES.index(self.crud_value)
    
    def __ge__(self, other: Union[str, 'Permission']) -> bool:
        """
        Checks if the permission is greater than or equal to the other

        - This is used to determine the order of permissions

        Example:

            >>> permission = Permission(key='read:users')
            >>> 'read:users' >= permission
            True
            >>> 'create:users' >= permission
            True
            >>> 'update:users' >= permission
            True
            >>> 'read:something' >= permission
            False
        """
        if isinstance(other, str): 
            if self.resource_value not in other: return False
            crud_value = other.split(':')[0]
            return CRUD_VALUES.index(crud_value) >= CRUD_VALUES.index(self.crud_value)
        if self.resource_value not in other.resource_value: return False
        crud_value = other.crud_value
        return CRUD_VALUES.index(crud_value) >= CRUD_VALUES.index(self.crud_value)
    
    def __lt__(self, other: Union[str, 'Permission']) -> bool:
        """
        Checks if the permission is less than the other

        - This is used to determine the order of permissions

        Example:

            >>> permission = Permission(key='read:users')
            >>> 'read:users' < permission
            False
            >>> 'create:users' < permission
            True
            >>> 'update:users' < permission
            True
            >>> 'read:something' < permission
            False
        """
        if isinstance(other, str): 
            if self.resource_value not in other: return False
            crud_value = other.split(':')[0]
            return CRUD_VALUES.index(crud_value) < CRUD_VALUES.index(self.crud_value)
        if self.resource_value not in other.resource_value: return False
        crud_value = other.crud_value
        return CRUD_VALUES.index(crud_value) < CRUD_VALUES.index(self.crud_value)
    
    def __le__(self, other: Union[str, 'Permission']) -> bool:
        """
        Checks if the permission is less than or equal to the other

        - This is used to determine the order of permissions

        Example:

            >>> permission = Permission(key='read:users')
            >>> 'read:users' <= permission
            True
            >>> 'create:users' <= permission
            True
            >>> 'update:users' <= permission
            True
            >>> 'read:something' <= permission
            False
        """
        if isinstance(other, str): 
            if self.resource_value not in other: return False
            crud_value = other.split(':')[0]
            return CRUD_VALUES.index(crud_value) <= CRUD_VALUES.index(self.crud_value)
        if self.resource_value not in other.resource_value: return False
        crud_value = other.crud_value
        return CRUD_VALUES.index(crud_value) <= CRUD_VALUES.index(self.crud_value)

    def __contains__(self, item: Union[str, 'Permission']) -> bool:
        """
        Checks if the permission contains the item
        
        Example:

            >>> permission = Permission(key='read:users')
            >>> 'read:users' in permission
            True
            >>> 'read' in permission
            True
            >>> 'write:users' in permission
            False
            >>> 'write' in permission
            False
        """
        return item in self.key if isinstance(item, str) else item.key in self.key
        



class Role(BaseModel):
    """
    Role
    """
    id: str = Field(None, description="The role ID")
    key: str = Field(None, description="The role key")
    name: str = Field(None, description="The role name")
    permissions: List[Permission] = Field(default_factory=list, description="The role permissions")

    def __eq__(self, other: Union[str, 'Role', 'Permission']) -> bool:
        """
        Checks if the role is equal to the other
        """
        if isinstance(other, str) and ':' in other or isinstance(other, Permission):
            return any(other == permission for permission in self.permissions)
        return self.key == other if isinstance(other, str) else self.key == other.key

    """
    Permission Comparisons
    """

    def __gt__(self, other: Union[str, 'Permission']) -> bool:
        """
        Checks if the role has a greater permission than the other
        """
        return any(permission > other for permission in self.permissions)

    def __ge__(self, other: Union[str, 'Permission']) -> bool:
        """
        Checks if the role has a greater or equal permission than the other
        """
        return any(permission >= other for permission in self.permissions)

    def __lt__(self, other: Union[str, 'Permission']) -> bool:
        """
        Checks if the role has a lesser permission than the other
        """
        return any(permission < other for permission in self.permissions)

    def __le__(self, other: Union[str, 'Permission']) -> bool:
        """
        Checks if the role has a lesser or equal permission than the other
        """
        return any(permission <= other for permission in self.permissions)

    def __contains__(self, item: Union[str, 'Permission']) -> bool:
        """
        Checks if the role contains the permission
        """
        return any(item in permission for permission in self.permissions)



KT = TypeVar('KT')
VT = TypeVar('VT')


class JSONProperty(collections.abc.MutableMapping, MutableMapping[KT, VT]):
    """
    A JSON property that can be used to store arbitrary JSON data.
    """

    def __init__(
        self, 
        client: 'KindeApiClient',
        key: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        self.key = key
        self._data = data or {}
        if isinstance(self._data, str): self._data = serializer.loads(self._data)
        self._client = client
        self._update_enabled = client._app_api.settings.is_mtg_enabled

    @contextlib.contextmanager
    def with_update(self):
        """
        Updates the data after the context manager exits
        """
        yield
        if self._update_enabled:
            self._client._update_user_property(
                self.key, 
                serializer.dumps(self._data),
                is_json= False,
            )

    def pop(self, key: KT, default: Optional[VT] = None) -> VT:
        with self.with_update():
            return self._data.pop(key, default)
        
    def update(self, **kwargs: Any) -> None:
        """
        Updates the data
        """
        with self.with_update():
            self._data.update(kwargs)

    def setdefault(self, key: KT, default: VT) -> VT:
        with self.with_update():
            return self._data.setdefault(key, default)
        
    def clear(self) -> None:
        with self.with_update():
            self._data.clear()

    def __getitem__(self, key: KT) -> VT:
        return self._data[key]

    def __setitem__(self, key: KT, value: VT) -> None:
        with self.with_update():
            self._data[key] = value

    def __delitem__(self, key: KT) -> None:
        with self.with_update():
            del self._data[key]

    def __iter__(self) -> Iterator[KT]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f'<JSONProperty({self._data})>'
    
    def __str__(self) -> str:
        return str(self._data)
    
    def __eq__(self, other: Any) -> bool:
        return self._data == other
    
    def __ne__(self, other: Any) -> bool:
        return self._data != other
    
    def __bool__(self) -> bool:
        return bool(self._data)
    
    def __contains__(self, key: KT) -> bool:
        return key in self._data
    
    def __hash__(self) -> int:
        return hash(self._data)
    
class JSONOrgProperty(JSONProperty):
    """
    A JSON property that can be used to store arbitrary JSON data.
    """


    @contextlib.contextmanager
    def with_update(self):
        """
        Updates the data after the context manager exits
        """
        yield
        if self._update_enabled:
            self._client._update_org_property(
                self.key, 
                serializer.dumps(self._data),
                is_json= False,
            )
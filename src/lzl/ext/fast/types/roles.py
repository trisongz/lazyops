from __future__ import annotations

from lzl.types.common import UpperStrEnum, _EXTEND_SUPPORTED
from typing import Union, Optional, Dict

if _EXTEND_SUPPORTED:
    from aenum import extend_enum

UserPrivilageLevel = {
    'ANON': 0,
    'UNKNOWN': 0,
    'AUTHENTICATED': 5,

    # Access Level (1-20)
    'READ': 5,
    'WRITE': 10,
    'MODIFY': 15,
    'PRIVILAGED': 20, # 'PRIVILAGED' is a user with 'READ', 'WRITE', and 'MODIFY' privilages
    
    # User Level (30-50)
    'USER': 30,             # 'USER' has 'READ', 'WRITE', and 'MODIFY' privilages
    'USER_API': 30,         # 'USER_API' is a user with 'USER' and 'API' privilages
    'USER_STAFF': 35,       # 'USER_STAFF' is a user with 'USER' and 'STAFF' privilages
    'USER_PRIVILAGED': 40,  # 'USER_PRIVILAGED' is a user with 'USER' and 'PRIVILAGED' privilages
    'USER_ADMIN': 45,       # 'USER_ADMIN' is a user with 'USER' and 'ADMIN' privilages
    
    # Internal Level (50-70)
    'STAFF': 50,            # 'STAFF' has 'READ', 'WRITE', and 'MODIFY' privilages
    'API_CLIENT': 50,       # 'API_CLIENT' is a user with 'API' privilages
    'SERVICE': 50,          # 'SERVICE' is a user with 'API' privilages
    'SERVICE_ACCOUNT': 50,  # 'SERVICE_ACCOUNT' is a user with 'API' privilages
    'SYSTEM': 60,           # 'SYSTEM' has 'READ', 'WRITE', and 'MODIFY' privilages
    
    # Admin Level (100+)
    'ADMIN': 100,           # 'ADMIN' has 'READ', 'WRITE', and 'MODIFY' privilages
    'SYSTEM_ADMIN': 150,
    'SUPER_ADMIN': 1000,
}
UserPrivilageIntLevel = {v: k for k, v in UserPrivilageLevel.items()}

DEFAULT_UNKNOWN_ROLE = 'UNKNOWN'
_DEFAULT_ROLE = object()

def set_default_unknown_role(role: Union[str, int, 'UserRole']) -> None:
    """
    Sets the default unknown role
    """
    global DEFAULT_UNKNOWN_ROLE
    if role != DEFAULT_UNKNOWN_ROLE:
        DEFAULT_UNKNOWN_ROLE = role
        from lazyops.utils.logs import logger
        logger.info(f'Set Default Unknown Role: {DEFAULT_UNKNOWN_ROLE}')

def extend_role(
    name: str,
    priviledge_level: int,
    set_as_default: bool = False,
    override: bool = False,
):
    """
    Extends the Role with a new level
    """
    if not _EXTEND_SUPPORTED: raise ImportError('aenum is not installed. Please install it to use this feature')
    global UserPrivilageLevel, UserPrivilageIntLevel
    name = name.upper()
    if name in UserPrivilageLevel:
        if not override: raise ValueError(f'Role {name} already exists')
    else:
        extend_enum(UserRole, name, name)
    
    UserPrivilageLevel[name] = priviledge_level
    UserPrivilageIntLevel[name] = priviledge_level
    if set_as_default: set_default_unknown_role(name)
    
def extend_roles(
    roles: Dict[str, int],
    set_as_default: Optional[str] = None,
    override: bool = False,
) -> None:
    """
    Extends the Roles with a new level
    """
    if not _EXTEND_SUPPORTED: raise ImportError('aenum is not installed. Please install it to use this feature')
    global UserPrivilageLevel, UserPrivilageIntLevel
    for role, priviledge_level in roles.items():
        if role in UserPrivilageLevel:
            if not override: raise ValueError(f'Role {role} already exists')
        else:
            extend_enum(UserRole, role, role)
        UserPrivilageLevel[role] = priviledge_level
        UserPrivilageIntLevel[role] = priviledge_level
        if set_as_default and role == set_as_default: set_default_unknown_role(role)

    
class UserRole(UpperStrEnum):
    ANON = 'ANON'
    UNKNOWN = 'UNKNOWN'
    # DEFAULT = 'DEFAULT'
    AUTHENTICATED = 'AUTHENTICATED'
    
    
    # Access Level (1-20)
    READ = 'READ'
    WRITE = 'WRITE'
    MODIFY = 'MODIFY'
    PRIVILAGED = 'PRIVILAGED'
    
    # User Level (30-50)
    USER = 'USER'
    USER_API = 'USER_API'
    USER_STAFF = 'USER_STAFF'
    USER_PRIVILAGED = 'USER_PRIVILAGED'
    USER_ADMIN = 'USER_ADMIN'

    # Internal Level (50-70)
    STAFF = 'STAFF'
    SYSTEM = 'SYSTEM'
    SERVICE = 'SERVICE'
    SERVICE_ACCOUNT = 'SERVICE_ACCOUNT'
    API_CLIENT = 'API_CLIENT'

    # Admin Level (100+)
    ADMIN = 'ADMIN'
    SYSTEM_ADMIN = 'SYSTEM_ADMIN'
    SUPER_ADMIN = 'SUPER_ADMIN'

    @property
    def privilage_level(self) -> int:
        """
        Returns the privilage level of the user role
        - Can be subclassed to return a different value
        """
        return UserPrivilageLevel[self.value]

    def __eq__(self, other: Union[int, str, 'UserRole']) -> bool:
        """
        Returns True if the user role is equal to the other
        """
        if other is None: other = UserRole.ANON
        if isinstance(other, int):
            return self.privilage_level == other
        if hasattr(other, 'privilage_level'):
            return self.privilage_level == other.privilage_level
        return self.privilage_level == UserPrivilageLevel[other.upper()]

    def __ne__(self, other: Union[int, str, 'UserRole']) -> bool:
        """
        Returns True if the user role is not equal to the other
        """
        if other is None: other = UserRole.ANON
        if isinstance(other, int):
            return self.privilage_level != other
        if hasattr(other, 'privilage_level'):
            return self.privilage_level != other.privilage_level
        return self.privilage_level != UserPrivilageLevel[other.upper()]

    def __lt__(self, other: Union[int, str, 'UserRole']) -> bool:
        """
        Returns True if the user role is less than the other
        """
        if other is None: other = UserRole.ANON
        if isinstance(other, int):
            return self.privilage_level < other
        if hasattr(other, 'privilage_level'):
            return self.privilage_level < other.privilage_level
        return self.privilage_level < UserPrivilageLevel[other.upper()]

    def __le__(self, other: Union[int, 'UserRole']) -> bool:
        """
        Returns True if the user role is less than or equal to the other
        """
        if other is None: other = UserRole.ANON
        if isinstance(other, int):
            return self.privilage_level <= other
        if hasattr(other, 'privilage_level'):
            return self.privilage_level <= other.privilage_level
        return self.privilage_level <= UserPrivilageLevel[other.upper()]

    def __gt__(self, other: Union[int, str, 'UserRole']) -> bool:
        """
        Returns True if the user role is greater than the other
        """
        if other is None: other = UserRole.ANON
        if isinstance(other, int):
            return self.privilage_level > other
        if hasattr(other, 'privilage_level'):
            return self.privilage_level > other.privilage_level
        return self.privilage_level > UserPrivilageLevel[other.upper()]
        
    def __ge__(self, other: Union[int, str, 'UserRole']) -> bool:
        """
        Returns True if the user role is greater than or equal to the other
        """
        if other is None: other = UserRole.ANON
        if isinstance(other, int):
            return self.privilage_level >= other
        if hasattr(other, 'privilage_level'):
            return self.privilage_level >= other.privilage_level
        return self.privilage_level >= UserPrivilageLevel[other.upper()]
    
    def __contains__(self, other: Union[int, str, 'UserRole']) -> bool:
        """
        Returns True if the user role is contained in the other
        """
        if other is None: other = UserRole.ANON
        if isinstance(other, int):
            return self.privilage_level >= other
        if hasattr(other, 'privilage_level'):
            return self.privilage_level >= other.privilage_level
        return self.privilage_level >= UserPrivilageLevel[other.upper()]

    @classmethod
    def parse_role(cls, role: Union[str, int], default: Optional[Union[str, int, 'UserRole']] = _DEFAULT_ROLE) -> 'UserRole':
        """
        Parses the role
        """
        if role is None: return UserRole.ANON
        try:
            return cls(UserPrivilageIntLevel[role]) if isinstance(role, int) else cls(role.upper())
        except Exception as e:
            from lazyops.utils.logs import logger
            if default is _DEFAULT_ROLE: default = DEFAULT_UNKNOWN_ROLE
            default_role = cls.parse_role(default, None) if default is not None else None
            logger.warning(f'Error Parsing Unknown Role: {role}: {e} - Returning {default_role} Role')
            return default_role
    
    def __hash__(self):
        """
        Returns the hash of the user role
        """
        return hash(self.value)


    @classmethod
    def set_default_unknown_role(cls, role: Union[str, int, 'UserRole']) -> None:
        """
        Sets the default unknown role
        """
        return set_default_unknown_role(role)

    @classmethod
    def extend_role(
        cls,
        name: str,
        priviledge_level: int,
        set_as_default: bool = False,
    ):
        """
        Extends the Role with a new level
        """
        return extend_role(name, priviledge_level, set_as_default)

    parse = parse_role

from lazyops.types.common import UpperStrEnum
from typing import Union

UserPrivilageLevel = {
    'ANON': 0,

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
    'SYSTEM': 60,           # 'SYSTEM' has 'READ', 'WRITE', and 'MODIFY' privilages
    
    # Admin Level (100+)
    'ADMIN': 100,           # 'ADMIN' has 'READ', 'WRITE', and 'MODIFY' privilages
    'SYSTEM_ADMIN': 150,
    'SUPER_ADMIN': 1000,
}
    
class UserRole(UpperStrEnum):
    ANON = 'ANON'
    
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

    def __lt__(self, other: Union[int, 'UserRole']) -> bool:
        """
        Returns True if the user role is less than the other
        """
        if isinstance(other, int):
            return self.privilage_level < other
        return self.privilage_level < other.privilage_level

    def __le__(self, other: Union[int, 'UserRole']) -> bool:
        """
        Returns True if the user role is less than or equal to the other
        """
        if isinstance(other, int):
            return self.privilage_level <= other
        return self.privilage_level <= other.privilage_level

    def __gt__(self, other: Union[int, 'UserRole']) -> bool:
        """
        Returns True if the user role is greater than the other
        """
        if isinstance(other, int):
            return self.privilage_level > other
        return self.privilage_level > other.privilage_level

    def __ge__(self, other: Union[int, 'UserRole']) -> bool:
        """
        Returns True if the user role is greater than or equal to the other
        """
        if isinstance(other, int):
            return self.privilage_level >= other
        return self.privilage_level >= other.privilage_level

    

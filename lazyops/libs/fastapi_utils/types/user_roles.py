
from lazyops.types.common import UpperStrEnum

class UserRole(UpperStrEnum):
    ANON = 'ANON'
    USER = 'USER'
    STAFF = 'STAFF'
    SYSTEM = 'SYSTEM'
    ADMIN = 'ADMIN'
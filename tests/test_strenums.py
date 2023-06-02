from lazyops.types.common import StrEnum, UpperStrEnum

class New(StrEnum):
    """
    The job status
    """
    NEW = 'new'
    START = 'start'
    STAGING = 'staging'
    FINAL = 'final'

    def __contains__(self, other) -> bool:
        __key = other.lower() if isinstance(other, str) else other
        print(__key)
        return super().__contains__(__key)

# this returns false
x = (
    'NEW' in [
        New.NEW,
    ]
)
print(x)

# This returns True
print('new' in New.NEW)

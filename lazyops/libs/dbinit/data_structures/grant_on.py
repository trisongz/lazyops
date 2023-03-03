from dataclasses import dataclass
from typing import Sequence

from lazyops.libs.dbinit.data_structures.privileges import Privilege
from lazyops.libs.dbinit.mixins.grantable import Grantable


@dataclass
class GrantOn:
    """
    Represents a Sequence of :class:`lazyops.libs.dbinit.data_structures.Privilege` to grant on this
    :class:`lazyops.libs.dbinit.entities.Role` for a Sequence of :class:`lazyops.libs.dbinit.mixins.Grantable`.
    """

    privileges: Sequence[Privilege]
    on: Sequence[Grantable]


# type to represent how to store grants in Role
GrantStore = dict[Grantable, set[Privilege]]

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from lazyops.libs.dbinit.data_structures.privileges import Privilege

if TYPE_CHECKING:
    from lazyops.libs.dbinit.entities.role import Role


@dataclass
class GrantTo:
    """
    Represents a Sequence of :class:`lazyops.libs.dbinit.data_structures.Privilege` to grant to a
    :class:`lazyops.libs.dbinit.entities.Role` for a given :class:`lazyops.libs.dbinit.mixins.Grantable`.
    """

    privileges: Sequence[Privilege]
    to: Sequence[Role]

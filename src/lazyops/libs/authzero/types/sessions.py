from __future__ import annotations

"""
Wrapper for niquest Sessions
"""

from abc import ABC
from typing import Optional, List, Dict, Any, Union
from lazyops.libs import lazyload


if lazyload.TYPE_CHECKING:
    import niquests
    from niquests import Session, AsyncSession, Response, AsyncResponse
else:
    niquests = lazyload.LazyLoad("niquests")


class RequestSessionContext(ABC):
    """
    The Request Session Context

    - This is a wrapper for the niquests Session, which will maintain handling of long running sessions
    """

    def __init__(self):
        
        self.session: Optional['Session'] = None
        self.asession: Optional['AsyncSession'] = None

        self.n_requests: int = 0
        self.an_requests: int = 0
    




from __future__ import annotations

from starlette.authentication import BaseUser
from typing import Optional, Dict, Any, List, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..providers import ProviderClientT
    from ..manager import OAuth2Manager
    from .token import OAuth2Token
    

class OAuth2User(BaseUser):
    """
    The OAuth2 User
    """

    def __init__(
        self,
        token: Optional['OAuth2Token'],
        client: Optional['ProviderClientT'],
        manager: Optional['OAuth2Manager'],
        **kwargs,
    ):
        """
        Initializes the OAuth2 User
        """
        self.token = token
        self.client = client
        self.manager = manager
        self.is_admin = False
        self.is_staff = False
        self.roles = None

        
        # if self.token is not None:

    
    @property
    def is_authenticated(self) -> bool:
        """
        Returns True if the User is authenticated
        """
        return self.token is not None
    
    @property
    def display_name(self) -> Optional[str]:
        """
        Returns the User's Display Name
        """
        return self.token.display_name if self.is_authenticated else ""
    
    @property
    def email(self) -> Optional[str]:
        """
        Returns the User's Email
        """
        return self.token.email if self.is_authenticated else ""
    
    @property
    def identity(self) -> Optional[str]:
        """
        Returns the User's Identity
        """
        return self.token.identity if self.is_authenticated else ""
    
    async def alogout(self):
        """
        Logs the User Out
        """
        if not self.is_authenticated: return

    


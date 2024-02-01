from __future__ import annotations

from lazyops.types import BaseModel, Field
from typing import Optional, Dict, Any, Union, List

class SlackContext(BaseModel):
    """
    Holds the Slack Context
    """

    channels: Dict[str, str] = Field(default_factory = dict)
    users: Dict[str, str] = Field(default_factory = dict)
    user_info: Dict[str, Dict[str, Any]] = Field(default_factory = dict)
    user_lookup: Dict[str, str] = Field(default_factory = dict)
    uids: Dict[str, str] = Field(default_factory = dict)

    username_mapping: Optional[Dict[str, Union[str, List[str]]]] = Field(default_factory = dict)
    initialized: Optional[bool] = False
    
    def lookup_id(self, name: str) -> Optional[str]:
        """
        Lookup ID
        """
        return self.uids.get(name, self.users.get(name, self.channels.get(name)))

class SlackPayload(BaseModel):
    token: Optional[str] = None
    team_id: Optional[str] = None
    team_domain: Optional[str] = None
    enterprise_id: Optional[str] = None
    enterprise_name: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    command: Optional[str] = None
    text: Optional[str] = None
    response_url: Optional[str] = None
    trigger_id: Optional[str] = None
    api_app_id: Optional[str] = None
    

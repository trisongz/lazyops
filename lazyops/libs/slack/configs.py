from __future__ import annotations

import json
from pathlib import Path
from lazyops.types import BaseSettings
from typing import Optional, Dict, Any, List
from .types import SlackContext


lib_path = Path(__file__).parent
context_path = lib_path.joinpath('slack_context.json')


class SlackSettings(BaseSettings):
    """
    Slack Settings
    """

    webhook_url: Optional[str] = None
    bot_token: Optional[str] = None
    app_token: Optional[str] = None

    default_user: Optional[str] = None
    default_channel: Optional[str] = None
    cache_context: Optional[bool] = True

    class Config:
        env_prefix = 'SLACK_'
        case_sensitive = False

    def load_context(self) -> SlackContext:
        """
        Loads the Slack Context
        """
        if not context_path.exists(): return SlackContext()
        return SlackContext(
            **json.loads(context_path.read_text())
        )
    
    def save_context(self, context: SlackContext) -> None:
        """
        Saves the Slack Context
        """
        context_path.write_text(json.dumps(context.model_dump(), indent = 4))

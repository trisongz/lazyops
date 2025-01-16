from __future__ import annotations

import json
from lzl.io import File
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from .types import SlackContext


lib_path = Path(__file__).parent
context_path = lib_path.joinpath('slack_context.json')

if TYPE_CHECKING:
    from lzl.io import File

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
    context_file: Optional[File] = context_path

    class Config:
        env_prefix = 'SLACK_'
        case_sensitive = False
        extra = 'allow'

    def load_context(self, ctx_file: Optional[File] = None) -> SlackContext:
        """
        Loads the Slack Context
        """
        if ctx_file is not None:
            # assert ctx_file.exists(), f"Context File does not exist: {ctx_file}"
            self.context_file = ctx_file

        if not self.context_file.exists(): return SlackContext()
        return SlackContext(
            **json.loads(self.context_file.read_text())
        )
        # if not context_path.exists(): return SlackContext()
        # return SlackContext(
        #     **json.loads(context_path.read_text())
        # )
    
    def save_context(self, context: SlackContext) -> None:
        """
        Saves the Slack Context
        """
        self.context_file.write_text(json.dumps(context.model_dump(), indent = 4))
        # context_path.write_text(json.dumps(context.model_dump(), indent = 4))

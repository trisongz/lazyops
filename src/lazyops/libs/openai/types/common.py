from __future__ import annotations

from enum import Enum
from typing import Optional


class ApiType(str, Enum):
    azure = "azure"
    openai = "openai"
    open_ai = "openai"
    azure_ad = "azure_ad"
    azuread = "azure_ad"

    def get_version(
        self, 
        version: Optional[str] = None
    ):
        if self.value in {"azure", "azure_ad", "azuread"} and not version:
            return "2023-07-01-preview"
        return version

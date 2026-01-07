from __future__ import annotations

"""
Cloudflare Settings Configuration
"""

from pydantic_settings import BaseSettings
from typing import Optional


class CloudflareSettings(BaseSettings):
    """
    Cloudflare API Settings

    Environment variables:
        CLOUDFLARE_API_TOKEN: Bearer token for API authentication (preferred)
        CLOUDFLARE_API_KEY: Legacy Global API Key
        CLOUDFLARE_EMAIL: Email associated with API key (required for API key auth)
        CLOUDFLARE_ACCOUNT_ID: Default account ID
        CLOUDFLARE_ZONE_ID: Default zone ID (optional)
    """

    api_token: Optional[str] = None
    api_key: Optional[str] = None
    email: Optional[str] = None
    account_id: Optional[str] = None
    zone_id: Optional[str] = None
    base_url: str = "https://api.cloudflare.com/client/v4"

    class Config:
        env_prefix = "CLOUDFLARE_"
        case_sensitive = False
        extra = "allow"

    @property
    def has_auth(self) -> bool:
        """Check if valid authentication is configured"""
        return bool(self.api_token or (self.api_key and self.email))

    @property
    def auth_headers(self) -> dict:
        """
        Returns the appropriate authentication headers

        Prefers Bearer token over API key
        """
        if self.api_token:
            return {"Authorization": f"Bearer {self.api_token}"}
        elif self.api_key and self.email:
            return {
                "X-Auth-Key": self.api_key,
                "X-Auth-Email": self.email,
            }
        return {}

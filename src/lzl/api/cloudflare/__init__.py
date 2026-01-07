"""
Cloudflare API Client

This package provides a hybrid sync/async client for the Cloudflare API
with support for DNS record management.

Example usage:
    >>> from lzl.api.cloudflare import client
    >>>
    >>> # List zones
    >>> zones = client.list_zones()
    >>>
    >>> # List DNS records
    >>> records = client.dns.list(zone_id)
    >>>
    >>> # Declarative DNS management
    >>> records = [
    ...     {"dns_name": "email", "record_type": "MX", "targets": ["10 mail.server.com"]},
    ...     {"dns_name": "www", "record_type": "A", "targets": ["192.0.2.1"]},
    ... ]
    >>> result = client.apply_dns_records(records, root_domain="example.com")
    >>>
    >>> # Async usage
    >>> result = await client.aapply_dns_records(records, root_domain="example.com")
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from lzl.proxied import ProxyObject

from .configs import CloudflareSettings
from .client import CloudflareClient
from .types import RecordType, SyncMode, ZoneStatus
from .models import (
    DNSRecord,
    DNSRecordInput,
    DNSRecordOptions,
    Zone,
    ApplyResult,
    MultiZoneApplyResult,
    RecordChange,
)
from .resources import DNSResource
from .resources.dns import (
    GOOGLE_WORKSPACE_MX,
    SPF_GOOGLE,
    SPF_MICROSOFT,
    SPF_GOOGLE_AND_MICROSOFT,
)

__all__ = [
    # Settings
    "CloudflareSettings",
    # Client
    "CloudflareClient",
    # Types
    "RecordType",
    "SyncMode",
    "ZoneStatus",
    # Models
    "DNSRecord",
    "DNSRecordInput",
    "DNSRecordOptions",
    "Zone",
    "ApplyResult",
    "MultiZoneApplyResult",
    "RecordChange",
    # Resources
    "DNSResource",
    # Constants
    "GOOGLE_WORKSPACE_MX",
    "SPF_GOOGLE",
    "SPF_MICROSOFT",
    "SPF_GOOGLE_AND_MICROSOFT",
    # Singletons
    "settings",
    "client",
    "get_settings",
    "get_client",
]


def get_settings() -> CloudflareSettings:
    """Get the Cloudflare settings singleton"""
    return CloudflareSettings()


def get_client() -> CloudflareClient:
    """Get the Cloudflare client singleton"""
    return CloudflareClient()


# Module-level singletons using ProxyObject for lazy initialization
if TYPE_CHECKING:
    settings: CloudflareSettings
    client: CloudflareClient
else:
    settings: CloudflareSettings = ProxyObject(obj_getter=get_settings)
    client: CloudflareClient = ProxyObject(obj_getter=get_client)

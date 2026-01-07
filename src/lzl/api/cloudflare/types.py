from __future__ import annotations

"""
Cloudflare Type Definitions
"""

from enum import Enum
from typing import Literal


class RecordType(str, Enum):
    """DNS Record Types supported by Cloudflare"""
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    TXT = "TXT"
    NS = "NS"
    SRV = "SRV"
    CAA = "CAA"
    PTR = "PTR"
    SPF = "SPF"
    HTTPS = "HTTPS"
    SVCB = "SVCB"
    LOC = "LOC"
    CERT = "CERT"
    DNSKEY = "DNSKEY"
    DS = "DS"
    NAPTR = "NAPTR"
    SMIMEA = "SMIMEA"
    SSHFP = "SSHFP"
    TLSA = "TLSA"
    URI = "URI"


class SyncMode(str, Enum):
    """
    Sync modes for apply_dns_records

    upsert: Only create/update records, never delete (safe default)
    full: Full sync - deletes records not in the provided list (destructive)
    """
    UPSERT = "upsert"
    FULL = "full"


class ZoneStatus(str, Enum):
    """Zone status values"""
    ACTIVE = "active"
    PENDING = "pending"
    INITIALIZING = "initializing"
    MOVED = "moved"
    DELETED = "deleted"
    DEACTIVATED = "deactivated"
    READ_ONLY = "read only"


# Type aliases
SyncModeType = Literal["upsert", "full"]
TTLType = Literal["auto"] | int

from __future__ import annotations

"""
Cloudflare Pydantic Models
"""

import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from typing import Optional, Dict, Any, List, Union, Literal
from .types import RecordType, SyncMode, ZoneStatus


# ============================================================================
# Input Models (User-provided)
# ============================================================================

class DNSRecordOptions(BaseModel):
    """Options for DNS record configuration"""
    proxied: Optional[bool] = None
    ttl: Optional[Union[int, Literal["auto"]]] = None
    priority: Optional[int] = None
    comment: Optional[str] = None
    tags: Optional[List[str]] = None

    model_config = {"extra": "allow"}


class DNSRecordInput(BaseModel):
    """
    User-friendly input format for DNS records

    Supports both full DNS names and subdomain shorthand:
    - Full: {"dns_name": "email.hlxn.io", ...}
    - Short: {"dns_name": "email", ...} with root_domain="hlxn.io"
    """
    dns_name: str
    record_type: str
    targets: List[str]
    options: Optional[DNSRecordOptions] = None

    model_config = {"extra": "allow"}

    @field_validator("record_type", mode="before")
    @classmethod
    def normalize_record_type(cls, v: str) -> str:
        """Normalize record type to uppercase"""
        return v.upper() if isinstance(v, str) else v

    def expand_name(self, root_domain: Optional[str] = None) -> str:
        """
        Expand dns_name to full domain name

        If dns_name already contains dots and no root_domain specified,
        assume it's already a full name
        """
        if root_domain:
            if self.dns_name == "@" or self.dns_name == root_domain:
                return root_domain
            elif self.dns_name.endswith(f".{root_domain}"):
                return self.dns_name
            else:
                return f"{self.dns_name}.{root_domain}"
        return self.dns_name

    def parse_mx_priority(self, target: str) -> tuple[int, str]:
        """
        Parse MX priority from target string

        Formats supported:
        - "10 mail.server.com" -> (10, "mail.server.com")
        - "mail.server.com" with options.priority -> (priority, "mail.server.com")
        """
        if self.record_type == "MX":
            match = re.match(r"^(\d+)\s+(.+)$", target.strip())
            if match:
                return int(match.group(1)), match.group(2)
            elif self.options and self.options.priority is not None:
                return self.options.priority, target
            else:
                # Default priority
                return 10, target
        return 0, target

    def to_api_records(self, root_domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Convert to Cloudflare API format

        Returns a list because one input can expand to multiple records
        (e.g., multiple targets for MX records)
        """
        full_name = self.expand_name(root_domain)
        records = []

        for target in self.targets:
            record = {
                "type": self.record_type,
                "name": full_name,
            }

            # Handle MX priority
            if self.record_type == "MX":
                priority, content = self.parse_mx_priority(target)
                record["content"] = content
                record["priority"] = priority
            else:
                record["content"] = target

            # Add options
            if self.options:
                if self.options.proxied is not None:
                    record["proxied"] = self.options.proxied
                if self.options.ttl is not None:
                    record["ttl"] = 1 if self.options.ttl == "auto" else self.options.ttl
                if self.options.comment:
                    record["comment"] = self.options.comment
                if self.options.tags:
                    record["tags"] = self.options.tags

            records.append(record)

        return records


# ============================================================================
# API Response Models
# ============================================================================

class AccountInfo(BaseModel):
    """Account information from zone"""
    id: str
    name: Optional[str] = None

    model_config = {"extra": "allow"}


class Zone(BaseModel):
    """Cloudflare Zone model"""
    id: str
    name: str
    status: Optional[str] = None
    paused: Optional[bool] = None
    type: Optional[str] = None
    development_mode: Optional[int] = None
    name_servers: Optional[List[str]] = None
    original_name_servers: Optional[List[str]] = None
    original_registrar: Optional[str] = None
    original_dnshost: Optional[str] = None
    modified_on: Optional[datetime] = None
    created_on: Optional[datetime] = None
    activated_on: Optional[datetime] = None
    account: Optional[AccountInfo] = None

    model_config = {"extra": "allow"}


class DNSRecordMeta(BaseModel):
    """DNS Record metadata"""
    auto_added: Optional[bool] = None
    source: Optional[str] = None

    model_config = {"extra": "allow"}


class DNSRecord(BaseModel):
    """Cloudflare DNS Record model"""
    id: str
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    name: str
    type: str
    content: str
    proxiable: Optional[bool] = None
    proxied: Optional[bool] = None
    ttl: Optional[int] = None
    priority: Optional[int] = None
    locked: Optional[bool] = None
    comment: Optional[str] = None
    tags: Optional[List[str]] = None
    created_on: Optional[datetime] = None
    modified_on: Optional[datetime] = None
    meta: Optional[DNSRecordMeta] = None

    model_config = {"extra": "allow"}

    def matches(self, other: "DNSRecord") -> bool:
        """Check if two records match (same name, type, content)"""
        return (
            self.name == other.name
            and self.type == other.type
            and self.content == other.content
        )

    def matches_input(self, name: str, record_type: str, content: str) -> bool:
        """Check if record matches input parameters"""
        return (
            self.name == name
            and self.type == record_type
            and self.content == content
        )
    
    @model_validator(mode='after')
    def validate_dns_record(self, info: ValidationInfo) -> DNSRecord:
        """
        Validate DNS record fields after initialization
        """
        if info.context:
            if not self.zone_id and info.context.get("zone_id"):
                self.zone_id = info.context["zone_id"]
            if not self.zone_name:
                if info.context.get("zone_name"):
                    self.zone_name = info.context["zone_name"]
                elif info.context.get('cf') and self.zone_id and (zone_name := info.context['cf']._get_zone_name(self.zone_id)):
                    self.zone_name = zone_name
        return self
        


class APIResponse(BaseModel):
    """Base Cloudflare API response wrapper"""
    success: bool
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    result: Optional[Any] = None
    result_info: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


class ZoneListResponse(APIResponse):
    """Response for zone list endpoint"""
    result: Optional[List[Zone]] = None


class DNSRecordListResponse(APIResponse):
    """Response for DNS record list endpoint"""
    result: Optional[List[DNSRecord]] = None


class DNSRecordResponse(APIResponse):
    """Response for single DNS record endpoints"""
    result: Optional[DNSRecord] = None


class BatchResult(BaseModel):
    """Result from batch operations"""
    deletes: Optional[List[DNSRecord]] = None
    patches: Optional[List[DNSRecord]] = None
    puts: Optional[List[DNSRecord]] = None
    posts: Optional[List[DNSRecord]] = None

    model_config = {"extra": "allow"}


class BatchResponse(APIResponse):
    """Response for batch DNS record operations"""
    result: Optional[BatchResult] = None


# ============================================================================
# Apply Result Models
# ============================================================================

class RecordChange(BaseModel):
    """Represents a single record change"""
    action: Literal["create", "update", "delete"]
    name: str
    type: str
    content: str
    old_content: Optional[str] = None
    record_id: Optional[str] = None


class ApplyResult(BaseModel):
    """Result of apply_dns_records operation"""
    zone_id: str
    zone_name: str
    dry_run: bool = False
    sync_mode: str = "upsert"

    to_create: List[RecordChange] = Field(default_factory=list)
    to_update: List[RecordChange] = Field(default_factory=list)
    to_delete: List[RecordChange] = Field(default_factory=list)

    created: List[DNSRecord] = Field(default_factory=list)
    updated: List[DNSRecord] = Field(default_factory=list)
    deleted: List[DNSRecord] = Field(default_factory=list)

    errors: List[str] = Field(default_factory=list)

    @property
    def total_changes(self) -> int:
        """Total number of changes"""
        if self.dry_run:
            return len(self.to_create) + len(self.to_update) + len(self.to_delete)
        return len(self.created) + len(self.updated) + len(self.deleted)

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred"""
        return len(self.errors) > 0


class MultiZoneApplyResult(BaseModel):
    """Result of apply_dns_records across multiple zones"""
    results: List[ApplyResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    @property
    def total_changes(self) -> int:
        """Total changes across all zones"""
        return sum(r.total_changes for r in self.results)

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred"""
        return len(self.errors) > 0 or any(r.has_errors for r in self.results)

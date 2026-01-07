from __future__ import annotations

"""
DNS Resource - CRUD operations for Cloudflare DNS records
"""

import json
from typing import Optional, Dict, Any, List, Union, TYPE_CHECKING, Literal

from ..models import (
    DNSRecord,
    DNSRecordListResponse,
    DNSRecordResponse,
    BatchResponse,
    BatchResult,
)

if TYPE_CHECKING:
    from ..client import CloudflareClient
    from lzl.api import aiohttpx

# Common service provider MX records
GOOGLE_WORKSPACE_MX = [
    {"priority": 1, "content": "aspmx.l.google.com"},
    {"priority": 5, "content": "alt1.aspmx.l.google.com"},
    {"priority": 5, "content": "alt2.aspmx.l.google.com"},
    {"priority": 10, "content": "alt3.aspmx.l.google.com"},
    {"priority": 10, "content": "alt4.aspmx.l.google.com"},
]

MICROSOFT_365_MX = [
    # Priority 0, content is {domain}-com.mail.protection.outlook.com
    # Domain-specific, needs to be generated
]

# Common SPF records
SPF_GOOGLE = "v=spf1 include:_spf.google.com ~all"
SPF_MICROSOFT = "v=spf1 include:spf.protection.outlook.com ~all"
SPF_GOOGLE_AND_MICROSOFT = "v=spf1 include:_spf.google.com include:spf.protection.outlook.com ~all"



class DNSResource:
    """
    DNS Record operations for Cloudflare API

    Provides sync and async methods for CRUD operations on DNS records.
    """

    def __init__(self, cf: "CloudflareClient"):
        """
        Initialize DNS Resource

        Args:
            cf: CloudflareClient instance
        """
        self._cf = cf
        self._client = self._cf.http_client
        self._base_url = self._cf._base_url

    def _endpoint(self, zone_id: str, record_id: Optional[str] = None) -> str:
        """Build endpoint URL"""
        base = f"{self._base_url}/zones/{zone_id}/dns_records"
        if record_id:
            return f"{base}/{record_id}"
        return base

    # ========================================================================
    # Zone Resolution - Accept zone name or ID
    # ========================================================================

    def _resolve_zone_id(self, zone: str) -> str:
        """
        Resolve zone name or ID to zone ID

        Args:
            zone: Zone name (e.g., "example.com") or zone ID

        Returns:
            Zone ID

        Raises:
            ValueError: If zone not found
        """
        # Check if it's already an ID (in cache)
        if zone in self._cf._zone_id_cache:
            return zone

        # Check if it's a name (in cache)
        if zone in self._cf._zone_cache:
            return self._cf._zone_cache[zone].id

        # Fetch zone
        zone_obj = self._cf.get_zone(zone)
        if not zone_obj:
            raise ValueError(f"Zone not found: {zone}")
        return zone_obj.id

    async def _aresolve_zone_id(self, zone: str) -> str:
        """Async version of _resolve_zone_id()"""
        # Check if it's already an ID (in cache)
        if zone in self._cf._zone_id_cache:
            return zone

        # Check if it's a name (in cache)
        if zone in self._cf._zone_cache:
            return self._cf._zone_cache[zone].id

        # Fetch zone
        zone_obj = await self._cf.aget_zone(zone)
        if not zone_obj:
            raise ValueError(f"Zone not found: {zone}")
        return zone_obj.id

    def _expand_name(self, name: str, zone_id: str) -> str:
        """
        Expand record name to FQDN

        Args:
            name: Record name (subdomain or FQDN)
            zone_id: Zone ID

        Returns:
            Fully qualified domain name
        """
        zone_name = self._cf._get_zone_name(zone_id)
        if not zone_name:
            return name

        if name == "@" or name == zone_name:
            return zone_name
        elif name.endswith(f".{zone_name}"):
            return name
        else:
            return f"{name}.{zone_name}"

    # ========================================================================
    # List Records
    # ========================================================================

    def list(
        self,
        zone_id: str,
        *,
        name: Optional[str] = None,
        record_type: Optional[str] = None,
        content: Optional[str] = None,
        proxied: Optional[bool] = None,
        per_page: int = 100,
        page: int = 1,
        **kwargs,
    ) -> List[DNSRecord]:
        """
        List DNS records for a zone

        Args:
            zone_id: Zone identifier
            name: Filter by record name
            record_type: Filter by record type (A, AAAA, CNAME, etc.)
            content: Filter by content/value
            proxied: Filter by proxy status
            per_page: Number of records per page (max 5000)
            page: Page number

        Returns:
            List of DNS records
        """
        params: Dict[str, Any] = {"per_page": per_page, "page": page}
        if name:
            params["name"] = name
        if record_type:
            params["type"] = record_type
        if content:
            params["content"] = content
        if proxied is not None:
            params["proxied"] = proxied
        params.update(kwargs)

        response = self._client.get(self._endpoint(zone_id), params=params)
        response.raise_for_status()
        data = DNSRecordListResponse.model_validate(
            response.json(),
            context = {
                'zone_id': zone_id,
                'cf': self._cf,
            }
        )
        return data.result or []

    async def alist(
        self,
        zone_id: str,
        *,
        name: Optional[str] = None,
        record_type: Optional[str] = None,
        content: Optional[str] = None,
        proxied: Optional[bool] = None,
        per_page: int = 100,
        page: int = 1,
        **kwargs,
    ) -> List[DNSRecord]:
        """Async version of list()"""
        params: Dict[str, Any] = {"per_page": per_page, "page": page}
        if name:
            params["name"] = name
        if record_type:
            params["type"] = record_type
        if content:
            params["content"] = content
        if proxied is not None:
            params["proxied"] = proxied
        params.update(kwargs)

        response = await self._client.async_get(self._endpoint(zone_id), params=params)
        response.raise_for_status()
        data = DNSRecordListResponse.model_validate(
            response.json(),
            context = {
                'zone_id': zone_id,
                'cf': self._cf,
            }
        )
        return data.result or []

    def list_all(
        self,
        zone_id: str,
        *,
        name: Optional[str] = None,
        record_type: Optional[str] = None,
        **kwargs,
    ) -> List[DNSRecord]:
        """
        List all DNS records (handles pagination)

        Args:
            zone_id: Zone identifier
            name: Filter by record name
            record_type: Filter by record type

        Returns:
            List of all DNS records
        """
        all_records: List[DNSRecord] = []
        page = 1
        per_page = 1000

        while True:
            records = self.list(
                zone_id,
                name=name,
                record_type=record_type,
                per_page=per_page,
                page=page,
                **kwargs,
            )
            all_records.extend(records)
            if len(records) < per_page:
                break
            page += 1

        return all_records

    async def alist_all(
        self,
        zone_id: str,
        *,
        name: Optional[str] = None,
        record_type: Optional[str] = None,
        **kwargs,
    ) -> List[DNSRecord]:
        """Async version of list_all()"""
        all_records: List[DNSRecord] = []
        page = 1
        per_page = 1000

        while True:
            records = await self.alist(
                zone_id,
                name=name,
                record_type=record_type,
                per_page=per_page,
                page=page,
                **kwargs,
            )
            all_records.extend(records)
            if len(records) < per_page:
                break
            page += 1

        return all_records

    # ========================================================================
    # Get Record
    # ========================================================================

    def get(self, zone_id: str, record_id: str) -> Optional[DNSRecord]:
        """
        Get a specific DNS record

        Args:
            zone_id: Zone identifier
            record_id: Record identifier

        Returns:
            DNS record or None if not found
        """
        response = self._client.get(self._endpoint(zone_id, record_id))
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = DNSRecordResponse.model_validate(
            response.json(),
            context = {"zone_id": zone_id, "cf": self._cf}
        )
        return data.result

    async def aget(self, zone_id: str, record_id: str) -> Optional[DNSRecord]:
        """Async version of get()"""
        response = await self._client.async_get(self._endpoint(zone_id, record_id))
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = DNSRecordResponse.model_validate(
            response.json(),
            context = {"zone_id": zone_id, "cf": self._cf}
        )
        return data.result

    # ========================================================================
    # Create Record
    # ========================================================================

    def create(
        self,
        zone_id: str,
        record: Dict[str, Any],
    ) -> DNSRecord:
        """
        Create a new DNS record

        Args:
            zone_id: Zone identifier
            record: Record data (type, name, content, etc.)

        Returns:
            Created DNS record
        """
        response = self._client.post(self._endpoint(zone_id), json=record)
        response.raise_for_status()
        data = DNSRecordResponse.model_validate(response.json(), context = {"zone_id": zone_id, "cf": self._cf})
        return data.result

    async def acreate(
        self,
        zone_id: str,
        record: Dict[str, Any],
    ) -> DNSRecord:
        """Async version of create()"""
        response = await self._client.async_post(self._endpoint(zone_id), json=record)
        response.raise_for_status()
        data = DNSRecordResponse.model_validate(
            response.json(),
            context = {"zone_id": zone_id, "cf": self._cf}
        )
        return data.result

    # ========================================================================
    # Update Record
    # ========================================================================

    def update(
        self,
        zone_id: str,
        record_id: str,
        record: Dict[str, Any],
        *,
        partial: bool = False,
    ) -> DNSRecord:
        """
        Update a DNS record

        Args:
            zone_id: Zone identifier
            record_id: Record identifier
            record: Updated record data
            partial: If True, use PATCH (partial update), else PUT (full replace)

        Returns:
            Updated DNS record
        """
        if partial:
            response = self._client.patch(
                self._endpoint(zone_id, record_id), json=record
            )
        else:
            response = self._client.put(self._endpoint(zone_id, record_id), json=record)
        response.raise_for_status()
        data = DNSRecordResponse.model_validate(
            response.json(),
            context = {"zone_id": zone_id, "cf": self._cf}
        )
        return data.result

    async def aupdate(
        self,
        zone_id: str,
        record_id: str,
        record: Dict[str, Any],
        *,
        partial: bool = False,
    ) -> DNSRecord:
        """Async version of update()"""
        if partial:
            response = await self._client.async_patch(
                self._endpoint(zone_id, record_id), json=record
            )
        else:
            response = await self._client.async_put(
                self._endpoint(zone_id, record_id), json=record
            )
        response.raise_for_status()
        data = DNSRecordResponse.model_validate(
            response.json(),
            context = {"zone_id": zone_id, "cf": self._cf}
        )
        return data.result

    # ========================================================================
    # Delete Record
    # ========================================================================

    def delete(self, zone_id: str, record_id: str) -> bool:
        """
        Delete a DNS record

        Args:
            zone_id: Zone identifier
            record_id: Record identifier

        Returns:
            True if deleted successfully
        """
        response = self._client.delete(self._endpoint(zone_id, record_id))
        response.raise_for_status()
        data = response.json()
        return data.get("success", False)

    async def adelete(self, zone_id: str, record_id: str) -> bool:
        """Async version of delete()"""
        response = await self._client.async_delete(self._endpoint(zone_id, record_id))
        response.raise_for_status()
        data = response.json()
        return data.get("success", False)

    # ========================================================================
    # Batch Operations
    # ========================================================================

    def batch(
        self,
        zone_id: str,
        *,
        deletes: Optional[List[Dict[str, Any]]] = None,
        patches: Optional[List[Dict[str, Any]]] = None,
        puts: Optional[List[Dict[str, Any]]] = None,
        posts: Optional[List[Dict[str, Any]]] = None,
    ) -> BatchResult:
        """
        Batch DNS record operations

        Operations are executed in order: deletes -> patches -> puts -> posts

        Args:
            zone_id: Zone identifier
            deletes: Records to delete (requires id)
            patches: Records to patch (requires id + fields to update)
            puts: Records to fully replace (requires id + all fields)
            posts: Records to create (new records)

        Returns:
            BatchResult with affected records
        """
        payload: Dict[str, Any] = {}
        if deletes:
            payload["deletes"] = deletes
        if patches:
            payload["patches"] = patches
        if puts:
            payload["puts"] = puts
        if posts:
            payload["posts"] = posts

        response = self._client.post(f"{self._endpoint(zone_id)}/batch", json=payload)
        response.raise_for_status()
        data = BatchResponse.model_validate(response.json(), context={"zone_id": zone_id, "cf": self._cf})
        return data.result or BatchResult()

    async def abatch(
        self,
        zone_id: str,
        *,
        deletes: Optional[List[Dict[str, Any]]] = None,
        patches: Optional[List[Dict[str, Any]]] = None,
        puts: Optional[List[Dict[str, Any]]] = None,
        posts: Optional[List[Dict[str, Any]]] = None,
    ) -> BatchResult:
        """Async version of batch()"""
        payload: Dict[str, Any] = {}
        if deletes:
            payload["deletes"] = deletes
        if patches:
            payload["patches"] = patches
        if puts:
            payload["puts"] = puts
        if posts:
            payload["posts"] = posts

        response = await self._client.async_post(
            f"{self._endpoint(zone_id)}/batch", json=payload
        )
        response.raise_for_status()
        data = BatchResponse.model_validate(response.json(), context={"zone_id": zone_id, "cf": self._cf})
        return data.result or BatchResult()

    # ========================================================================
    # Upsert Operations
    # ========================================================================

    def upsert(
        self,
        zone_id: str,
        record: Dict[str, Any],
        *,
        match_content: bool = True,
    ) -> DNSRecord:
        """
        Create or update a DNS record

        Finds existing records by name and type, then either creates a new record
        or updates an existing one.

        Args:
            zone_id: Zone identifier
            record: Record data (must include type, name, content)
            match_content: If True, also match on content to find existing record.
                          If False, updates the first record with matching name/type.

        Returns:
            Created or updated DNS record
        """
        name = record.get("name")
        record_type = record.get("type")
        content = record.get("content")

        if not name or not record_type:
            raise ValueError("Record must include 'name' and 'type'")

        # Find existing records
        existing = self.list(zone_id, name=name, record_type=record_type)

        if match_content and content:
            # Find exact match including content
            for existing_record in existing:
                if existing_record.content == content:
                    # Update existing record
                    return self.update(zone_id, existing_record.id, record, partial=True)
            # No exact match, create new
            return self.create(zone_id, record)
        elif existing:
            # Update first matching record
            return self.update(zone_id, existing[0].id, record, partial=True)
        else:
            # Create new record
            return self.create(zone_id, record)

    async def aupsert(
        self,
        zone_id: str,
        record: Dict[str, Any],
        *,
        match_content: bool = True,
    ) -> DNSRecord:
        """Async version of upsert()"""
        name = record.get("name")
        record_type = record.get("type")
        content = record.get("content")

        if not name or not record_type:
            raise ValueError("Record must include 'name' and 'type'")

        # Find existing records
        existing = await self.alist(zone_id, name=name, record_type=record_type)

        if match_content and content:
            # Find exact match including content
            for existing_record in existing:
                if existing_record.content == content:
                    # Update existing record
                    return await self.aupdate(
                        zone_id, existing_record.id, record, partial=True
                    )
            # No exact match, create new
            return await self.acreate(zone_id, record)
        elif existing:
            # Update first matching record
            return await self.aupdate(zone_id, existing[0].id, record, partial=True)
        else:
            # Create new record
            return await self.acreate(zone_id, record)

    def upsert_many(
        self,
        zone_id: str,
        records: List[Dict[str, Any]],
        *,
        match_content: bool = True,
    ) -> List[DNSRecord]:
        """
        Upsert multiple DNS records

        More efficient than calling upsert() multiple times as it fetches
        existing records once and uses batch operations.

        Args:
            zone_id: Zone identifier
            records: List of record data
            match_content: If True, match on content to find existing records

        Returns:
            List of created/updated DNS records
        """
        if not records:
            return []

        # Fetch all existing records for efficiency
        existing = self.list_all(zone_id)
        existing_map: Dict[tuple, DNSRecord] = {}
        for r in existing:
            key = (r.name, r.type, r.content) if match_content else (r.name, r.type)
            if key not in existing_map:
                existing_map[key] = r

        # Categorize records
        to_create: List[Dict[str, Any]] = []
        to_update: List[Dict[str, Any]] = []

        for record in records:
            name = record.get("name")
            record_type = record.get("type")
            content = record.get("content")

            if match_content:
                key = (name, record_type, content)
            else:
                key = (name, record_type)

            if key in existing_map:
                to_update.append({**record, "id": existing_map[key].id})
            else:
                to_create.append(record)

        # Execute batch operation
        result = self.batch(
            zone_id,
            posts=to_create if to_create else None,
            patches=to_update if to_update else None,
        )

        results: List[DNSRecord] = []
        if result.posts:
            results.extend(result.posts)
        if result.patches:
            results.extend(result.patches)
        return results

    async def aupsert_many(
        self,
        zone_id: str,
        records: List[Dict[str, Any]],
        *,
        match_content: bool = True,
    ) -> List[DNSRecord]:
        """Async version of upsert_many()"""
        if not records:
            return []

        # Fetch all existing records for efficiency
        existing = await self.alist_all(zone_id)
        existing_map: Dict[tuple, DNSRecord] = {}
        for r in existing:
            key = (r.name, r.type, r.content) if match_content else (r.name, r.type)
            if key not in existing_map:
                existing_map[key] = r

        # Categorize records
        to_create: List[Dict[str, Any]] = []
        to_update: List[Dict[str, Any]] = []

        for record in records:
            name = record.get("name")
            record_type = record.get("type")
            content = record.get("content")

            if match_content:
                key = (name, record_type, content)
            else:
                key = (name, record_type)

            if key in existing_map:
                to_update.append({**record, "id": existing_map[key].id})
            else:
                to_create.append(record)

        # Execute batch operation
        result = await self.abatch(
            zone_id,
            posts=to_create if to_create else None,
            patches=to_update if to_update else None,
        )

        results: List[DNSRecord] = []
        if result.posts:
            results.extend(result.posts)
        if result.patches:
            results.extend(result.patches)
        return results

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def find_by_name_and_type(
        self,
        zone_id: str,
        name: str,
        record_type: str,
    ) -> List[DNSRecord]:
        """
        Find records by name and type

        Args:
            zone_id: Zone identifier
            name: Record name
            record_type: Record type

        Returns:
            List of matching records
        """
        return self.list(zone_id, name=name, record_type=record_type)

    async def afind_by_name_and_type(
        self,
        zone_id: str,
        name: str,
        record_type: str,
    ) -> List[DNSRecord]:
        """Async version of find_by_name_and_type()"""
        return await self.alist(zone_id, name=name, record_type=record_type)

    # ========================================================================
    # Record Type-Specific Helpers
    # ========================================================================

    def add_a_record(
        self,
        zone: str,
        name: str,
        ip: str,
        *,
        proxied: bool = False,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """
        Add an A record (IPv4)

        Args:
            zone: Zone name or ID
            name: Record name (subdomain or "@" for root)
            ip: IPv4 address
            proxied: Enable Cloudflare proxy
            ttl: Time to live (1 = auto)
            comment: Optional comment

        Returns:
            Created DNS record
        """
        zone_id = self._resolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "A",
            "name": full_name,
            "content": ip,
            "proxied": proxied,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return self.create(zone_id, record)

    async def aadd_a_record(
        self,
        zone: str,
        name: str,
        ip: str,
        *,
        proxied: bool = False,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """Async version of add_a_record()"""
        zone_id = await self._aresolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "A",
            "name": full_name,
            "content": ip,
            "proxied": proxied,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return await self.acreate(zone_id, record)

    def add_aaaa_record(
        self,
        zone: str,
        name: str,
        ip: str,
        *,
        proxied: bool = False,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """
        Add an AAAA record (IPv6)

        Args:
            zone: Zone name or ID
            name: Record name (subdomain or "@" for root)
            ip: IPv6 address
            proxied: Enable Cloudflare proxy
            ttl: Time to live (1 = auto)
            comment: Optional comment

        Returns:
            Created DNS record
        """
        zone_id = self._resolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "AAAA",
            "name": full_name,
            "content": ip,
            "proxied": proxied,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return self.create(zone_id, record)

    async def aadd_aaaa_record(
        self,
        zone: str,
        name: str,
        ip: str,
        *,
        proxied: bool = False,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """Async version of add_aaaa_record()"""
        zone_id = await self._aresolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "AAAA",
            "name": full_name,
            "content": ip,
            "proxied": proxied,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return await self.acreate(zone_id, record)

    def add_cname_record(
        self,
        zone: str,
        name: str,
        target: str,
        *,
        proxied: bool = False,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """
        Add a CNAME record

        Args:
            zone: Zone name or ID
            name: Record name (subdomain)
            target: Target domain
            proxied: Enable Cloudflare proxy
            ttl: Time to live (1 = auto)
            comment: Optional comment

        Returns:
            Created DNS record
        """
        zone_id = self._resolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "CNAME",
            "name": full_name,
            "content": target,
            "proxied": proxied,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return self.create(zone_id, record)

    async def aadd_cname_record(
        self,
        zone: str,
        name: str,
        target: str,
        *,
        proxied: bool = False,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """Async version of add_cname_record()"""
        zone_id = await self._aresolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "CNAME",
            "name": full_name,
            "content": target,
            "proxied": proxied,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return await self.acreate(zone_id, record)

    def add_mx_record(
        self,
        zone: str,
        name: str,
        mail_server: str,
        priority: int = 10,
        *,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """
        Add an MX record

        Args:
            zone: Zone name or ID
            name: Record name (usually "@" for root domain)
            mail_server: Mail server hostname
            priority: MX priority (lower = higher priority)
            ttl: Time to live (1 = auto)
            comment: Optional comment

        Returns:
            Created DNS record
        """
        zone_id = self._resolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "MX",
            "name": full_name,
            "content": mail_server,
            "priority": priority,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return self.create(zone_id, record)

    async def aadd_mx_record(
        self,
        zone: str,
        name: str,
        mail_server: str,
        priority: int = 10,
        *,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """Async version of add_mx_record()"""
        zone_id = await self._aresolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "MX",
            "name": full_name,
            "content": mail_server,
            "priority": priority,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return await self.acreate(zone_id, record)

    def add_txt_record(
        self,
        zone: str,
        name: str,
        content: str,
        *,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """
        Add a TXT record

        Args:
            zone: Zone name or ID
            name: Record name (subdomain or "@" for root)
            content: TXT record content
            ttl: Time to live (1 = auto)
            comment: Optional comment

        Returns:
            Created DNS record
        """
        zone_id = self._resolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "TXT",
            "name": full_name,
            "content": content,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return self.create(zone_id, record)

    async def aadd_txt_record(
        self,
        zone: str,
        name: str,
        content: str,
        *,
        ttl: int = 1,
        comment: Optional[str] = None,
    ) -> DNSRecord:
        """Async version of add_txt_record()"""
        zone_id = await self._aresolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)
        record = {
            "type": "TXT",
            "name": full_name,
            "content": content,
            "ttl": ttl,
        }
        if comment:
            record["comment"] = comment
        return await self.acreate(zone_id, record)

    # ========================================================================
    # Service Templates
    # ========================================================================

    def add_google_workspace_mx(
        self,
        zone: str,
        name: str = "@",
        *,
        ttl: int = 1,
        replace_existing: bool = True,
    ) -> List[DNSRecord]:
        """
        Add Google Workspace MX records

        Args:
            zone: Zone name or ID
            name: Record name (usually "@" for root domain)
            ttl: Time to live (1 = auto)
            replace_existing: If True, delete existing MX records first

        Returns:
            List of created MX records
        """
        zone_id = self._resolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)

        # Delete existing MX records if requested
        if replace_existing:
            existing = self.list(zone_id, name=full_name, record_type="MX")
            if existing:
                self.batch(zone_id, deletes=[{"id": r.id} for r in existing])

        # Create Google Workspace MX records
        records_to_create = []
        for mx in GOOGLE_WORKSPACE_MX:
            records_to_create.append({
                "type": "MX",
                "name": full_name,
                "content": mx["content"],
                "priority": mx["priority"],
                "ttl": ttl,
            })

        result = self.batch(zone_id, posts=records_to_create)
        return result.posts or []

    async def aadd_google_workspace_mx(
        self,
        zone: str,
        name: str = "@",
        *,
        ttl: int = 1,
        replace_existing: bool = True,
    ) -> List[DNSRecord]:
        """Async version of add_google_workspace_mx()"""
        zone_id = await self._aresolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)

        # Delete existing MX records if requested
        if replace_existing:
            existing = await self.alist(zone_id, name=full_name, record_type="MX")
            if existing:
                await self.abatch(zone_id, deletes=[{"id": r.id} for r in existing])

        # Create Google Workspace MX records
        records_to_create = []
        for mx in GOOGLE_WORKSPACE_MX:
            records_to_create.append({
                "type": "MX",
                "name": full_name,
                "content": mx["content"],
                "priority": mx["priority"],
                "ttl": ttl,
            })

        result = await self.abatch(zone_id, posts=records_to_create)
        return result.posts or []

    def add_microsoft_365_mx(
        self,
        zone: str,
        name: str = "@",
        *,
        ttl: int = 1,
        replace_existing: bool = True,
    ) -> List[DNSRecord]:
        """
        Add Microsoft 365 MX record

        Args:
            zone: Zone name or ID
            name: Record name (usually "@" for root domain)
            ttl: Time to live (1 = auto)
            replace_existing: If True, delete existing MX records first

        Returns:
            List of created MX records
        """
        zone_id = self._resolve_zone_id(zone)
        zone_name = self._cf._get_zone_name(zone_id) or zone
        full_name = self._expand_name(name, zone_id)

        # Delete existing MX records if requested
        if replace_existing:
            existing = self.list(zone_id, name=full_name, record_type="MX")
            if existing:
                self.batch(zone_id, deletes=[{"id": r.id} for r in existing])

        # Generate Microsoft 365 MX record
        # Format: {domain}-{tld}.mail.protection.outlook.com
        domain_parts = zone_name.replace(".", "-")
        mx_content = f"{domain_parts}.mail.protection.outlook.com"

        record = {
            "type": "MX",
            "name": full_name,
            "content": mx_content,
            "priority": 0,
            "ttl": ttl,
        }

        result = self.batch(zone_id, posts=[record])
        return result.posts or []

    async def aadd_microsoft_365_mx(
        self,
        zone: str,
        name: str = "@",
        *,
        ttl: int = 1,
        replace_existing: bool = True,
    ) -> List[DNSRecord]:
        """Async version of add_microsoft_365_mx()"""
        zone_id = await self._aresolve_zone_id(zone)
        zone_name = self._cf._get_zone_name(zone_id) or zone
        full_name = self._expand_name(name, zone_id)

        # Delete existing MX records if requested
        if replace_existing:
            existing = await self.alist(zone_id, name=full_name, record_type="MX")
            if existing:
                await self.abatch(zone_id, deletes=[{"id": r.id} for r in existing])

        # Generate Microsoft 365 MX record
        domain_parts = zone_name.replace(".", "-")
        mx_content = f"{domain_parts}.mail.protection.outlook.com"

        record = {
            "type": "MX",
            "name": full_name,
            "content": mx_content,
            "priority": 0,
            "ttl": ttl,
        }

        result = await self.abatch(zone_id, posts=[record])
        return result.posts or []

    def add_spf_record(
        self,
        zone: str,
        name: str = "@",
        *,
        providers: Optional[List[Literal["google", "microsoft", "custom"]]] = None,
        custom_includes: Optional[List[str]] = None,
        ip4: Optional[List[str]] = None,
        ip6: Optional[List[str]] = None,
        policy: Literal["~all", "-all", "?all", "+all"] = "~all",
        ttl: int = 1,
        replace_existing: bool = True,
    ) -> DNSRecord:
        """
        Add an SPF TXT record

        Args:
            zone: Zone name or ID
            name: Record name (usually "@" for root domain)
            providers: List of email providers ("google", "microsoft")
            custom_includes: Additional include mechanisms
            ip4: IPv4 addresses to authorize
            ip6: IPv6 addresses to authorize
            policy: SPF policy (~all=softfail, -all=fail, ?all=neutral, +all=pass)
            ttl: Time to live (1 = auto)
            replace_existing: If True, delete existing SPF records first

        Returns:
            Created SPF TXT record
        """
        zone_id = self._resolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)

        # Build SPF record
        spf_parts = ["v=spf1"]

        if providers:
            if "google" in providers:
                spf_parts.append("include:_spf.google.com")
            if "microsoft" in providers:
                spf_parts.append("include:spf.protection.outlook.com")

        if custom_includes:
            for inc in custom_includes:
                spf_parts.append(f"include:{inc}")

        if ip4:
            for ip in ip4:
                spf_parts.append(f"ip4:{ip}")

        if ip6:
            for ip in ip6:
                spf_parts.append(f"ip6:{ip}")

        spf_parts.append(policy)
        spf_content = " ".join(spf_parts)

        # Delete existing SPF records if requested
        if replace_existing:
            existing = self.list(zone_id, name=full_name, record_type="TXT")
            spf_records = [r for r in existing if r.content.startswith("v=spf1")]
            if spf_records:
                self.batch(zone_id, deletes=[{"id": r.id} for r in spf_records])

        return self.create(zone_id, {
            "type": "TXT",
            "name": full_name,
            "content": spf_content,
            "ttl": ttl,
        })

    async def aadd_spf_record(
        self,
        zone: str,
        name: str = "@",
        *,
        providers: Optional[List[Literal["google", "microsoft", "custom"]]] = None,
        custom_includes: Optional[List[str]] = None,
        ip4: Optional[List[str]] = None,
        ip6: Optional[List[str]] = None,
        policy: Literal["~all", "-all", "?all", "+all"] = "~all",
        ttl: int = 1,
        replace_existing: bool = True,
    ) -> DNSRecord:
        """Async version of add_spf_record()"""
        zone_id = await self._aresolve_zone_id(zone)
        full_name = self._expand_name(name, zone_id)

        # Build SPF record
        spf_parts = ["v=spf1"]

        if providers:
            if "google" in providers:
                spf_parts.append("include:_spf.google.com")
            if "microsoft" in providers:
                spf_parts.append("include:spf.protection.outlook.com")

        if custom_includes:
            for inc in custom_includes:
                spf_parts.append(f"include:{inc}")

        if ip4:
            for ip in ip4:
                spf_parts.append(f"ip4:{ip}")

        if ip6:
            for ip in ip6:
                spf_parts.append(f"ip6:{ip}")

        spf_parts.append(policy)
        spf_content = " ".join(spf_parts)

        # Delete existing SPF records if requested
        if replace_existing:
            existing = await self.alist(zone_id, name=full_name, record_type="TXT")
            spf_records = [r for r in existing if r.content.startswith("v=spf1")]
            if spf_records:
                await self.abatch(zone_id, deletes=[{"id": r.id} for r in spf_records])

        return await self.acreate(zone_id, {
            "type": "TXT",
            "name": full_name,
            "content": spf_content,
            "ttl": ttl,
        })

    def add_dmarc_record(
        self,
        zone: str,
        *,
        policy: Literal["none", "quarantine", "reject"] = "none",
        rua: Optional[str] = None,
        ruf: Optional[str] = None,
        pct: int = 100,
        ttl: int = 1,
        replace_existing: bool = True,
    ) -> DNSRecord:
        """
        Add a DMARC TXT record

        Args:
            zone: Zone name or ID
            policy: DMARC policy (none, quarantine, reject)
            rua: Aggregate report URI (email)
            ruf: Forensic report URI (email)
            pct: Percentage of messages to apply policy (1-100)
            ttl: Time to live (1 = auto)
            replace_existing: If True, delete existing DMARC record first

        Returns:
            Created DMARC TXT record
        """
        zone_id = self._resolve_zone_id(zone)
        zone_name = self._cf._get_zone_name(zone_id) or zone
        full_name = f"_dmarc.{zone_name}"

        # Build DMARC record
        dmarc_parts = [f"v=DMARC1", f"p={policy}"]

        if pct != 100:
            dmarc_parts.append(f"pct={pct}")

        if rua:
            # Ensure mailto: prefix
            rua_addr = rua if rua.startswith("mailto:") else f"mailto:{rua}"
            dmarc_parts.append(f"rua={rua_addr}")

        if ruf:
            ruf_addr = ruf if ruf.startswith("mailto:") else f"mailto:{ruf}"
            dmarc_parts.append(f"ruf={ruf_addr}")

        dmarc_content = "; ".join(dmarc_parts)

        # Delete existing DMARC record if requested
        if replace_existing:
            existing = self.list(zone_id, name=full_name, record_type="TXT")
            dmarc_records = [r for r in existing if r.content.startswith("v=DMARC1")]
            if dmarc_records:
                self.batch(zone_id, deletes=[{"id": r.id} for r in dmarc_records])

        return self.create(zone_id, {
            "type": "TXT",
            "name": full_name,
            "content": dmarc_content,
            "ttl": ttl,
        })

    async def aadd_dmarc_record(
        self,
        zone: str,
        *,
        policy: Literal["none", "quarantine", "reject"] = "none",
        rua: Optional[str] = None,
        ruf: Optional[str] = None,
        pct: int = 100,
        ttl: int = 1,
        replace_existing: bool = True,
    ) -> DNSRecord:
        """Async version of add_dmarc_record()"""
        zone_id = await self._aresolve_zone_id(zone)
        zone_name = self._cf._get_zone_name(zone_id) or zone
        full_name = f"_dmarc.{zone_name}"

        # Build DMARC record
        dmarc_parts = [f"v=DMARC1", f"p={policy}"]

        if pct != 100:
            dmarc_parts.append(f"pct={pct}")

        if rua:
            rua_addr = rua if rua.startswith("mailto:") else f"mailto:{rua}"
            dmarc_parts.append(f"rua={rua_addr}")

        if ruf:
            ruf_addr = ruf if ruf.startswith("mailto:") else f"mailto:{ruf}"
            dmarc_parts.append(f"ruf={ruf_addr}")

        dmarc_content = "; ".join(dmarc_parts)

        # Delete existing DMARC record if requested
        if replace_existing:
            existing = await self.alist(zone_id, name=full_name, record_type="TXT")
            dmarc_records = [r for r in existing if r.content.startswith("v=DMARC1")]
            if dmarc_records:
                await self.abatch(zone_id, deletes=[{"id": r.id} for r in dmarc_records])

        return await self.acreate(zone_id, {
            "type": "TXT",
            "name": full_name,
            "content": dmarc_content,
            "ttl": ttl,
        })

    # ========================================================================
    # Export / Import
    # ========================================================================

    def export_records(
        self,
        zone: str,
        *,
        format: Literal["json", "dict", "bind"] = "json",
        record_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None,
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        Export DNS records from a zone

        Args:
            zone: Zone name or ID
            format: Output format ("json", "dict", "bind")
            record_types: Only export these record types
            exclude_types: Exclude these record types

        Returns:
            Exported records as string (json/bind) or list of dicts
        """
        zone_id = self._resolve_zone_id(zone)
        zone_name = self._cf._get_zone_name(zone_id) or zone

        records = self.list_all(zone_id)

        # Filter by record types
        if record_types:
            records = [r for r in records if r.type in record_types]
        if exclude_types:
            records = [r for r in records if r.type not in exclude_types]

        # Convert to export format
        export_data = []
        for record in records:
            export_data.append({
                "name": record.name,
                "type": record.type,
                "content": record.content,
                "ttl": record.ttl,
                "proxied": record.proxied,
                "priority": record.priority,
                "comment": record.comment,
            })

        if format == "dict":
            return export_data
        elif format == "json":
            return json.dumps({"zone": zone_name, "records": export_data}, indent=2)
        elif format == "bind":
            # Generate BIND zone file format
            lines = [f"; Zone file export for {zone_name}", f"$ORIGIN {zone_name}."]
            for record in records:
                name = record.name
                if name == zone_name:
                    name = "@"
                elif name.endswith(f".{zone_name}"):
                    name = name[:-len(f".{zone_name}") - 1]

                ttl = record.ttl if record.ttl and record.ttl != 1 else ""
                if record.type == "MX":
                    lines.append(f"{name}\t{ttl}\tIN\t{record.type}\t{record.priority}\t{record.content}.")
                elif record.type in ("CNAME", "NS"):
                    lines.append(f"{name}\t{ttl}\tIN\t{record.type}\t{record.content}.")
                elif record.type == "TXT":
                    lines.append(f'{name}\t{ttl}\tIN\t{record.type}\t"{record.content}"')
                else:
                    lines.append(f"{name}\t{ttl}\tIN\t{record.type}\t{record.content}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Unknown format: {format}")

    async def aexport_records(
        self,
        zone: str,
        *,
        format: Literal["json", "dict", "bind"] = "json",
        record_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None,
    ) -> Union[str, List[Dict[str, Any]]]:
        """Async version of export_records()"""
        zone_id = await self._aresolve_zone_id(zone)
        zone_name = self._cf._get_zone_name(zone_id) or zone

        records = await self.alist_all(zone_id)

        # Filter by record types
        if record_types:
            records = [r for r in records if r.type in record_types]
        if exclude_types:
            records = [r for r in records if r.type not in exclude_types]

        # Convert to export format
        export_data = []
        for record in records:
            export_data.append({
                "name": record.name,
                "type": record.type,
                "content": record.content,
                "ttl": record.ttl,
                "proxied": record.proxied,
                "priority": record.priority,
                "comment": record.comment,
            })

        if format == "dict":
            return export_data
        elif format == "json":
            return json.dumps({"zone": zone_name, "records": export_data}, indent=2)
        elif format == "bind":
            lines = [f"; Zone file export for {zone_name}", f"$ORIGIN {zone_name}."]
            for record in records:
                name = record.name
                if name == zone_name:
                    name = "@"
                elif name.endswith(f".{zone_name}"):
                    name = name[:-len(f".{zone_name}") - 1]

                ttl = record.ttl if record.ttl and record.ttl != 1 else ""
                if record.type == "MX":
                    lines.append(f"{name}\t{ttl}\tIN\t{record.type}\t{record.priority}\t{record.content}.")
                elif record.type in ("CNAME", "NS"):
                    lines.append(f"{name}\t{ttl}\tIN\t{record.type}\t{record.content}.")
                elif record.type == "TXT":
                    lines.append(f'{name}\t{ttl}\tIN\t{record.type}\t"{record.content}"')
                else:
                    lines.append(f"{name}\t{ttl}\tIN\t{record.type}\t{record.content}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Unknown format: {format}")

    def import_records(
        self,
        zone: str,
        data: Union[str, List[Dict[str, Any]]],
        *,
        format: Literal["json", "dict"] = "json",
        merge: bool = True,
    ) -> List[DNSRecord]:
        """
        Import DNS records to a zone

        Args:
            zone: Zone name or ID
            data: Records data (JSON string or list of dicts)
            format: Input format ("json" or "dict")
            merge: If True, upsert records. If False, only create new records.

        Returns:
            List of created/updated records
        """
        zone_id = self._resolve_zone_id(zone)

        # Parse input
        if format == "json" and isinstance(data, str):
            parsed = json.loads(data)
            records_data = parsed.get("records", parsed) if isinstance(parsed, dict) else parsed
        else:
            records_data = data

        # Convert to API format
        records_to_import = []
        for rec in records_data:
            record = {
                "type": rec["type"],
                "name": rec["name"],
                "content": rec["content"],
            }
            if rec.get("ttl"):
                record["ttl"] = rec["ttl"]
            if rec.get("proxied") is not None:
                record["proxied"] = rec["proxied"]
            if rec.get("priority") is not None:
                record["priority"] = rec["priority"]
            if rec.get("comment"):
                record["comment"] = rec["comment"]
            records_to_import.append(record)

        if merge:
            return self.upsert_many(zone_id, records_to_import)
        else:
            result = self.batch(zone_id, posts=records_to_import)
            return result.posts or []

    async def aimport_records(
        self,
        zone: str,
        data: Union[str, List[Dict[str, Any]]],
        *,
        format: Literal["json", "dict"] = "json",
        merge: bool = True,
    ) -> List[DNSRecord]:
        """Async version of import_records()"""
        zone_id = await self._aresolve_zone_id(zone)

        # Parse input
        if format == "json" and isinstance(data, str):
            parsed = json.loads(data)
            records_data = parsed.get("records", parsed) if isinstance(parsed, dict) else parsed
        else:
            records_data = data

        # Convert to API format
        records_to_import = []
        for rec in records_data:
            record = {
                "type": rec["type"],
                "name": rec["name"],
                "content": rec["content"],
            }
            if rec.get("ttl"):
                record["ttl"] = rec["ttl"]
            if rec.get("proxied") is not None:
                record["proxied"] = rec["proxied"]
            if rec.get("priority") is not None:
                record["priority"] = rec["priority"]
            if rec.get("comment"):
                record["comment"] = rec["comment"]
            records_to_import.append(record)

        if merge:
            return await self.aupsert_many(zone_id, records_to_import)
        else:
            result = await self.abatch(zone_id, posts=records_to_import)
            return result.posts or []

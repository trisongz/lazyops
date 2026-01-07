from __future__ import annotations

"""
DNS Resource - CRUD operations for Cloudflare DNS records
"""

from typing import Optional, Dict, Any, List, Union, TYPE_CHECKING
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



class DNSResource:
    """
    DNS Record operations for Cloudflare API

    Provides sync and async methods for CRUD operations on DNS records.
    """

    def __init__(self, cf: "CloudflareClient"):
        """
        Initialize DNS Resource

        Args:
            client: aiohttpx Client instance
            base_url: Base URL for Cloudflare API
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

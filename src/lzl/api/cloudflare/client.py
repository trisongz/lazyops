from __future__ import annotations

"""
Cloudflare API Client

A hybrid sync/async client for the Cloudflare API with DNS record management.
"""

from collections import defaultdict
from lzl.api import aiohttpx
from lzl.logging import logger
from typing import Optional, Dict, Any, List, Union

from .configs import CloudflareSettings
from .types import SyncModeType
from .models import (
    Zone,
    ZoneListResponse,
    DNSRecordInput,
    DNSRecordOptions,
    RecordChange,
    ApplyResult,
    MultiZoneApplyResult,
)
from .resources import DNSResource

logger.set_module_name(__name__, "cloudflare.client")


class CloudflareClient:
    """
    Cloudflare API Client

    Provides sync and async methods for interacting with the Cloudflare API.
    Follows the pattern established by other lzl API clients (slack, openai).

    Example usage:
        >>> from lzl.api.cloudflare import client
        >>> zones = client.list_zones()
        >>> records = client.dns.list(zone_id)
        >>> result = await client.aapply_dns_records(records, root_domain="example.com")
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        api_key: Optional[str] = None,
        email: Optional[str] = None,
        account_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = 30.0,
        **kwargs,
    ):
        """
        Initialize Cloudflare client

        Args:
            api_token: Bearer API token (preferred auth method)
            api_key: Legacy Global API Key
            email: Email for API key auth
            account_id: Default account ID
            zone_id: Default zone ID
            base_url: API base URL (default: https://api.cloudflare.com/client/v4)
            timeout: Request timeout in seconds
            **kwargs: Additional kwargs passed to aiohttpx.Client
        """
        self.settings = CloudflareSettings()

        # Override settings with explicit parameters
        self._api_token = api_token or self.settings.api_token
        self._api_key = api_key or self.settings.api_key
        self._email = email or self.settings.email
        self._account_id = account_id or self.settings.account_id
        self._zone_id = zone_id or self.settings.zone_id
        self._base_url = base_url or self.settings.base_url
        self._timeout = timeout
        self._extra_kwargs = kwargs

        # Lazy initialized components
        self._http_client: Optional[aiohttpx.Client] = None
        self._dns: Optional[DNSResource] = None

        # Zone cache
        self._zone_cache: Dict[str, Zone] = {}  # name -> Zone
        self._zone_id_cache: Dict[str, Zone] = {}  # id -> Zone

        # Validation
        if not self.has_auth:
            logger.warning(
                "No Cloudflare authentication configured. "
                "Set CLOUDFLARE_API_TOKEN or CLOUDFLARE_API_KEY+CLOUDFLARE_EMAIL"
            )

    @property
    def has_auth(self) -> bool:
        """Check if valid authentication is configured"""
        return bool(self._api_token or (self._api_key and self._email))

    @property
    def auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        if self._api_token:
            return {"Authorization": f"Bearer {self._api_token}"}
        elif self._api_key and self._email:
            return {
                "X-Auth-Key": self._api_key,
                "X-Auth-Email": self._email,
            }
        return {}

    @property
    def http_client(self) -> aiohttpx.Client:
        """Get or create the HTTP client"""
        if self._http_client is None:
            headers = {
                "Content-Type": "application/json",
                **self.auth_headers,
            }
            self._http_client = aiohttpx.Client(
                base_url=self._base_url,
                headers=headers,
                timeout=self._timeout,
                disable_httpx_logger=True,
                **self._extra_kwargs,
            )
        return self._http_client

    @property
    def dns(self) -> DNSResource:
        """Get the DNS resource"""
        if self._dns is None: self._dns = DNSResource(self)
        return self._dns

    # ========================================================================
    # Zone Management
    # ========================================================================

    def _get_zone_id(
        self,
        zone_name: str,
    ) -> Optional[str]:
        """
        Attempts to fetch the zone id from the zone cache
        """
        if zone_name in self._zone_cache:
            return self._zone_cache[zone_name].id
        return None

    def _get_zone_name(
        self,
        zone_id: str,
    ) -> Optional[str]:
        """
        Attempts to fetch the zone name from the zone cache
        """
        if zone_id in self._zone_id_cache:
            return self._zone_id_cache[zone_id].name
        return None

    def list_zones(
        self,
        *,
        name: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 50,
        page: int = 1,
        **kwargs,
    ) -> List[Zone]:
        """
        List zones

        Args:
            name: Filter by zone name
            status: Filter by status (active, pending, etc.)
            per_page: Results per page
            page: Page number

        Returns:
            List of zones
        """
        params: Dict[str, Any] = {"per_page": per_page, "page": page}
        if name:
            params["name"] = name
        if status:
            params["status"] = status
        params.update(kwargs)

        response = self.http_client.get("/zones", params=params)
        response.raise_for_status()
        data = ZoneListResponse.model_validate(response.json())

        # Cache zones
        for zone in data.result or []:
            self._zone_cache[zone.name] = zone
            self._zone_id_cache[zone.id] = zone

        return data.result or []

    async def alist_zones(
        self,
        *,
        name: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 50,
        page: int = 1,
        **kwargs,
    ) -> List[Zone]:
        """Async version of list_zones()"""
        params: Dict[str, Any] = {"per_page": per_page, "page": page}
        if name:
            params["name"] = name
        if status:
            params["status"] = status
        params.update(kwargs)

        response = await self.http_client.async_get("/zones", params=params)
        response.raise_for_status()
        data = ZoneListResponse.model_validate(response.json())

        # Cache zones
        for zone in data.result or []:
            self._zone_cache[zone.name] = zone
            self._zone_id_cache[zone.id] = zone

        return data.result or []

    def get_zone(self, name_or_id: str) -> Optional[Zone]:
        """
        Get a zone by name or ID

        Args:
            name_or_id: Zone name (e.g., "example.com") or zone ID

        Returns:
            Zone if found, None otherwise
        """
        # Check cache first
        if name_or_id in self._zone_cache:
            return self._zone_cache[name_or_id]
        if name_or_id in self._zone_id_cache:
            return self._zone_id_cache[name_or_id]

        # Try to fetch by name
        zones = self.list_zones(name=name_or_id)
        if zones:
            return zones[0]

        # Try to fetch by ID
        response = self.http_client.get(f"/zones/{name_or_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        if data.get("success") and data.get("result"):
            zone = Zone.model_validate(data["result"])
            self._zone_cache[zone.name] = zone
            self._zone_id_cache[zone.id] = zone
            return zone
        return None

    async def aget_zone(self, name_or_id: str) -> Optional[Zone]:
        """Async version of get_zone()"""
        # Check cache first
        if name_or_id in self._zone_cache:
            return self._zone_cache[name_or_id]
        if name_or_id in self._zone_id_cache:
            return self._zone_id_cache[name_or_id]

        # Try to fetch by name
        zones = await self.alist_zones(name=name_or_id)
        if zones:
            return zones[0]

        # Try to fetch by ID
        response = await self.http_client.async_get(f"/zones/{name_or_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        if data.get("success") and data.get("result"):
            zone = Zone.model_validate(data["result"])
            self._zone_cache[zone.name] = zone
            self._zone_id_cache[zone.id] = zone
            return zone
        return None

    def get_zone_id(self, name_or_id: str) -> Optional[str]:
        """
        Get zone ID by name or ID

        Args:
            name_or_id: Zone name or ID

        Returns:
            Zone ID if found
        """
        zone = self.get_zone(name_or_id)
        return zone.id if zone else None

    async def aget_zone_id(self, name_or_id: str) -> Optional[str]:
        """Async version of get_zone_id()"""
        zone = await self.aget_zone(name_or_id)
        return zone.id if zone else None

    # ========================================================================
    # Zone Name Extraction
    # ========================================================================

    @staticmethod
    def extract_root_domain(fqdn: str) -> str:
        """
        Extract root domain from FQDN

        Simple implementation that assumes last two parts are the root domain.
        For more complex TLDs (co.uk, etc.), this may need enhancement.

        Args:
            fqdn: Fully qualified domain name

        Returns:
            Root domain (e.g., "example.com" from "sub.example.com")
        """
        parts = fqdn.rstrip(".").split(".")
        return fqdn.rstrip(".") if len(parts) <= 2 else ".".join(parts[-2:])

    # ========================================================================
    # Apply DNS Records
    # ========================================================================

    def apply_dns_records(
        self,
        records: List[Union[Dict[str, Any], DNSRecordInput]],
        *,
        root_domain: Optional[str] = None,
        sync_mode: SyncModeType = "upsert",
        dry_run: bool = False,
    ) -> MultiZoneApplyResult:
        """
        Apply DNS records declaratively

        Takes a list of desired records and syncs them with Cloudflare.

        Args:
            records: List of record definitions
            root_domain: If set, treats dns_name as subdomain of this domain
            sync_mode: "upsert" (add/update only) or "full" (delete missing)
            dry_run: If True, only compute changes without applying

        Returns:
            MultiZoneApplyResult with changes per zone
        """
        # Parse input records
        parsed_records = self._parse_input_records(records)

        # Group by zone
        zone_records = self._group_records_by_zone(parsed_records, root_domain)

        # Apply to each zone
        result = MultiZoneApplyResult()
        for zone_name, zone_inputs in zone_records.items():
            try:
                zone_result = self._apply_zone_records(
                    zone_name, zone_inputs, sync_mode, dry_run
                )
                result.results.append(zone_result)
            except Exception as e:
                result.errors.append(f"Error processing zone {zone_name}: {str(e)}")

        return result

    async def aapply_dns_records(
        self,
        records: List[Union[Dict[str, Any], DNSRecordInput]],
        *,
        root_domain: Optional[str] = None,
        sync_mode: SyncModeType = "upsert",
        dry_run: bool = False,
    ) -> MultiZoneApplyResult:
        """Async version of apply_dns_records()"""
        # Parse input records
        parsed_records = self._parse_input_records(records)

        # Group by zone
        zone_records = self._group_records_by_zone(parsed_records, root_domain)

        # Apply to each zone
        result = MultiZoneApplyResult()
        for zone_name, zone_inputs in zone_records.items():
            try:
                zone_result = await self._aapply_zone_records(
                    zone_name, zone_inputs, sync_mode, dry_run
                )
                result.results.append(zone_result)
            except Exception as e:
                result.errors.append(f"Error processing zone {zone_name}: {str(e)}")

        return result

    def _parse_input_records(
        self, records: List[Union[Dict[str, Any], DNSRecordInput]]
    ) -> List[DNSRecordInput]:
        """Parse input records to DNSRecordInput objects"""
        parsed = []
        for record in records:
            if isinstance(record, DNSRecordInput):
                parsed.append(record)
            else:
                # Convert dict to DNSRecordInput
                options = record.get("options")
                if options and isinstance(options, dict):
                    options = DNSRecordOptions.model_validate(options)
                parsed.append(
                    DNSRecordInput(
                        dns_name=record["dns_name"],
                        record_type=record["record_type"],
                        targets=record["targets"],
                        options=options,
                    )
                )
        return parsed

    def _group_records_by_zone(
        self,
        records: List[DNSRecordInput],
        root_domain: Optional[str],
    ) -> Dict[str, List[DNSRecordInput]]:
        """Group records by their zone"""
        zone_records: Dict[str, List[DNSRecordInput]] = defaultdict(list)

        for record in records:
            if root_domain:
                zone_name = root_domain
            else:
                # Extract zone from full DNS name
                full_name = record.dns_name
                zone_name = self.extract_root_domain(full_name)

            zone_records[zone_name].append(record)

        return dict(zone_records)

    def _apply_zone_records(
        self,
        zone_name: str,
        records: List[DNSRecordInput],
        sync_mode: SyncModeType,
        dry_run: bool,
    ) -> ApplyResult:
        """Apply records to a single zone (sync)"""
        # Get zone
        zone = self.get_zone(zone_name)
        if not zone:
            result = ApplyResult(
                zone_id="",
                zone_name=zone_name,
                dry_run=dry_run,
                sync_mode=sync_mode,
            )
            result.errors.append(f"Zone not found: {zone_name}")
            return result

        result = ApplyResult(
            zone_id=zone.id,
            zone_name=zone.name,
            dry_run=dry_run,
            sync_mode=sync_mode,
        )

        # Get existing records
        existing = self.dns.list_all(zone.id)
        existing_map = {(r.name, r.type, r.content): r for r in existing}

        # Build desired state
        desired_records: List[Dict[str, Any]] = []
        for record_input in records:
            api_records = record_input.to_api_records(root_domain=zone.name)
            desired_records.extend(api_records)

        desired_map = {(r["name"], r["type"], r["content"]): r for r in desired_records}

        # Compute diff
        to_create = []
        to_update = []
        to_delete = []

        # Find records to create or update
        for key, desired in desired_map.items():
            name, rtype, content = key
            if key in existing_map:
                # Check if update needed (compare relevant fields)
                existing_record = existing_map[key]
                needs_update = False

                if desired.get("proxied") is not None and desired["proxied"] != existing_record.proxied:
                    needs_update = True
                if desired.get("ttl") is not None and desired["ttl"] != existing_record.ttl:
                    needs_update = True
                if desired.get("priority") is not None and desired["priority"] != existing_record.priority:
                    needs_update = True

                if needs_update:
                    change = RecordChange(
                        action="update",
                        name=name,
                        type=rtype,
                        content=content,
                        record_id=existing_record.id,
                    )
                    to_update.append((change, {**desired, "id": existing_record.id}))
            else:
                # Create new record
                change = RecordChange(
                    action="create",
                    name=name,
                    type=rtype,
                    content=content,
                )
                to_create.append((change, desired))

        # Find records to delete (only in full sync mode)
        if sync_mode == "full":
            for key, existing_record in existing_map.items():
                name, rtype, content = key
                if key not in desired_map:
                    change = RecordChange(
                        action="delete",
                        name=name,
                        type=rtype,
                        content=content,
                        record_id=existing_record.id,
                    )
                    to_delete.append((change, existing_record))

        # Populate result with planned changes
        result.to_create = [c for c, _ in to_create]
        result.to_update = [c for c, _ in to_update]
        result.to_delete = [c for c, _ in to_delete]

        if dry_run:
            return result

        # Apply changes using batch API
        try:
            batch_result = self.dns.batch(
                zone.id,
                posts=[r for _, r in to_create] if to_create else None,
                patches=[r for _, r in to_update] if to_update else None,
                deletes=[{"id": r.id} for _, r in to_delete] if to_delete else None,
            )

            if batch_result.posts:
                result.created = batch_result.posts
            if batch_result.patches:
                result.updated = batch_result.patches
            if batch_result.deletes:
                result.deleted = batch_result.deletes

        except Exception as e:
            result.errors.append(f"Batch operation failed: {str(e)}")

        return result

    async def _aapply_zone_records(
        self,
        zone_name: str,
        records: List[DNSRecordInput],
        sync_mode: SyncModeType,
        dry_run: bool,
    ) -> ApplyResult:
        """Apply records to a single zone (async)"""
        # Get zone
        zone = await self.aget_zone(zone_name)
        if not zone:
            result = ApplyResult(
                zone_id="",
                zone_name=zone_name,
                dry_run=dry_run,
                sync_mode=sync_mode,
            )
            result.errors.append(f"Zone not found: {zone_name}")
            return result

        result = ApplyResult(
            zone_id=zone.id,
            zone_name=zone.name,
            dry_run=dry_run,
            sync_mode=sync_mode,
        )

        # Get existing records
        existing = await self.dns.alist_all(zone.id)
        existing_map = {(r.name, r.type, r.content): r for r in existing}

        # Build desired state
        desired_records: List[Dict[str, Any]] = []
        for record_input in records:
            api_records = record_input.to_api_records(root_domain=zone.name)
            desired_records.extend(api_records)

        desired_map = {(r["name"], r["type"], r["content"]): r for r in desired_records}

        # Compute diff
        to_create = []
        to_update = []
        to_delete = []

        # Find records to create or update
        for key, desired in desired_map.items():
            name, rtype, content = key
            if key in existing_map:
                # Check if update needed
                existing_record = existing_map[key]
                needs_update = False

                if desired.get("proxied") is not None and desired["proxied"] != existing_record.proxied:
                    needs_update = True
                if desired.get("ttl") is not None and desired["ttl"] != existing_record.ttl:
                    needs_update = True
                if desired.get("priority") is not None and desired["priority"] != existing_record.priority:
                    needs_update = True

                if needs_update:
                    change = RecordChange(
                        action="update",
                        name=name,
                        type=rtype,
                        content=content,
                        record_id=existing_record.id,
                    )
                    to_update.append((change, {**desired, "id": existing_record.id}))
            else:
                # Create new record
                change = RecordChange(
                    action="create",
                    name=name,
                    type=rtype,
                    content=content,
                )
                to_create.append((change, desired))

        # Find records to delete (only in full sync mode)
        if sync_mode == "full":
            for key, existing_record in existing_map.items():
                name, rtype, content = key
                if key not in desired_map:
                    change = RecordChange(
                        action="delete",
                        name=name,
                        type=rtype,
                        content=content,
                        record_id=existing_record.id,
                    )
                    to_delete.append((change, existing_record))

        # Populate result with planned changes
        result.to_create = [c for c, _ in to_create]
        result.to_update = [c for c, _ in to_update]
        result.to_delete = [c for c, _ in to_delete]

        if dry_run:
            return result

        # Apply changes using batch API
        try:
            batch_result = await self.dns.abatch(
                zone.id,
                posts=[r for _, r in to_create] if to_create else None,
                patches=[r for _, r in to_update] if to_update else None,
                deletes=[{"id": r.id} for _, r in to_delete] if to_delete else None,
            )

            if batch_result.posts:
                result.created = batch_result.posts
            if batch_result.patches:
                result.updated = batch_result.patches
            if batch_result.deletes:
                result.deleted = batch_result.deletes

        except Exception as e:
            result.errors.append(f"Batch operation failed: {str(e)}")

        return result

    # ========================================================================
    # Diff / Preview
    # ========================================================================

    def diff_dns_records(
        self,
        records: List[Union[Dict[str, Any], DNSRecordInput]],
        *,
        root_domain: Optional[str] = None,
        sync_mode: SyncModeType = "upsert",
    ) -> MultiZoneApplyResult:
        """
        Preview DNS record changes without applying them

        Computes the diff between desired and current state without making changes.
        This is a convenience wrapper around apply_dns_records with dry_run=True.

        Args:
            records: List of desired record definitions
            root_domain: If set, treats dns_name as subdomain of this domain
            sync_mode: "upsert" (add/update only) or "full" (delete missing)

        Returns:
            MultiZoneApplyResult with planned changes (to_create, to_update, to_delete)

        Example:
            >>> diff = client.diff_dns_records(records, root_domain="example.com")
            >>> for zone_result in diff.results:
            ...     print(f"Zone: {zone_result.zone_name}")
            ...     print(f"  Create: {len(zone_result.to_create)}")
            ...     print(f"  Update: {len(zone_result.to_update)}")
            ...     print(f"  Delete: {len(zone_result.to_delete)}")
        """
        return self.apply_dns_records(
            records,
            root_domain=root_domain,
            sync_mode=sync_mode,
            dry_run=True,
        )

    async def adiff_dns_records(
        self,
        records: List[Union[Dict[str, Any], DNSRecordInput]],
        *,
        root_domain: Optional[str] = None,
        sync_mode: SyncModeType = "upsert",
    ) -> MultiZoneApplyResult:
        """Async version of diff_dns_records()"""
        return await self.aapply_dns_records(
            records,
            root_domain=root_domain,
            sync_mode=sync_mode,
            dry_run=True,
        )

    def compare_zones(
        self,
        source_zone: str,
        target_zone: str,
        *,
        record_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compare DNS records between two zones

        Args:
            source_zone: Source zone name or ID
            target_zone: Target zone name or ID
            record_types: Only compare these record types

        Returns:
            Dict with comparison results:
            - only_in_source: Records only in source zone
            - only_in_target: Records only in target zone
            - different: Records with same name/type but different content
            - identical: Records that match exactly
        """
        source_id = self.get_zone_id(source_zone)
        target_id = self.get_zone_id(target_zone)

        if not source_id or not target_id:
            raise ValueError(f"Zone not found: {source_zone if not source_id else target_zone}")

        source_records = self.dns.list_all(source_id)
        target_records = self.dns.list_all(target_id)

        if record_types:
            source_records = [r for r in source_records if r.type in record_types]
            target_records = [r for r in target_records if r.type in record_types]

        # Build lookup maps (by relative name and type)
        source_zone_name = self._get_zone_name(source_id)
        target_zone_name = self._get_zone_name(target_id)

        def get_relative_name(record: Any, zone_name: str) -> str:
            if record.name == zone_name:
                return "@"
            elif record.name.endswith(f".{zone_name}"):
                return record.name[:-len(f".{zone_name}") - 1]
            return record.name

        source_map = {}
        for r in source_records:
            rel_name = get_relative_name(r, source_zone_name)
            key = (rel_name, r.type)
            if key not in source_map:
                source_map[key] = []
            source_map[key].append(r)

        target_map = {}
        for r in target_records:
            rel_name = get_relative_name(r, target_zone_name)
            key = (rel_name, r.type)
            if key not in target_map:
                target_map[key] = []
            target_map[key].append(r)

        # Compare
        only_in_source = []
        only_in_target = []
        different = []
        identical = []

        all_keys = set(source_map.keys()) | set(target_map.keys())

        for key in all_keys:
            source_recs = source_map.get(key, [])
            target_recs = target_map.get(key, [])

            if not target_recs:
                only_in_source.extend([{"name": r.name, "type": r.type, "content": r.content} for r in source_recs])
            elif not source_recs:
                only_in_target.extend([{"name": r.name, "type": r.type, "content": r.content} for r in target_recs])
            else:
                source_contents = {r.content for r in source_recs}
                target_contents = {r.content for r in target_recs}

                if source_contents == target_contents:
                    identical.extend([{"name": key[0], "type": key[1], "content": list(source_contents)}])
                else:
                    different.append({
                        "name": key[0],
                        "type": key[1],
                        "source_content": list(source_contents),
                        "target_content": list(target_contents),
                    })

        return {
            "only_in_source": only_in_source,
            "only_in_target": only_in_target,
            "different": different,
            "identical": identical,
            "source_zone": source_zone,
            "target_zone": target_zone,
        }

    async def acompare_zones(
        self,
        source_zone: str,
        target_zone: str,
        *,
        record_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Async version of compare_zones()"""
        source_id = await self.aget_zone_id(source_zone)
        target_id = await self.aget_zone_id(target_zone)

        if not source_id or not target_id:
            raise ValueError(f"Zone not found: {source_zone if not source_id else target_zone}")

        source_records = await self.dns.alist_all(source_id)
        target_records = await self.dns.alist_all(target_id)

        if record_types:
            source_records = [r for r in source_records if r.type in record_types]
            target_records = [r for r in target_records if r.type in record_types]

        # Build lookup maps
        source_zone_name = self._get_zone_name(source_id)
        target_zone_name = self._get_zone_name(target_id)

        def get_relative_name(record: Any, zone_name: str) -> str:
            if record.name == zone_name:
                return "@"
            elif record.name.endswith(f".{zone_name}"):
                return record.name[:-len(f".{zone_name}") - 1]
            return record.name

        source_map = {}
        for r in source_records:
            rel_name = get_relative_name(r, source_zone_name)
            key = (rel_name, r.type)
            if key not in source_map:
                source_map[key] = []
            source_map[key].append(r)

        target_map = {}
        for r in target_records:
            rel_name = get_relative_name(r, target_zone_name)
            key = (rel_name, r.type)
            if key not in target_map:
                target_map[key] = []
            target_map[key].append(r)

        # Compare
        only_in_source = []
        only_in_target = []
        different = []
        identical = []

        all_keys = set(source_map.keys()) | set(target_map.keys())

        for key in all_keys:
            source_recs = source_map.get(key, [])
            target_recs = target_map.get(key, [])

            if not target_recs:
                only_in_source.extend([{"name": r.name, "type": r.type, "content": r.content} for r in source_recs])
            elif not source_recs:
                only_in_target.extend([{"name": r.name, "type": r.type, "content": r.content} for r in target_recs])
            else:
                source_contents = {r.content for r in source_recs}
                target_contents = {r.content for r in target_recs}

                if source_contents == target_contents:
                    identical.extend([{"name": key[0], "type": key[1], "content": list(source_contents)}])
                else:
                    different.append({
                        "name": key[0],
                        "type": key[1],
                        "source_content": list(source_contents),
                        "target_content": list(target_contents),
                    })

        return {
            "only_in_source": only_in_source,
            "only_in_target": only_in_target,
            "different": different,
            "identical": identical,
            "source_zone": source_zone,
            "target_zone": target_zone,
        }

    # ========================================================================
    # Cleanup
    # ========================================================================

    def close(self):
        """Close the HTTP client"""
        if self._http_client:
            self._http_client.close()
            self._http_client = None

    async def aclose(self):
        """Async close the HTTP client"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()

"""
Cloudflare MCP Server Implementation

Exposes Cloudflare DNS management functionality as MCP tools.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional, List, Literal

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from ..client import CloudflareClient
from ..models import DNSRecordInput

# Global client instance
_client: Optional[CloudflareClient] = None


def get_client() -> CloudflareClient:
    """Get or create the Cloudflare client singleton"""
    global _client
    if _client is None:
        _client = CloudflareClient()
        if not _client.has_auth:
            raise ValueError(
                "Cloudflare authentication not configured. "
                "Set CLOUDFLARE_API_TOKEN or CLOUDFLARE_API_KEY+CLOUDFLARE_EMAIL environment variables."
            )
    return _client


def create_server() -> Server:
    """Create and configure the MCP server"""
    server = Server("cloudflare-dns")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available Cloudflare DNS tools"""
        return [
            # Zone Management
            Tool(
                name="cloudflare_list_zones",
                description="List all Cloudflare zones (domains) in the account",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Filter zones by name (optional)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by status: active, pending, etc. (optional)",
                        },
                    },
                },
            ),
            Tool(
                name="cloudflare_get_zone",
                description="Get details for a specific zone by name or ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name (e.g., 'example.com') or zone ID",
                        },
                    },
                    "required": ["zone"],
                },
            ),
            # DNS Record Listing
            Tool(
                name="cloudflare_list_records",
                description="List DNS records for a zone",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Filter by record name (optional)",
                        },
                        "record_type": {
                            "type": "string",
                            "description": "Filter by type: A, AAAA, CNAME, MX, TXT, etc. (optional)",
                        },
                    },
                    "required": ["zone"],
                },
            ),
            # Record Type Helpers
            Tool(
                name="cloudflare_add_a_record",
                description="Add an A record (IPv4 address) to a zone",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Record name (subdomain or '@' for root)",
                        },
                        "ip": {
                            "type": "string",
                            "description": "IPv4 address",
                        },
                        "proxied": {
                            "type": "boolean",
                            "description": "Enable Cloudflare proxy (default: false)",
                            "default": False,
                        },
                        "ttl": {
                            "type": "integer",
                            "description": "Time to live in seconds (1 = auto)",
                            "default": 1,
                        },
                        "comment": {
                            "type": "string",
                            "description": "Optional comment",
                        },
                    },
                    "required": ["zone", "name", "ip"],
                },
            ),
            Tool(
                name="cloudflare_add_aaaa_record",
                description="Add an AAAA record (IPv6 address) to a zone",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Record name (subdomain or '@' for root)",
                        },
                        "ip": {
                            "type": "string",
                            "description": "IPv6 address",
                        },
                        "proxied": {
                            "type": "boolean",
                            "description": "Enable Cloudflare proxy (default: false)",
                            "default": False,
                        },
                        "ttl": {
                            "type": "integer",
                            "description": "Time to live in seconds (1 = auto)",
                            "default": 1,
                        },
                    },
                    "required": ["zone", "name", "ip"],
                },
            ),
            Tool(
                name="cloudflare_add_cname_record",
                description="Add a CNAME record to a zone",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Record name (subdomain)",
                        },
                        "target": {
                            "type": "string",
                            "description": "Target domain",
                        },
                        "proxied": {
                            "type": "boolean",
                            "description": "Enable Cloudflare proxy (default: false)",
                            "default": False,
                        },
                        "ttl": {
                            "type": "integer",
                            "description": "Time to live in seconds (1 = auto)",
                            "default": 1,
                        },
                    },
                    "required": ["zone", "name", "target"],
                },
            ),
            Tool(
                name="cloudflare_add_mx_record",
                description="Add an MX record (mail server) to a zone",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Record name (usually '@' for root domain)",
                        },
                        "mail_server": {
                            "type": "string",
                            "description": "Mail server hostname",
                        },
                        "priority": {
                            "type": "integer",
                            "description": "MX priority (lower = higher priority)",
                            "default": 10,
                        },
                        "ttl": {
                            "type": "integer",
                            "description": "Time to live in seconds (1 = auto)",
                            "default": 1,
                        },
                    },
                    "required": ["zone", "name", "mail_server"],
                },
            ),
            Tool(
                name="cloudflare_add_txt_record",
                description="Add a TXT record to a zone",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Record name (subdomain or '@' for root)",
                        },
                        "content": {
                            "type": "string",
                            "description": "TXT record content",
                        },
                        "ttl": {
                            "type": "integer",
                            "description": "Time to live in seconds (1 = auto)",
                            "default": 1,
                        },
                    },
                    "required": ["zone", "name", "content"],
                },
            ),
            # Service Templates
            Tool(
                name="cloudflare_add_google_workspace_mx",
                description="Add Google Workspace MX records (all 5 records with correct priorities)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Record name (usually '@' for root domain)",
                            "default": "@",
                        },
                        "replace_existing": {
                            "type": "boolean",
                            "description": "Delete existing MX records first (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["zone"],
                },
            ),
            Tool(
                name="cloudflare_add_microsoft_365_mx",
                description="Add Microsoft 365 MX record (auto-generates domain-specific endpoint)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Record name (usually '@' for root domain)",
                            "default": "@",
                        },
                        "replace_existing": {
                            "type": "boolean",
                            "description": "Delete existing MX records first (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["zone"],
                },
            ),
            Tool(
                name="cloudflare_add_spf_record",
                description="Add an SPF TXT record for email authentication",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Record name (usually '@' for root domain)",
                            "default": "@",
                        },
                        "providers": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["google", "microsoft"]},
                            "description": "Email providers to include (google, microsoft)",
                        },
                        "custom_includes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Additional SPF include mechanisms",
                        },
                        "ip4": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IPv4 addresses to authorize",
                        },
                        "ip6": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IPv6 addresses to authorize",
                        },
                        "policy": {
                            "type": "string",
                            "enum": ["~all", "-all", "?all", "+all"],
                            "description": "SPF policy: ~all (softfail), -all (fail), ?all (neutral), +all (pass)",
                            "default": "~all",
                        },
                        "replace_existing": {
                            "type": "boolean",
                            "description": "Delete existing SPF records first (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["zone"],
                },
            ),
            Tool(
                name="cloudflare_add_dmarc_record",
                description="Add a DMARC TXT record for email authentication",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "policy": {
                            "type": "string",
                            "enum": ["none", "quarantine", "reject"],
                            "description": "DMARC policy",
                            "default": "none",
                        },
                        "rua": {
                            "type": "string",
                            "description": "Aggregate report email address",
                        },
                        "ruf": {
                            "type": "string",
                            "description": "Forensic report email address",
                        },
                        "pct": {
                            "type": "integer",
                            "description": "Percentage of messages to apply policy (1-100)",
                            "default": 100,
                        },
                        "replace_existing": {
                            "type": "boolean",
                            "description": "Delete existing DMARC record first (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["zone"],
                },
            ),
            # CRUD Operations
            Tool(
                name="cloudflare_create_record",
                description="Create a DNS record with full control over all parameters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "type": {
                            "type": "string",
                            "description": "Record type: A, AAAA, CNAME, MX, TXT, NS, SRV, etc.",
                        },
                        "name": {
                            "type": "string",
                            "description": "Record name (FQDN or subdomain)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Record content/value",
                        },
                        "ttl": {
                            "type": "integer",
                            "description": "Time to live in seconds (1 = auto)",
                            "default": 1,
                        },
                        "proxied": {
                            "type": "boolean",
                            "description": "Enable Cloudflare proxy",
                        },
                        "priority": {
                            "type": "integer",
                            "description": "Priority for MX/SRV records",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Optional comment",
                        },
                    },
                    "required": ["zone", "type", "name", "content"],
                },
            ),
            Tool(
                name="cloudflare_update_record",
                description="Update an existing DNS record",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "record_id": {
                            "type": "string",
                            "description": "Record ID to update",
                        },
                        "content": {
                            "type": "string",
                            "description": "New content/value",
                        },
                        "ttl": {
                            "type": "integer",
                            "description": "New TTL",
                        },
                        "proxied": {
                            "type": "boolean",
                            "description": "Enable/disable Cloudflare proxy",
                        },
                        "comment": {
                            "type": "string",
                            "description": "New comment",
                        },
                    },
                    "required": ["zone", "record_id"],
                },
            ),
            Tool(
                name="cloudflare_delete_record",
                description="Delete a DNS record",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "record_id": {
                            "type": "string",
                            "description": "Record ID to delete",
                        },
                    },
                    "required": ["zone", "record_id"],
                },
            ),
            # Export/Import
            Tool(
                name="cloudflare_export_records",
                description="Export DNS records from a zone",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["json", "bind"],
                            "description": "Output format: json or bind (zone file)",
                            "default": "json",
                        },
                        "record_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Only export these record types (optional)",
                        },
                        "exclude_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Exclude these record types (optional)",
                        },
                    },
                    "required": ["zone"],
                },
            ),
            Tool(
                name="cloudflare_import_records",
                description="Import DNS records to a zone from JSON",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID",
                        },
                        "records": {
                            "type": "array",
                            "description": "Array of record objects with name, type, content",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                    "content": {"type": "string"},
                                    "ttl": {"type": "integer"},
                                    "proxied": {"type": "boolean"},
                                    "priority": {"type": "integer"},
                                },
                                "required": ["name", "type", "content"],
                            },
                        },
                        "merge": {
                            "type": "boolean",
                            "description": "If true, upsert records. If false, only create new.",
                            "default": True,
                        },
                    },
                    "required": ["zone", "records"],
                },
            ),
            # Diff/Preview
            Tool(
                name="cloudflare_diff_records",
                description="Preview DNS record changes without applying them",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID (required if using subdomain shorthand)",
                        },
                        "records": {
                            "type": "array",
                            "description": "Desired records in declarative format",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dns_name": {"type": "string", "description": "Subdomain or FQDN"},
                                    "record_type": {"type": "string", "description": "A, CNAME, MX, TXT, etc."},
                                    "targets": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Record values/targets",
                                    },
                                    "options": {
                                        "type": "object",
                                        "description": "Optional: proxied, ttl, priority, comment",
                                    },
                                },
                                "required": ["dns_name", "record_type", "targets"],
                            },
                        },
                        "sync_mode": {
                            "type": "string",
                            "enum": ["upsert", "full"],
                            "description": "upsert = add/update only, full = also delete missing records",
                            "default": "upsert",
                        },
                    },
                    "required": ["records"],
                },
            ),
            Tool(
                name="cloudflare_compare_zones",
                description="Compare DNS records between two zones",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_zone": {
                            "type": "string",
                            "description": "Source zone name or ID",
                        },
                        "target_zone": {
                            "type": "string",
                            "description": "Target zone name or ID",
                        },
                        "record_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Only compare these record types (optional)",
                        },
                    },
                    "required": ["source_zone", "target_zone"],
                },
            ),
            # Apply (Declarative)
            Tool(
                name="cloudflare_apply_records",
                description="Apply DNS records declaratively (create, update, optionally delete to match desired state)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "zone": {
                            "type": "string",
                            "description": "Zone name or ID (required if using subdomain shorthand)",
                        },
                        "records": {
                            "type": "array",
                            "description": "Desired records in declarative format",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dns_name": {"type": "string", "description": "Subdomain or FQDN"},
                                    "record_type": {"type": "string", "description": "A, CNAME, MX, TXT, etc."},
                                    "targets": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Record values/targets",
                                    },
                                    "options": {
                                        "type": "object",
                                        "description": "Optional: proxied, ttl, priority, comment",
                                    },
                                },
                                "required": ["dns_name", "record_type", "targets"],
                            },
                        },
                        "sync_mode": {
                            "type": "string",
                            "enum": ["upsert", "full"],
                            "description": "upsert = add/update only (safe), full = delete records not in list (destructive)",
                            "default": "upsert",
                        },
                    },
                    "required": ["records"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls"""
        try:
            client = get_client()
            result = await _handle_tool(client, name, arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    return server


async def _handle_tool(client: CloudflareClient, name: str, args: dict[str, Any]) -> Any:
    """Route tool calls to appropriate handlers"""

    # Zone Management
    if name == "cloudflare_list_zones":
        zones = await client.alist_zones(
            name=args.get("name"),
            status=args.get("status"),
        )
        return [{"id": z.id, "name": z.name, "status": z.status} for z in zones]

    elif name == "cloudflare_get_zone":
        zone = await client.aget_zone(args["zone"])
        if zone:
            return {
                "id": zone.id,
                "name": zone.name,
                "status": zone.status,
                "name_servers": zone.name_servers,
                "created_on": zone.created_on,
            }
        return {"error": f"Zone not found: {args['zone']}"}

    # DNS Record Listing
    elif name == "cloudflare_list_records":
        zone_id = await client.aget_zone_id(args["zone"])
        if not zone_id:
            return {"error": f"Zone not found: {args['zone']}"}

        records = await client.dns.alist_all(
            zone_id,
            name=args.get("name"),
            record_type=args.get("record_type"),
        )
        return [
            {
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "content": r.content,
                "ttl": r.ttl,
                "proxied": r.proxied,
                "priority": r.priority,
            }
            for r in records
        ]

    # Record Type Helpers
    elif name == "cloudflare_add_a_record":
        record = await client.dns.aadd_a_record(
            args["zone"],
            args["name"],
            args["ip"],
            proxied=args.get("proxied", False),
            ttl=args.get("ttl", 1),
            comment=args.get("comment"),
        )
        return {"success": True, "record": _record_to_dict(record)}

    elif name == "cloudflare_add_aaaa_record":
        record = await client.dns.aadd_aaaa_record(
            args["zone"],
            args["name"],
            args["ip"],
            proxied=args.get("proxied", False),
            ttl=args.get("ttl", 1),
        )
        return {"success": True, "record": _record_to_dict(record)}

    elif name == "cloudflare_add_cname_record":
        record = await client.dns.aadd_cname_record(
            args["zone"],
            args["name"],
            args["target"],
            proxied=args.get("proxied", False),
            ttl=args.get("ttl", 1),
        )
        return {"success": True, "record": _record_to_dict(record)}

    elif name == "cloudflare_add_mx_record":
        record = await client.dns.aadd_mx_record(
            args["zone"],
            args["name"],
            args["mail_server"],
            priority=args.get("priority", 10),
            ttl=args.get("ttl", 1),
        )
        return {"success": True, "record": _record_to_dict(record)}

    elif name == "cloudflare_add_txt_record":
        record = await client.dns.aadd_txt_record(
            args["zone"],
            args["name"],
            args["content"],
            ttl=args.get("ttl", 1),
        )
        return {"success": True, "record": _record_to_dict(record)}

    # Service Templates
    elif name == "cloudflare_add_google_workspace_mx":
        records = await client.dns.aadd_google_workspace_mx(
            args["zone"],
            name=args.get("name", "@"),
            replace_existing=args.get("replace_existing", True),
        )
        return {"success": True, "records": [_record_to_dict(r) for r in records]}

    elif name == "cloudflare_add_microsoft_365_mx":
        records = await client.dns.aadd_microsoft_365_mx(
            args["zone"],
            name=args.get("name", "@"),
            replace_existing=args.get("replace_existing", True),
        )
        return {"success": True, "records": [_record_to_dict(r) for r in records]}

    elif name == "cloudflare_add_spf_record":
        record = await client.dns.aadd_spf_record(
            args["zone"],
            name=args.get("name", "@"),
            providers=args.get("providers"),
            custom_includes=args.get("custom_includes"),
            ip4=args.get("ip4"),
            ip6=args.get("ip6"),
            policy=args.get("policy", "~all"),
            replace_existing=args.get("replace_existing", True),
        )
        return {"success": True, "record": _record_to_dict(record)}

    elif name == "cloudflare_add_dmarc_record":
        record = await client.dns.aadd_dmarc_record(
            args["zone"],
            policy=args.get("policy", "none"),
            rua=args.get("rua"),
            ruf=args.get("ruf"),
            pct=args.get("pct", 100),
            replace_existing=args.get("replace_existing", True),
        )
        return {"success": True, "record": _record_to_dict(record)}

    # CRUD Operations
    elif name == "cloudflare_create_record":
        zone_id = await client.aget_zone_id(args["zone"])
        if not zone_id:
            return {"error": f"Zone not found: {args['zone']}"}

        record_data = {
            "type": args["type"],
            "name": args["name"],
            "content": args["content"],
        }
        if args.get("ttl"):
            record_data["ttl"] = args["ttl"]
        if args.get("proxied") is not None:
            record_data["proxied"] = args["proxied"]
        if args.get("priority") is not None:
            record_data["priority"] = args["priority"]
        if args.get("comment"):
            record_data["comment"] = args["comment"]

        record = await client.dns.acreate(zone_id, record_data)
        return {"success": True, "record": _record_to_dict(record)}

    elif name == "cloudflare_update_record":
        zone_id = await client.aget_zone_id(args["zone"])
        if not zone_id:
            return {"error": f"Zone not found: {args['zone']}"}

        update_data = {}
        if args.get("content"):
            update_data["content"] = args["content"]
        if args.get("ttl"):
            update_data["ttl"] = args["ttl"]
        if args.get("proxied") is not None:
            update_data["proxied"] = args["proxied"]
        if args.get("comment"):
            update_data["comment"] = args["comment"]

        record = await client.dns.aupdate(zone_id, args["record_id"], update_data, partial=True)
        return {"success": True, "record": _record_to_dict(record)}

    elif name == "cloudflare_delete_record":
        zone_id = await client.aget_zone_id(args["zone"])
        if not zone_id:
            return {"error": f"Zone not found: {args['zone']}"}

        success = await client.dns.adelete(zone_id, args["record_id"])
        return {"success": success}

    # Export/Import
    elif name == "cloudflare_export_records":
        result = await client.dns.aexport_records(
            args["zone"],
            format=args.get("format", "json"),
            record_types=args.get("record_types"),
            exclude_types=args.get("exclude_types"),
        )
        if isinstance(result, str):
            return {"format": args.get("format", "json"), "data": result}
        return {"format": "dict", "records": result}

    elif name == "cloudflare_import_records":
        records = await client.dns.aimport_records(
            args["zone"],
            args["records"],
            format="dict",
            merge=args.get("merge", True),
        )
        return {"success": True, "imported": len(records), "records": [_record_to_dict(r) for r in records]}

    # Diff/Preview
    elif name == "cloudflare_diff_records":
        result = await client.adiff_dns_records(
            args["records"],
            root_domain=args.get("zone"),
            sync_mode=args.get("sync_mode", "upsert"),
        )
        return _apply_result_to_dict(result)

    elif name == "cloudflare_compare_zones":
        result = await client.acompare_zones(
            args["source_zone"],
            args["target_zone"],
            record_types=args.get("record_types"),
        )
        return result

    # Apply
    elif name == "cloudflare_apply_records":
        result = await client.aapply_dns_records(
            args["records"],
            root_domain=args.get("zone"),
            sync_mode=args.get("sync_mode", "upsert"),
        )
        return _apply_result_to_dict(result)

    else:
        return {"error": f"Unknown tool: {name}"}


def _record_to_dict(record) -> dict:
    """Convert DNSRecord to dict"""
    return {
        "id": record.id,
        "name": record.name,
        "type": record.type,
        "content": record.content,
        "ttl": record.ttl,
        "proxied": record.proxied,
        "priority": record.priority,
    }


def _apply_result_to_dict(result) -> dict:
    """Convert MultiZoneApplyResult to dict"""
    zones = []
    for zone_result in result.results:
        zones.append({
            "zone_id": zone_result.zone_id,
            "zone_name": zone_result.zone_name,
            "to_create": [
                {"name": c.name, "type": c.type, "content": c.content}
                for c in zone_result.to_create
            ],
            "to_update": [
                {"name": c.name, "type": c.type, "content": c.content, "old_content": c.old_content}
                for c in zone_result.to_update
            ],
            "to_delete": [
                {"name": c.name, "type": c.type, "content": c.content}
                for c in zone_result.to_delete
            ],
            "created": [_record_to_dict(r) for r in zone_result.created],
            "updated": [_record_to_dict(r) for r in zone_result.updated],
            "deleted": [_record_to_dict(r) for r in zone_result.deleted],
            "errors": zone_result.errors,
        })

    return {
        "zones": zones,
        "errors": result.errors,
        "total_changes": result.total_changes,
    }


async def serve():
    """Run the MCP server"""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for the MCP server"""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

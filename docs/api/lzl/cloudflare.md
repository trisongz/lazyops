# Cloudflare Client

The `lzl.api.cloudflare` module provides a hybrid sync/async client for the Cloudflare API with comprehensive DNS record management capabilities.

## Overview

The Cloudflare client follows the established patterns in the `lzl.api` ecosystem:

- **Hybrid sync/async**: All methods have both synchronous and asynchronous versions
- **Settings management**: Uses `pydantic-settings` for environment-based configuration
- **Lazy initialization**: Components are initialized on first use via `ProxyObject`
- **Resource-based design**: API operations are organized into resource classes

## Installation

The Cloudflare client is included with `lzl` - no additional dependencies required:

```bash
pip install lazyops
```

## Quick Start

```python
from lzl.api.cloudflare import client

# List all zones
zones = client.list_zones()

# List DNS records for a zone
records = client.dns.list(zone_id)

# Create a new record
client.dns.create(zone_id, {
    "type": "A",
    "name": "www.example.com",
    "content": "192.0.2.1",
    "ttl": 3600,
})

# Async operations
zones = await client.alist_zones()
records = await client.dns.alist(zone_id)
```

## Configuration

### Environment Variables

The client automatically reads configuration from environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `CLOUDFLARE_API_TOKEN` | Bearer API token (recommended) | Yes* |
| `CLOUDFLARE_API_KEY` | Legacy Global API Key | Yes* |
| `CLOUDFLARE_EMAIL` | Email for API key authentication | With `API_KEY` |
| `CLOUDFLARE_ACCOUNT_ID` | Default account ID | No |
| `CLOUDFLARE_ZONE_ID` | Default zone ID | No |

*Either `API_TOKEN` or (`API_KEY` + `EMAIL`) is required.

### CloudflareSettings

::: lzl.api.cloudflare.CloudflareSettings
    options:
      show_root_heading: true
      show_source: false
      members:
        - api_token
        - api_key
        - email
        - account_id
        - zone_id
        - base_url
        - has_auth
        - auth_headers

### Programmatic Configuration

```python
from lzl.api.cloudflare import CloudflareClient

# Using API Token (recommended)
client = CloudflareClient(api_token="your-api-token")

# Using API Key + Email
client = CloudflareClient(
    api_key="your-api-key",
    email="your-email@example.com",
)

# With additional options
client = CloudflareClient(
    api_token="your-api-token",
    account_id="default-account-id",
    timeout=60.0,  # Request timeout in seconds
)
```

## Zone Management

### Listing Zones

```python
# List all zones
zones = client.list_zones()

# Filter by name
zones = client.list_zones(name="example.com")

# Filter by status
zones = client.list_zones(status="active")

# Pagination
zones = client.list_zones(per_page=100, page=2)

# Async
zones = await client.alist_zones()
```

### Getting a Zone

```python
# By name
zone = client.get_zone("example.com")

# By ID
zone = client.get_zone("zone-id-here")

# Get just the zone ID
zone_id = client.get_zone_id("example.com")
```

### Zone Model

::: lzl.api.cloudflare.Zone
    options:
      show_root_heading: true
      show_source: false

## DNS Resource

The DNS resource provides CRUD operations for DNS records.

### DNSResource

::: lzl.api.cloudflare.DNSResource
    options:
      show_root_heading: true
      show_source: false
      members:
        - list
        - alist
        - list_all
        - alist_all
        - get
        - aget
        - create
        - acreate
        - update
        - aupdate
        - delete
        - adelete
        - batch
        - abatch
        - upsert
        - aupsert
        - upsert_many
        - aupsert_many

### Listing Records

```python
# List all records in a zone
records = client.dns.list(zone_id)

# Filter by name
records = client.dns.list(zone_id, name="www.example.com")

# Filter by type
records = client.dns.list(zone_id, record_type="A")

# Filter by content
records = client.dns.list(zone_id, content="192.0.2.1")

# Filter by proxy status
records = client.dns.list(zone_id, proxied=True)

# Pagination
records = client.dns.list(zone_id, per_page=100, page=2)

# List all (handles pagination automatically)
all_records = client.dns.list_all(zone_id)
```

### Creating Records

```python
# Simple A record
record = client.dns.create(zone_id, {
    "type": "A",
    "name": "www.example.com",
    "content": "192.0.2.1",
})

# With options
record = client.dns.create(zone_id, {
    "type": "A",
    "name": "www.example.com",
    "content": "192.0.2.1",
    "ttl": 3600,       # TTL in seconds (1 = auto)
    "proxied": True,   # Enable Cloudflare proxy
    "comment": "Web server",
    "tags": ["production", "web"],
})

# MX record with priority
record = client.dns.create(zone_id, {
    "type": "MX",
    "name": "example.com",
    "content": "mail.example.com",
    "priority": 10,
})

# TXT record
record = client.dns.create(zone_id, {
    "type": "TXT",
    "name": "_dmarc.example.com",
    "content": "v=DMARC1; p=reject; rua=mailto:dmarc@example.com",
})
```

### Updating Records

```python
# Full update (PUT) - requires all fields
record = client.dns.update(zone_id, record_id, {
    "type": "A",
    "name": "www.example.com",
    "content": "192.0.2.2",
    "ttl": 3600,
    "proxied": True,
})

# Partial update (PATCH) - only specified fields
record = client.dns.update(zone_id, record_id, {
    "content": "192.0.2.2",
}, partial=True)
```

### Deleting Records

```python
# Delete by ID
success = client.dns.delete(zone_id, record_id)
```

### Upserting Records

The upsert operation creates a record if it doesn't exist, or updates it if it does:

```python
# Single upsert
record = client.dns.upsert(zone_id, {
    "type": "A",
    "name": "www.example.com",
    "content": "192.0.2.1",
})

# By default, matches on name + type + content
# Set match_content=False to match only on name + type
record = client.dns.upsert(zone_id, {
    "type": "A",
    "name": "www.example.com",
    "content": "192.0.2.1",
}, match_content=False)

# Bulk upsert (more efficient - uses batch API)
records = client.dns.upsert_many(zone_id, [
    {"type": "A", "name": "www.example.com", "content": "192.0.2.1"},
    {"type": "A", "name": "api.example.com", "content": "192.0.2.2"},
    {"type": "CNAME", "name": "cdn.example.com", "content": "cdn.cloudflare.com"},
])
```

### Batch Operations

Execute multiple operations in a single API call:

```python
result = client.dns.batch(
    zone_id,
    # Create new records
    posts=[
        {"type": "A", "name": "new.example.com", "content": "192.0.2.1"},
    ],
    # Update existing records (partial)
    patches=[
        {"id": "record-id-1", "content": "192.0.2.2"},
    ],
    # Replace existing records (full)
    puts=[
        {"id": "record-id-2", "type": "A", "name": "www.example.com", "content": "192.0.2.3", "ttl": 1},
    ],
    # Delete records
    deletes=[
        {"id": "record-id-3"},
    ],
)

# Operations execute in order: deletes -> patches -> puts -> posts
```

### DNS Record Model

::: lzl.api.cloudflare.DNSRecord
    options:
      show_root_heading: true
      show_source: false

## Declarative DNS Management

The `apply_dns_records` method provides a declarative way to manage DNS records - define the desired state, and the client handles the rest.

### Basic Usage

```python
# Define desired DNS state
records = [
    {
        "dns_name": "www",
        "record_type": "A",
        "targets": ["192.0.2.1"],
    },
    {
        "dns_name": "api",
        "record_type": "A",
        "targets": ["192.0.2.2"],
    },
    {
        "dns_name": "email",
        "record_type": "MX",
        "targets": ["10 mail.example.com", "20 mail2.example.com"],
    },
]

# Apply to a zone
result = client.apply_dns_records(records, root_domain="example.com")

# Check results
print(f"Created: {len(result.results[0].created)}")
print(f"Updated: {len(result.results[0].updated)}")
```

### Input Format

::: lzl.api.cloudflare.DNSRecordInput
    options:
      show_root_heading: true
      show_source: false

Records can be specified with full DNS names or subdomain shorthand:

```python
# Full DNS names (can span multiple zones)
records = [
    {"dns_name": "www.example.com", "record_type": "A", "targets": ["192.0.2.1"]},
    {"dns_name": "api.other-domain.com", "record_type": "A", "targets": ["192.0.2.2"]},
]
result = client.apply_dns_records(records)

# Subdomain shorthand (single zone)
records = [
    {"dns_name": "www", "record_type": "A", "targets": ["192.0.2.1"]},
    {"dns_name": "api", "record_type": "A", "targets": ["192.0.2.2"]},
    {"dns_name": "@", "record_type": "A", "targets": ["192.0.2.3"]},  # Root domain
]
result = client.apply_dns_records(records, root_domain="example.com")
```

### Options

```python
# Record with options
{
    "dns_name": "www",
    "record_type": "A",
    "targets": ["192.0.2.1"],
    "options": {
        "proxied": True,
        "ttl": "auto",  # or integer seconds
        "comment": "Main web server",
        "tags": ["production"],
    }
}
```

::: lzl.api.cloudflare.DNSRecordOptions
    options:
      show_root_heading: true
      show_source: false

### MX Priority

MX record priorities can be specified inline or explicitly:

```python
# Inline format (parsed from target string)
{"dns_name": "@", "record_type": "MX", "targets": ["10 mail.example.com", "20 mail2.example.com"]}

# Explicit format
{
    "dns_name": "@",
    "record_type": "MX",
    "targets": ["mail.example.com"],
    "options": {"priority": 10}
}
```

### Sync Modes

```python
# Upsert mode (default) - only creates and updates, never deletes
# This is the safe default for incremental changes
result = client.apply_dns_records(records, root_domain="example.com", sync_mode="upsert")

# Full sync mode - deletes records not in the provided list
# Use with caution! Can remove unrelated records
result = client.apply_dns_records(records, root_domain="example.com", sync_mode="full")
```

### Dry Run

Preview changes without applying them:

```python
result = client.apply_dns_records(records, root_domain="example.com", dry_run=True)

for zone_result in result.results:
    print(f"Zone: {zone_result.zone_name}")
    print(f"  To create: {len(zone_result.to_create)}")
    for change in zone_result.to_create:
        print(f"    - {change.name} {change.type} -> {change.content}")
    print(f"  To update: {len(zone_result.to_update)}")
    print(f"  To delete: {len(zone_result.to_delete)}")
```

### Result Models

::: lzl.api.cloudflare.ApplyResult
    options:
      show_root_heading: true
      show_source: false

::: lzl.api.cloudflare.MultiZoneApplyResult
    options:
      show_root_heading: true
      show_source: false

## Record Type-Specific Helpers

Convenience methods for common record types that accept zone name or ID:

```python
# A record (IPv4)
client.dns.add_a_record("example.com", "www", "192.0.2.1", proxied=True)

# AAAA record (IPv6)
client.dns.add_aaaa_record("example.com", "@", "2001:db8::1")

# CNAME record
client.dns.add_cname_record("example.com", "blog", "blog.example.net", proxied=True)

# MX record
client.dns.add_mx_record("example.com", "@", "mail.example.com", priority=10)

# TXT record
client.dns.add_txt_record("example.com", "@", "v=spf1 include:_spf.google.com ~all")
```

## Service Templates

Pre-configured templates for common email providers:

### Google Workspace

```python
# Add all Google Workspace MX records
records = client.dns.add_google_workspace_mx("example.com")

# Add SPF for Google
client.dns.add_spf_record("example.com", providers=["google"])

# Add DMARC
client.dns.add_dmarc_record(
    "example.com",
    policy="quarantine",
    rua="dmarc-reports@example.com",
)
```

### Microsoft 365

```python
# Add Microsoft 365 MX record
records = client.dns.add_microsoft_365_mx("example.com")

# Add SPF for Microsoft
client.dns.add_spf_record("example.com", providers=["microsoft"])
```

### Combined Setup

```python
# SPF for both Google and Microsoft
client.dns.add_spf_record(
    "example.com",
    providers=["google", "microsoft"],
    ip4=["203.0.113.1"],  # Additional IPs
    policy="-all",  # Strict policy
)

# Full DMARC setup
client.dns.add_dmarc_record(
    "example.com",
    policy="reject",
    rua="dmarc-aggregate@example.com",
    ruf="dmarc-forensic@example.com",
    pct=100,
)
```

## Export / Import

### Exporting Records

```python
# Export to JSON
json_data = client.dns.export_records("example.com", format="json")
with open("dns_backup.json", "w") as f:
    f.write(json_data)

# Export to BIND zone file format
bind_data = client.dns.export_records("example.com", format="bind")

# Export as Python dict
records = client.dns.export_records("example.com", format="dict")

# Filter by record types
mx_records = client.dns.export_records(
    "example.com",
    format="json",
    record_types=["MX", "TXT"],
)

# Exclude certain types
filtered = client.dns.export_records(
    "example.com",
    format="json",
    exclude_types=["NS", "SOA"],
)
```

### Importing Records

```python
# Import from JSON file
with open("dns_backup.json") as f:
    json_data = f.read()
records = client.dns.import_records("example.com", json_data, format="json")

# Import from dict (merge mode - upserts records)
records_data = [
    {"name": "www.example.com", "type": "A", "content": "192.0.2.1"},
    {"name": "api.example.com", "type": "A", "content": "192.0.2.2"},
]
records = client.dns.import_records("example.com", records_data, format="dict", merge=True)

# Import without merging (only creates new records)
records = client.dns.import_records("example.com", records_data, format="dict", merge=False)
```

## Diff / Preview

Preview changes before applying:

```python
# Preview changes without applying
desired_records = [
    {"dns_name": "www", "record_type": "A", "targets": ["192.0.2.1"]},
    {"dns_name": "api", "record_type": "A", "targets": ["192.0.2.2"]},
]

diff = client.diff_dns_records(desired_records, root_domain="example.com")

for zone_result in diff.results:
    print(f"Zone: {zone_result.zone_name}")

    print("To Create:")
    for change in zone_result.to_create:
        print(f"  + {change.name} {change.type} -> {change.content}")

    print("To Update:")
    for change in zone_result.to_update:
        print(f"  ~ {change.name} {change.type} -> {change.content}")

    print("To Delete:")
    for change in zone_result.to_delete:
        print(f"  - {change.name} {change.type} -> {change.content}")
```

### Comparing Zones

Compare DNS records between two zones:

```python
comparison = client.compare_zones("example.com", "example.net")

print(f"Records only in {comparison['source_zone']}:")
for rec in comparison["only_in_source"]:
    print(f"  {rec['name']} {rec['type']} {rec['content']}")

print(f"Records only in {comparison['target_zone']}:")
for rec in comparison["only_in_target"]:
    print(f"  {rec['name']} {rec['type']} {rec['content']}")

print("Different content:")
for rec in comparison["different"]:
    print(f"  {rec['name']} {rec['type']}")
    print(f"    Source: {rec['source_content']}")
    print(f"    Target: {rec['target_content']}")

# Compare specific record types only
comparison = client.compare_zones(
    "example.com",
    "example.net",
    record_types=["A", "CNAME"],
)
```

## Async Support

All methods have async counterparts with the `a` prefix:

```python
# Zone operations
zones = await client.alist_zones()
zone = await client.aget_zone("example.com")

# DNS operations
records = await client.dns.alist(zone_id)
record = await client.dns.acreate(zone_id, {...})
record = await client.dns.aupdate(zone_id, record_id, {...})
await client.dns.adelete(zone_id, record_id)
result = await client.dns.abatch(zone_id, posts=[...])

# Upsert
record = await client.dns.aupsert(zone_id, {...})
records = await client.dns.aupsert_many(zone_id, [...])

# Apply
result = await client.aapply_dns_records(records, root_domain="example.com")

# Record type helpers
await client.dns.aadd_a_record("example.com", "www", "192.0.2.1")
await client.dns.aadd_mx_record("example.com", "@", "mail.example.com", 10)

# Service templates
await client.dns.aadd_google_workspace_mx("example.com")
await client.dns.aadd_spf_record("example.com", providers=["google"])

# Export/Import
json_data = await client.dns.aexport_records("example.com")
await client.dns.aimport_records("example.com", json_data)

# Diff/Compare
diff = await client.adiff_dns_records(records, root_domain="example.com")
comparison = await client.acompare_zones("example.com", "example.net")
```

## Context Manager

The client supports context manager usage for proper resource cleanup:

```python
# Sync
with CloudflareClient(api_token="...") as client:
    zones = client.list_zones()
# HTTP client is automatically closed

# Async
async with CloudflareClient(api_token="...") as client:
    zones = await client.alist_zones()
```

## Module Singletons

For convenience, lazy-initialized singletons are available at the module level:

```python
from lzl.api.cloudflare import client, settings

# Uses environment variables automatically
zones = client.list_zones()

# Access settings
print(settings.base_url)
print(settings.has_auth)
```

## Error Handling

The client raises `httpx.HTTPStatusError` for API errors:

```python
import httpx

try:
    record = client.dns.create(zone_id, {...})
except httpx.HTTPStatusError as e:
    print(f"API error: {e.response.status_code}")
    print(f"Response: {e.response.json()}")
```

For `apply_dns_records`, errors are captured in the result:

```python
result = client.apply_dns_records(records, root_domain="example.com")

if result.has_errors:
    for error in result.errors:
        print(f"Error: {error}")
    for zone_result in result.results:
        for error in zone_result.errors:
            print(f"Zone {zone_result.zone_name}: {error}")
```

## API Reference

### CloudflareClient

::: lzl.api.cloudflare.CloudflareClient
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - has_auth
        - auth_headers
        - http_client
        - dns
        - list_zones
        - alist_zones
        - get_zone
        - aget_zone
        - get_zone_id
        - aget_zone_id
        - apply_dns_records
        - aapply_dns_records
        - close
        - aclose

# Cloudflare API Client

A hybrid sync/async client for the Cloudflare API with support for DNS record management.

## Installation

The Cloudflare client is included as part of `lzl`. No additional dependencies required.

## Quick Start

```python
from lzl.api.cloudflare import client

# List zones
zones = client.list_zones()

# List DNS records
records = client.dns.list(zone_id)

# Create a record
client.dns.create(zone_id, {
    "type": "A",
    "name": "www.example.com",
    "content": "192.0.2.1",
    "ttl": 3600,
})
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CLOUDFLARE_API_TOKEN` | Bearer API token (preferred) | Yes* |
| `CLOUDFLARE_API_KEY` | Legacy Global API Key | Yes* |
| `CLOUDFLARE_EMAIL` | Email for API key auth | With API_KEY |
| `CLOUDFLARE_ACCOUNT_ID` | Default account ID | No |
| `CLOUDFLARE_ZONE_ID` | Default zone ID | No |

*Either `API_TOKEN` or `API_KEY` + `EMAIL` is required.

### Programmatic Configuration

```python
from lzl.api.cloudflare import CloudflareClient

client = CloudflareClient(
    api_token="your-api-token",
    # OR
    api_key="your-api-key",
    email="your-email@example.com",
)
```

## DNS Operations

### CRUD Operations

```python
# List records
records = client.dns.list(zone_id)
records = client.dns.list(zone_id, name="www.example.com", record_type="A")
records = client.dns.list_all(zone_id)  # Handles pagination

# Get a single record
record = client.dns.get(zone_id, record_id)

# Create a record
record = client.dns.create(zone_id, {
    "type": "A",
    "name": "www.example.com",
    "content": "192.0.2.1",
})

# Update a record
record = client.dns.update(zone_id, record_id, {
    "content": "192.0.2.2",
}, partial=True)

# Delete a record
client.dns.delete(zone_id, record_id)
```

### Upsert Operations

The `upsert` method creates a record if it doesn't exist, or updates it if it does:

```python
# Single record upsert
record = client.dns.upsert(zone_id, {
    "type": "A",
    "name": "www.example.com",
    "content": "192.0.2.1",
})

# Upsert multiple records efficiently (uses batch API)
records = client.dns.upsert_many(zone_id, [
    {"type": "A", "name": "www.example.com", "content": "192.0.2.1"},
    {"type": "A", "name": "api.example.com", "content": "192.0.2.2"},
])
```

### Batch Operations

```python
result = client.dns.batch(
    zone_id,
    posts=[{"type": "A", "name": "new.example.com", "content": "192.0.2.1"}],
    patches=[{"id": record_id, "content": "192.0.2.2"}],
    deletes=[{"id": record_id_to_delete}],
)
```

## Declarative DNS Management

The `apply_dns_records` method provides a declarative way to manage DNS records:

```python
# Define desired DNS state
records = [
    {
        "dns_name": "email",
        "record_type": "MX",
        "targets": ["10 alt4.aspmx.l.google.com", "20 alt3.aspmx.l.google.com"],
    },
    {
        "dns_name": "spf",
        "record_type": "TXT",
        "targets": ["v=spf1 ip4:34.67.208.29 ~all"],
    },
    {
        "dns_name": "www",
        "record_type": "A",
        "targets": ["192.0.2.1"],
        "options": {"proxied": True, "ttl": "auto"},
    },
]

# Apply to a zone
result = client.apply_dns_records(records, root_domain="example.com")
print(f"Created: {len(result.results[0].created)}")
print(f"Updated: {len(result.results[0].updated)}")
```

### Input Formats

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
]
result = client.apply_dns_records(records, root_domain="example.com")
```

### MX Priority

MX priorities can be specified inline or explicitly:

```python
# Inline format (parsed from target)
{"dns_name": "email", "record_type": "MX", "targets": ["10 mail.server.com"]}

# Explicit format
{
    "dns_name": "email",
    "record_type": "MX",
    "targets": ["mail.server.com"],
    "options": {"priority": 10}
}
```

### Sync Modes

```python
# Upsert mode (default, safe) - only creates/updates, never deletes
result = client.apply_dns_records(records, root_domain="example.com", sync_mode="upsert")

# Full sync mode (destructive) - deletes records not in the list
result = client.apply_dns_records(records, root_domain="example.com", sync_mode="full")
```

### Dry Run

Preview changes without applying them:

```python
result = client.apply_dns_records(records, root_domain="example.com", dry_run=True)
print("To create:", result.results[0].to_create)
print("To update:", result.results[0].to_update)
print("To delete:", result.results[0].to_delete)
```

## Async Support

All methods have async counterparts with the `a` prefix:

```python
# Async operations
zones = await client.alist_zones()
records = await client.dns.alist(zone_id)
record = await client.dns.aupsert(zone_id, record_data)
result = await client.aapply_dns_records(records, root_domain="example.com")
```

## Context Manager

```python
# Sync context manager
with CloudflareClient(api_token="...") as client:
    zones = client.list_zones()

# Async context manager
async with CloudflareClient(api_token="...") as client:
    zones = await client.alist_zones()
```

## Module Singletons

For convenience, module-level singletons are available:

```python
from lzl.api.cloudflare import client, settings

# Uses environment variables automatically
zones = client.list_zones()
print(settings.base_url)
```

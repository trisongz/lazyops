# Cloudflare MCP Server

An MCP (Model Context Protocol) server that exposes Cloudflare DNS management functionality as tools for AI assistants like Claude.

## Installation

Install with MCP support:

```bash
# Using pip
pip install lazyops[cloudflare]

# Using uv
uv pip install lazyops[cloudflare]
```

## Configuration

Set your Cloudflare credentials as environment variables:

```bash
# Using API Token (recommended)
export CLOUDFLARE_API_TOKEN="your-api-token"

# Or using API Key + Email
export CLOUDFLARE_API_KEY="your-api-key"
export CLOUDFLARE_EMAIL="your-email@example.com"
```

## Running the Server

### Using uv (Recommended)

```bash
# Run directly with uv
uv run cloudflare-mcp

# Or with inline dependencies
uv run --with lazyops[cloudflare] cloudflare-mcp
```

### Using Python Module

```bash
python -m lzl.api.cloudflare.mcp
```

### Using Entry Point (after installation)

```bash
cloudflare-mcp
```

## Claude Desktop Configuration

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "cloudflare": {
      "command": "uv",
      "args": ["run", "--with", "lazyops[cloudflare]", "cloudflare-mcp"],
      "env": {
        "CLOUDFLARE_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

Or if you have `lazyops` installed globally:

```json
{
  "mcpServers": {
    "cloudflare": {
      "command": "cloudflare-mcp",
      "env": {
        "CLOUDFLARE_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

## Available Tools

### Zone Management

| Tool | Description |
|------|-------------|
| `cloudflare_list_zones` | List all zones in the account |
| `cloudflare_get_zone` | Get details for a specific zone |

### DNS Record Operations

| Tool | Description |
|------|-------------|
| `cloudflare_list_records` | List DNS records for a zone |
| `cloudflare_create_record` | Create a new DNS record |
| `cloudflare_update_record` | Update an existing record |
| `cloudflare_delete_record` | Delete a DNS record |

### Record Type Helpers

Convenience tools for common record types:

| Tool | Description |
|------|-------------|
| `cloudflare_add_a_record` | Add an A record (IPv4) |
| `cloudflare_add_aaaa_record` | Add an AAAA record (IPv6) |
| `cloudflare_add_cname_record` | Add a CNAME record |
| `cloudflare_add_mx_record` | Add an MX record |
| `cloudflare_add_txt_record` | Add a TXT record |

### Service Templates

Pre-configured email service setups:

| Tool | Description |
|------|-------------|
| `cloudflare_add_google_workspace_mx` | Add Google Workspace MX records |
| `cloudflare_add_microsoft_365_mx` | Add Microsoft 365 MX record |
| `cloudflare_add_spf_record` | Add SPF record with provider presets |
| `cloudflare_add_dmarc_record` | Add DMARC record |

### Export / Import

| Tool | Description |
|------|-------------|
| `cloudflare_export_records` | Export records to JSON or BIND format |
| `cloudflare_import_records` | Import records from JSON |

### Diff / Compare

| Tool | Description |
|------|-------------|
| `cloudflare_diff_records` | Preview changes without applying |
| `cloudflare_compare_zones` | Compare records between two zones |

### Declarative Management

| Tool | Description |
|------|-------------|
| `cloudflare_apply_records` | Apply desired DNS state declaratively |

## Example Prompts

Once connected, you can ask Claude:

- "List all my Cloudflare zones"
- "Show me the DNS records for example.com"
- "Add an A record pointing www.example.com to 192.0.2.1"
- "Set up Google Workspace email for example.com"
- "Add SPF and DMARC records for example.com"
- "Export all DNS records from example.com"
- "Compare DNS records between staging.example.com and example.com"

## Security Notes

- The server uses your Cloudflare credentials from environment variables
- All operations are performed with the permissions of your API token
- Use API tokens with minimal required permissions when possible
- The `sync_mode="full"` option in `cloudflare_apply_records` can delete records - use with caution

## Troubleshooting

### Server won't start

1. Ensure credentials are set:
   ```bash
   echo $CLOUDFLARE_API_TOKEN
   ```

2. Verify the MCP package is installed:
   ```bash
   uv pip show mcp
   ```

3. Test the server manually:
   ```bash
   uv run cloudflare-mcp
   ```

### Permission errors

Ensure your API token has the required permissions:
- `Zone:Read` - For listing zones
- `DNS:Read` - For listing records
- `DNS:Edit` - For creating/updating/deleting records

### Connection issues

Check that your `claude_desktop_config.json` is valid JSON and the paths are correct.

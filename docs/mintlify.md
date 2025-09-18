# Mintlify Documentation Workflow

Use the Mintlify CLI (`mint`) to preview and validate documentation locally. The
commands below assume `docs.json` lives at the project root (next to
`pyproject.toml`).

```bash
# Install or update the CLI
npm i -g mint
mint update

# Preview documentation locally on http://localhost:3000
mint dev

# Run validation checks
mint broken-links
mint openapi-check <openapiFilenameOrUrl>
```

When the documentation site is ready, deploy via the Mintlify dashboard or your
existing CI workflow.

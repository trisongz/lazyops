# MkDocs Setup Guide

This guide explains how to use MkDocs with Material theme for the LazyOps documentation.

## Overview

LazyOps uses [MkDocs](https://www.mkdocs.org/) with the [Material theme](https://squidfunk.github.io/mkdocs-material/) for generating beautiful, searchable documentation from Markdown files and Python docstrings.

## Prerequisites

Install the documentation dependencies:

```bash
pip install mkdocs mkdocs-material "mkdocstrings[python]" pymdown-extensions
```

Or install all docs extras:

```bash
pip install -e ".[docs]"
```

## Local Development

### Serve Documentation Locally

Run the development server to preview documentation with live reload:

```bash
make mkdocs-serve
# or
mkdocs serve
```

The documentation will be available at `http://127.0.0.1:8000/`.

### Build Documentation

Build the static site:

```bash
make mkdocs-build
# or
mkdocs build
```

The built site will be in the `site/` directory.

## Documentation Structure

```
docs/
├── index.md                 # Homepage
├── code-style.md           # Coding standards
├── future-updates.md       # Roadmap
├── todo.md                 # Task tracking
├── mintlify.md            # Mintlify workflow reference
├── mkdocs-setup.md        # This file
└── api/                    # API documentation
    ├── lzl/               # lzl namespace docs
    │   ├── index.md
    │   ├── io.md
    │   ├── load.md
    │   ├── logging.md
    │   ├── pool.md
    │   ├── proxied.md
    │   ├── require.md
    │   └── sysmon.md
    └── lzo/               # lzo namespace docs
        ├── index.md
        ├── registry.md
        ├── types.md
        └── utils.md
```

## Adding New Documentation

### Creating New Pages

1. Create a new Markdown file in the `docs/` directory
2. Add it to the navigation in `mkdocs.yml`

Example:

```yaml
nav:
  - New Section:
    - New Page: new-page.md
```

### Auto-generating API Documentation

Use the `mkdocstrings` plugin to automatically generate documentation from docstrings:

```markdown
# My Module

::: my_module.my_function
    options:
      show_source: true
```

This will render the docstring and source code of `my_function`.

### Supported Features

- **Code Blocks**: Syntax highlighting for Python and other languages
- **Admonitions**: Notes, warnings, tips, etc.
- **Tables**: Markdown tables with alignment
- **Links**: Internal and external links
- **Images**: Embedded images with captions
- **Math**: LaTeX math rendering
- **Tabs**: Tabbed content sections

## Configuration

The documentation configuration is in `mkdocs.yml`:

- **Theme**: Material theme with custom colors
- **Navigation**: Organized into sections and subsections
- **Plugins**: Search and mkdocstrings for API docs
- **Extensions**: Syntax highlighting, admonitions, etc.

## Deployment

### Manual Deployment

Deploy to GitHub Pages:

```bash
make mkdocs-deploy
# or
mkdocs gh-deploy --force
```

### Automatic Deployment

The documentation is automatically deployed to GitHub Pages on every push to `main` that affects:
- Files in `docs/`
- `mkdocs.yml`
- `.github/workflows/docs.yml`

The GitHub Actions workflow is defined in `.github/workflows/docs.yml`.

## Tips and Best Practices

1. **Preview Changes**: Always preview locally before committing
2. **Link Checking**: Use relative links for internal pages
3. **Code Examples**: Include working code examples
4. **Docstrings**: Use Google-style docstrings for consistency
5. **Images**: Store images in `docs/assets/` (create if needed)
6. **Search**: The search functionality works on the built site

## Troubleshooting

### Build Warnings

- **Unrecognized links**: Ensure link paths are correct (include `.md` extension)
- **Missing modules**: Ensure all Python modules can be imported
- **Syntax errors**: Check Python source files for syntax issues

### Local Server Issues

If the local server doesn't start:
- Check if port 8000 is already in use
- Use `mkdocs serve -a 127.0.0.1:8001` to use a different port

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [mkdocstrings](https://mkdocstrings.github.io/)
- [PyMdown Extensions](https://facelessuser.github.io/pymdown-extensions/)

# Convenience commands for common development workflows.

PYTHON ?= python
PYTEST ?= pytest
PYTEST_OPTS ?=
MINT ?= npx --yes mint
MKDOCS ?= mkdocs
DOCS_REMOTE ?= origin
DOCS_BRANCH ?= main

PYTHONPATH := src$(if $(PYTHONPATH),:$(PYTHONPATH),)
export PYTHONPATH

.PHONY: test test-lzl-io test-lzl-load test-lzl-logging test-lzl-pool test-lzl-proxied test-lzl-require test-lzl-sysmon test-lzl test-lzo-registry test-lzo-types test-lzo-utils test-lzo docs-preview docs-generate docs-publish mkdocs-serve mkdocs-build mkdocs-deploy

## test: Run the entire pytest suite
test:
	$(PYTEST) $(PYTEST_OPTS)

## test-lzl-io: Run IO-focused LazyLib tests added during documentation work
test-lzl-io:
	$(PYTEST) $(PYTEST_OPTS) \
		tests/lzl/test_io_serializers.py \
		tests/lzl/test_io_temporary.py \
		tests/lzl/test_io_persistent_dict.py

## test-lzl-load: Run LazyLoad utility tests
test-lzl-load:
	$(PYTEST) $(PYTEST_OPTS) tests/lzl/test_load_lazy.py

## test-lzl-logging: Run LazyOps logging tests
test-lzl-logging:
	$(PYTEST) $(PYTEST_OPTS) tests/lzl/test_logging_basic.py

## test-lzl-pool: Run LazyOps thread pool tests
test-lzl-pool:
	$(PYTEST) $(PYTEST_OPTS) tests/lzl/test_pool.py

## test-lzl-proxied: Run LazyOps proxy helper tests
test-lzl-proxied:
	$(PYTEST) $(PYTEST_OPTS) tests/lzl/test_proxied.py

## test-lzl-require: Run LazyOps dependency resolver tests
test-lzl-require:
	$(PYTEST) $(PYTEST_OPTS) tests/lzl/test_require.py

## test-lzl-sysmon: Run system monitoring context tests
test-lzl-sysmon:
	$(PYTEST) $(PYTEST_OPTS) tests/lzl/test_sysmon.py

## test-lzl: Run documentation-focused submodule tests
test-lzl: test-lzl-io test-lzl-load test-lzl-logging test-lzl-pool test-lzl-proxied test-lzl-require test-lzl-sysmon

## test-lzo-registry: Run registry tests created during `lzo` documentation sweep
test-lzo-registry:
	$(PYTEST) $(PYTEST_OPTS) tests/lzo/test_registry.py

## test-lzo-types: Run type helper tests added for `lzo.types`
test-lzo-types:
	$(PYTEST) $(PYTEST_OPTS) tests/lzo/test_types.py

## test-lzo-utils: Exercise utility helpers refreshed during documentation work
test-lzo-utils:
	$(PYTEST) $(PYTEST_OPTS) tests/lzo/test_utils.py

## test-lzo: Run the `lzo` suite generated alongside documentation updates
test-lzo: test-lzo-registry test-lzo-types test-lzo-utils

## docs-preview: Preview documentation locally via Mintlify
docs-preview:
	$(MINT) dev

## docs-generate: Run Mintlify validation checks before publishing
docs-generate:
	$(MINT) broken-links
	@if [ -n "$(DOCS_OPENAPI)" ]; then \
		$(MINT) openapi-check $(DOCS_OPENAPI); \
	fi

## docs-publish: Push documentation updates to trigger Mintlify deployment
docs-publish:
	git push $(DOCS_REMOTE) $(DOCS_BRANCH)

## mkdocs-serve: Serve MkDocs documentation locally for development
mkdocs-serve:
	$(MKDOCS) serve

## mkdocs-build: Build MkDocs documentation site
mkdocs-build:
	$(MKDOCS) build

## mkdocs-deploy: Deploy MkDocs documentation to GitHub Pages
mkdocs-deploy:
	$(MKDOCS) gh-deploy --force

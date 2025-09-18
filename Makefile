# Convenience commands for common development workflows.

PYTHON ?= python
PYTEST ?= pytest
PYTEST_OPTS ?=

.PHONY: test test-lzl-io test-lzl-load test-lzl-logging test-lzl

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

## test-lzl: Run documentation-focused submodule tests
test-lzl: test-lzl-io test-lzl-load test-lzl-logging

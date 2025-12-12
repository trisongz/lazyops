import pytest
import sys
from lzl.load import lazy_import, lazy_load

def test_lazy_import_module():
    """
    Test lazy importing of a standard module.
    """
    # Test with 'os' module
    os_mod = lazy_import('os', is_module=True)
    assert os_mod.path.join("a", "b") == "a/b"

def test_lazy_import_class():
    """
    Test lazy importing of a class.
    """
    # uuid.UUID
    UUID = lazy_import('uuid.UUID')
    u = UUID(int=1)
    assert str(u) == '00000000-0000-0000-0000-000000000001'

def test_lazy_load_decorator():
    """
    Test lazy_load decorator (if applicable, or similar pattern).
    """
    # Assuming lazy_load is available or similar
    pass

def test_error_handling():
    """
    Test handling of missing modules.
    """
    with pytest.raises(ImportError):
        # Trigger import
        mod = lazy_import('non_existent_module_xyz')
        _ = mod.some_attr

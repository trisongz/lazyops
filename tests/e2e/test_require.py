import pytest
from lzl.require import LazyLib

def test_require_check_installed():
    """
    Test checking for an installed package.
    """
    # pytest should be installed
    assert LazyLib.is_available("pytest")

def test_require_missing():
    """
    Test behavior for missing package.
    """
    assert not LazyLib.is_available("non_existent_package_12345")

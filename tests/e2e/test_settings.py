import pytest
import os
from lzo.types import BaseSettings
from pydantic import Field

class SettingsConfig(BaseSettings):
    my_var: str = Field(..., alias="MY_VAR")
    nested_var: str = "default"

def test_settings_env_loading():
    """
    Test loading settings from environment variables.
    """
    os.environ["MY_VAR"] = "test_value"
    settings = SettingsConfig()
    assert settings.my_var == "test_value"
    del os.environ["MY_VAR"]

def test_settings_defaults():
    """
    Test default values.
    """
    os.environ["MY_VAR"] = "val"
    settings = SettingsConfig()
    assert settings.nested_var == "default"
    del os.environ["MY_VAR"]

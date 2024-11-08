from __future__ import annotations

from lzl.proxied import ProxyObject
from lzo.registry.settings import register_app_settings, get_app_settings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lzl.io.file.configs.main import FileIOConfig

register_app_settings(
    'file',
    'lzl.io.file.configs.main.FileIOConfig',
)

def get_settings(**kwargs) -> 'FileIOConfig':
    """
    Returns the FileIO Settings
    """
    return get_app_settings('file', **kwargs)


fileio_settings: 'FileIOConfig' = ProxyObject(obj_getter = get_settings)
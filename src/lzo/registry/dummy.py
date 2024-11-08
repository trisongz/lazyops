

from lzo.types import BaseSettings
from lzo.types.base import Registered

class TestSettings(BaseSettings, Registered):
    name: str = 'test'
    version: str = '1.0.0'


class RegSettings(BaseSettings):
    name: str = 'reg'
    version: str = '1.0.0'
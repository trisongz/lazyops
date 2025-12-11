
import typing as t
from lzl.proxied.base import ProxyObject

class Settings:
    redis_url: str = "redis://localhost:6379"

def get_settings() -> Settings:
    return Settings()

# This is the usage pattern the user wants to work without explicit type hint
settings = ProxyObject(obj_getter=get_settings)

# We want to check if 'settings' is inferred as 'Settings'
# In a real IDE, we'd hover. Here we can use typing helpers or just run mypy.
if t.TYPE_CHECKING:
    reveal_type(settings)

from __future__ import annotations

"""
Extra Network Types
"""


import contextlib
import functools
import urllib.request
from typing import Union, List, Optional
from typing_extensions import Annotated

from pydantic import (
    BeforeValidator,
    AfterValidator,
    PlainSerializer,
    TypeAdapter,
    WithJsonSchema,
)


@functools.lru_cache(maxsize = 128)
def validate_one_url(url: str) -> bool:
    """
    Validate that the url is valid
    """
    with contextlib.suppress(Exception):
        urllib.request.urlopen(url, timeout = 0.5)
        return True
    return False


def validate_url_from_list(urls: Union[str, List[str]]) -> Optional[str]:
    """
    Validates between the urls and returns the first valid url
    """
    urls = [urls] if isinstance(urls, str) else urls
    return next((url for url in urls if validate_one_url(url)), None)

"""
Usage:

class ServerSettings(BaseModel):
    endpoint: ValidURL

settings = ServerSettings(endpoint = "https://www.google.com")
settings = ServerSettings(endpoint = ["http://fake.local", "https://www.google.com"])

>> settings.endpoint = "https://www.google.com"
"""

ValidURL = Annotated[
    str,
    BeforeValidator(validate_url_from_list),
    WithJsonSchema({'type': 'string'}, mode='serialization'),
]



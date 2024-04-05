"""
Niquest Based Client
"""

from __future__ import annotations

from lazyops.libs import lazyload


from gspread.client import Client as BaseClient
from gspread.http_client import HTTPClient as BaseHTTPClient
from typing import Optional, Union, Tuple

if lazyload.TYPE_CHECKING:
    import niquests
    import requests

    from google.auth.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession
    from niquests import Request
else:
    niquests = lazyload.LazyLoad("niquests")


class CredsAuth(niquests.Auth):
    """
    An instance of this class is used to authenticate requests.
    """

    def __init__(self, auth: Credentials) -> None:
        self.auth = auth

    def __call__(self, r: 'Request'):
        
        if not self.auth.valid:
            self.auth.refresh(r)


class HTTPClient(BaseHTTPClient):
    """An instance of this class communicates with Google API.

    :param Credentials auth: An instance of google.auth.Credentials used to authenticate requests
        created by either:

        * gspread.auth.oauth()
        * gspread.auth.oauth_from_dict()
        * gspread.auth.service_account()
        * gspread.auth.service_account_from_dict()

    :param Session session: (Optional) An OAuth2 credential object. Credential objects
        created by `google-auth <https://github.com/googleapis/google-auth-library-python>`_.

        You can pass you own Session object, simply pass ``auth=None`` and ``session=my_custom_session``.

    This class is not intended to be created manually.
    It will be created by the gspread.Client class.
    """

    def __init__(self, auth: 'Credentials', session: Optional['requests.Session'] = None) -> None:


        if session is not None:
            self.session = session
        else:
            from gspread.utils import convert_credentials
            self.auth: Credentials = convert_credentials(auth)
            self.session = AuthorizedSession(self.auth)

        self.timeout: Optional[Union[float, Tuple[float, float]]] = None

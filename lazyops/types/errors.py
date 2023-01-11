
from lazyops.imports._aiohttpx import aiohttpx
from lazyops.types.classprops import lazyproperty

class ClientError(Exception):
    client_name: str = 'APIClient'

    def __init__(
        self, 
        response: 'aiohttpx.Response'
    ):
        self.response = response

    @lazyproperty
    def url(self):
        return self.response.url
    
    @lazyproperty
    def status_code(self):
        return self.response.status_code
    
    @lazyproperty
    def headers(self):
        return self.response.headers
    
    @lazyproperty
    def payload(self):
        try:
            return self.response.json()
        except Exception:
            return self.response.text


    def __str__(self):
        return f"[{self.client_name}] url: {self.url}, status_code: {self.status_code}, payload: {self.payload}"


def fatal_exception(exc):
    if isinstance(exc, ClientError):
        # retry on no sessions available.
        # retry on overloaded
        # if exc.status_code in [500, 503]:
        #     return False
        # return exc.status_code >= 400
        return exc.status_code == 503 or exc.status_code >= 400
    else:
        # retry on all other errors (eg. network)
        return False

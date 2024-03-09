"""
Exceptions
"""

from lazyops.libs import lazyload
if lazyload.TYPE_CHECKING:
    from fastapi import HTTPException
else:
    HTTPException = lazyload.LazyLoad("fastapi.HTTPException")

class ExpiredJWTException(HTTPException):
    """
    Exception for expired JWT
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        super().__init__(status_code=401, detail=detail or 'Expired JWT', **kwargs)

class InvalidJWTException(HTTPException):
    """
    Exception for invalid JWT
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        super().__init__(status_code=401, detail=detail or 'Invalid JWT', **kwargs)
    

class InvalidOperationException(HTTPException):
    """
    Exception for invalid operation
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        super().__init__(status_code=400, detail=detail or 'Invalid Operation', **kwargs)


class InvalidTokenException(HTTPException):
    """
    Exception for invalid token
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        super().__init__(status_code=401, detail = f'Invalid Token: {detail}', **kwargs)

class NoTokenException(HTTPException):
    """
    Exception for no token
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        detail = detail or 'Not Authorized: no auth token found'
        super().__init__(status_code=401, detail = detail, **kwargs)


class NoAPIKeyException(HTTPException):
    """
    Exception for no API Key
    """
    def __init__(self, key: str = 'x-api-key', detail: str = None, **kwargs):
        """
        Constructor
        """
        detail = detail or f'Not Authorized: no `{key}` found'
        super().__init__(status_code=401, detail = detail, **kwargs)


class InvalidAPIKeyException(HTTPException):
    """
    Exception for invalid API Key
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        detail = detail or 'Invalid API Key'
        super().__init__(status_code=401, detail = detail, **kwargs)

class InvalidAPIKeyPrefixException(HTTPException):
    """
    Exception for invalid API Key prefix
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        detail = detail or 'Invalid API Key Prefix. Your API Key may be deprecated. Please regenerate your API Key by logging in again.'
        super().__init__(status_code=401, detail = detail, **kwargs)

class InvalidAPIKeySecretException(HTTPException):
    """
    Exception for invalid API Key secret
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        detail = detail or 'Invalid API Key. Your API Key may not belong to the correct application / environment. Please regenerate your API Key by logging in again.'
        super().__init__(status_code=401, detail = detail, **kwargs)

class InsufficientPermissionsException(HTTPException):
    """
    Exception for insufficient permissions
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        detail = detail or 'Insufficient Permissions'
        super().__init__(status_code=403, detail = detail, **kwargs)

class InvalidAuthorizationException(HTTPException):
    """
    Exception for invalid authorization
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        detail = detail or 'Invalid Authorization'
        super().__init__(status_code=403, detail = detail, **kwargs)

class ExpiredSessionException(HTTPException):
    """
    Exception for expired session
    """
    def __init__(self, detail: str = None, **kwargs):
        """
        Constructor
        """
        detail = detail or 'Session Expired. Please log in again.'
        super().__init__(status_code=403, detail = detail, **kwargs)


class AuthorizationException(HTTPException):
    """
    Exception for authorization
    """
    def __init__(self, detail: str = None, status_code: int = 403, **kwargs):
        """
        Constructor
        """
        detail = detail or f'Authorization Failed: {detail}'
        super().__init__(status_code = status_code, detail = detail, **kwargs)
"""
Exceptions
"""

import traceback
from lazyops.libs import lazyload
from typing import List, Optional

if lazyload.TYPE_CHECKING:
    import fastapi
    # from fastapi import HTTPException
else:
    fastapi = lazyload.LazyLoad("fastapi")
    # HTTPException = lazyload.LazyLoad("fastapi.HTTPException")

class AuthZeroException(fastapi.HTTPException):
    """
    Base Auth Zero Exception
    """

    base: Optional[str] = None
    concat_detail: Optional[bool] = True
    verbose: Optional[int] = None
    default_status_code: Optional[int] = 400

    log_error: Optional[bool] = False # Always log the error message
    log_devel: Optional[bool] = False # Log the error message if in development mode

    def __init__(self, detail: str = None, error: Optional[Exception] = None, status_code: Optional[int] = None, **kwargs):
        """
        Constructor
        """
        from ..configs import settings
        message = ""
        if not detail or self.concat_detail:
            message += f"{self.base}: " or ''
        if detail: message += detail
        if error and self.verbose is not None:
            if self.verbose >= 1:
                message += f"\nError: {error}"
            elif self.verbose <= 5:
                message += f"\nError: {error}\nTraceback: {traceback.format_exc()}"
        status_code = status_code or self.default_status_code
        super().__init__(status_code=status_code, detail=message, **kwargs)
        if self.log_error or (self.log_devel and settings.is_development_env):
            self.display(message, status_code)

    def display(self, message: str, status_code: int):
        """
        Displays the error
        """
        from ..utils.lazy import logger
        logger.error(f'[{self.__class__.__name__} - {status_code}]: {message}')


class ExpiredJWTException(AuthZeroException):
    """
    Expired JWT Exception
    """
    base = "Expired JWT"
    concat_detail = True
    log_devel = True
    default_status_code = 401

class InvalidJWTException(AuthZeroException):
    """
    Invalid JWT Exception
    """
    base = "Invalid JWT"
    concat_detail = True
    log_devel = True
    default_status_code = 401

class InvalidOperationException(AuthZeroException):
    """
    Invalid Operation Exception
    """
    base = "Invalid Operation"
    concat_detail = True
    log_devel = True
    default_status_code = 400

class InvalidTokenException(AuthZeroException):
    """
    Invalid Token Exception
    """
    base = "Invalid Token"
    concat_detail = True
    log_devel = True
    default_status_code = 401

class NoTokenException(AuthZeroException):
    """
    No Token Exception
    """
    base = "Not Authorized: no auth token found"
    concat_detail = True
    log_devel = True
    default_status_code = 401


class NoAPIKeyException(AuthZeroException):
    """
    No API Key Exception
    """
    base = "Not Authorized"
    concat_detail = True
    log_devel = True
    default_status_code = 401

    def __init__(self, key: str = 'x-api-key', detail: str = None, **kwargs):
        """
        Constructor
        """
        self.base += f' no `{key}` found'
        super().__init__(detail = detail, **kwargs)

class InvalidAPIKeyException(AuthZeroException):
    """
    Invalid API Key Exception
    """
    base = "Invalid API Key"
    concat_detail = True
    log_devel = True
    default_status_code = 401

class InvalidAPIKeyPrefixException(AuthZeroException):
    """
    Invalid API Key Prefix Exception
    """
    base = "Invalid API Key Prefix. Your API Key may be deprecated. Please regenerate your API Key by logging in again"
    concat_detail = True
    log_devel = False
    default_status_code = 401

class InvalidAPIKeySecretException(AuthZeroException):
    """
    Invalid API Key Secret Exception
    """
    base = "Invalid API Key. Your API Key may not belong to the correct application / environment. Please regenerate your API Key by logging in again"
    concat_detail = True
    log_devel = True
    default_status_code = 401

class InsufficientPermissionsException(AuthZeroException):
    """
    Insufficient Permissions Exception
    """
    base = "Insufficient Permissions"
    concat_detail = True
    log_devel = True
    default_status_code = 403

class InvalidAuthorizationException(AuthZeroException):
    """
    Invalid Authorization Exception
    """
    base = "Invalid Authorization"
    concat_detail = True
    log_devel = True
    default_status_code = 403

class ExpiredSesssionException(AuthZeroException):
    """
    Expired Session Exception
    """
    base = "Session Expired. Please log in again"
    concat_detail = True
    log_devel = True
    default_status_code = 403

class AuthorizationException(AuthZeroException):
    """
    Authorization Exception
    """
    base = "Authorization Failed"
    concat_detail = True
    log_devel = True
    default_status_code = 403


class InvalidRoleException(AuthZeroException):
    """
    Invalid Role Exception
    """
    base = "User does not have role"
    concat_detail = False
    log_devel = True
    default_status_code = 403

    def __init__(self, role: str):
        """
        Initializes the invalid role exception
        """
        detail = f'User does not have role `{role}`'
        super().__init__(detail = detail)

class InvalidRolesException(AuthZeroException):
    """
    Invalid Roles Exception
    """
    base = "User does not have sufficient roles"
    concat_detail = False
    log_devel = True
    default_status_code = 403

    def __init__(self, roles: List[str], require_all: bool = False):
        """
        Initializes the invalid roles exception
        """
        detail = f'User does not have sufficient roles `{roles}`' if require_all else f'User does not have any of the roles `{roles}`'
        super().__init__(detail = detail)


class InvalidAuthRoleException(AuthZeroException):
    """
    Invalid Auth Role Exception
    """
    base = "Invalid Auth Role"
    concat_detail = True
    log_devel = True
    default_status_code = 403

class NoUserException(AuthZeroException):
    """
    No User Exception
    """
    base = "Unauthorized: no user found"
    concat_detail = True
    log_devel = True
    default_status_code = 401

class InvalidAPIKeyException(AuthZeroException):
    """
    Invalid API Key Exception
    """
    base = "Invalid API Key"
    concat_detail = True
    log_devel = True
    default_status_code = 403

class ExpiredAPIKeyData(AuthZeroException):
    """
    Expired API Key Data
    """
    
    base = "Expired API Key Data"
    concat_detail = True
    log_devel = True
    default_status_code = 403
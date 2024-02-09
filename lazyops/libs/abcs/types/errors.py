from __future__ import annotations

"""
Generic Errors
"""

import traceback
from lazyops.utils.logs import logger
from fastapi.exceptions import HTTPException
from typing import Any, Optional, Union


_is_development_env: Optional[bool] = None

def set_development_env(is_development: bool):
    """
    Sets the development environment
    """
    global _is_development_env
    _is_development_env = is_development


class AppException(Exception):

    base: Optional[str] = None
    concat_detail: Optional[bool] = True
    verbosity: Optional[int] = None

    log_error: Optional[bool] = False # Always log the error message
    log_devel: Optional[bool] = False # Log the error message if in development mode

    """
    Base App Exception
    """

    def __init__(
        self, 
        detail: str = None, 
        error: Optional[Exception] = None, 
        **kwargs
    ):
        """
        Constructor
        """
        message = ""
        if not detail or self.concat_detail:
            message += f"{self.base}: " or ''
        if detail: message += detail
        if error and self.verbosity is not None:
            if self.verbosity >= 1:
                message += f"\nError: {error}"
            elif self.verbosity <= 5:
                message += f"\nError: {error}\nTraceback: {traceback.format_exc()}"
        super().__init__(message, **kwargs)
        if self.log_error or (self.log_devel and self.is_development_env):
            self.display(message)

    @property
    def is_development_env(self) -> bool:
        """
        Returns True if the app environment is development
        """
        return _is_development_env
    
    def display(self, message: str):
        """
        Displays the error
        """
        logger.error(f'[{self.__class__.__name__}]: {message}')

class DatabaseItemNotFoundException(AppException):
    """
    Database Item Not Found Exception
    """
    base = "Database Item Not Found"
    verbosity = 1
    log_devel = True

try:
    from fastapi.exceptions import HTTPException

    class APIException(HTTPException):
        """
        Base API Exception
        """
        
        base: Optional[str] = None
        concat_detail: Optional[bool] = True
        verbosity: Optional[int] = None
        default_status_code: Optional[int] = 500

        log_error: Optional[bool] = False # Always log the error message
        log_devel: Optional[bool] = False # Log the error message if in development mode

        def __init__(
            self, 
            detail: str = None, 
            error: Optional[Exception] = None, 
            status_code: Optional[int] = None, 
            **kwargs
        ):
            """
            Constructor
            """
            message = ""
            if not detail or self.concat_detail:
                message += f"{self.base}: " or ''
            if detail: message += detail
            if error and self.verbosity is not None:
                if self.verbosity >= 1:
                    message += f"\nError: {error}"
                elif self.verbosity <= 5:
                    message += f"\nError: {error}\nTraceback: {traceback.format_exc()}"
            status_code = status_code or self.default_status_code
            super().__init__(status_code=status_code, detail=message, **kwargs)
            if self.log_error or (self.log_devel and self.is_development_env):
                self.display(message, status_code)

        @property
        def is_development_env(self) -> bool:
            """
            Returns True if the app environment is development
            """
            return _is_development_env
        
        def display(self, message: str, status_code: int):
            """
            Displays the error
            """
            logger.error(f'[{self.__class__.__name__} - {status_code}]: {message}')
    

    class DatabaseItemNotFoundException(APIException):
        """
        Database Item Not Found Exception
        """
        base = "Database Item Not Found"
        verbosity = 1
        log_devel = True
        default_status_code = 404
    
    

except ImportError:
    pass

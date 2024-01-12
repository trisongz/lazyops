import traceback

from fastapi.exceptions import HTTPException
from lazyops.utils.logs import logger

from typing import Optional


class ORMException(HTTPException):
    """
    Base ORM Exception
    """
    
    base: Optional[str] = None
    concat_detail: Optional[bool] = True
    verbose: Optional[int] = None
    default_status_code: Optional[int] = 500
    log_error: Optional[bool] = True # Always log the error message

    def __init__(self, detail: str = None, error: Optional[Exception] = None, status_code: Optional[int] = None, **kwargs):
        """
        Constructor
        """
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
        if self.log_error:
            self.display(message, status_code)
    
    def display(self, message: str, status_code: int):
        """
        Displays the error
        """
        logger.error(f'[{self.__class__.__name__} - {status_code}]: {message}')


class NoItemFoundException(ORMException):
    """
    No Item Found Exception
    """
    base = "No Item Found"
    default_status_code = 404
    
class MissingItemsException(ORMException):
    """
    Missing Items Exception
    """
    base = "Not all Items were found for"
    default_status_code = 404
    

class NoResultsFoundException(ORMException):
    """
    No Results Found Exception
    """
    base = "No Results Found"
    default_status_code = 404

class InvalidModelException(ORMException):
    """
    Invalid Model Exception
    """
    base = "Invalid Model"
    default_status_code = 400

class InvalidOperationException(ORMException):
    """
    Invalid Operation Exception
    """
    base = "Invalid Operation"
    default_status_code = 400
    
class InvalidParameterException(ORMException):
    """
    Invalid Parameter Exception
    """
    base = "Invalid Parameter"
    default_status_code = 400

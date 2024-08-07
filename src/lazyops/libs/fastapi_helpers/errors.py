from __future__ import annotations

"""
A FastAPI Exception Helper to register errors
"""

import traceback
from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.encoders import jsonable_encoder
from .responses import JSONResponse, PrettyJSONResponse
from typing import Optional, Dict, Any, Union, Type, List, Callable, TYPE_CHECKING
from lazyops.utils.logs import logger


FASTAPI_ERRORS: Dict[str, List[Type['FastAPIException']]] = {}

def register_error(error: Type['FastAPIException']):
    """
    Registers an error
    """
    global FASTAPI_ERRORS
    if error.module not in FASTAPI_ERRORS: FASTAPI_ERRORS[error.module] = []
    FASTAPI_ERRORS[error.module].append(error)

    
class FastAPIException(HTTPException):
    """
    AuthZ Exception
    """
    module: Optional[str] = 'default'
    base: Optional[str] = None
    concat_detail: Optional[bool] = True
    verbose: Optional[int] = None
    
    kind: Optional[str] = 'fastapi_error'
    status: Optional[int] = 400 # Default status code
    problem: Optional[str] = None
    solution: Optional[str] = None

    log_error: Optional[bool] = False # Always log the error message

    def __init_subclass__(cls) -> None:
        """
        Registers the error
        """
        register_error(cls)
        return super().__init_subclass__()

    def __init__(self, detail: str = None, error: Optional[Exception] = None, status_code: Optional[int] = None, **kwargs):
        """
        Constructor
        """
        for kw in {'verbose', 'concat_detail', 'base', 'kind', 'problem', 'solution'}:
            if kw in kwargs: setattr(self, kw, kwargs.pop(kw))
        
        message = ""
        if (not detail or self.concat_detail) and self.base:
            message += f"{self.base}: " or ''
        if detail: message += detail
        if error and self.verbose is not None:
            if self.verbose >= 1:
                message += f"\nError: {error}"
            elif self.verbose <= 5:
                message += f"\nError: {error}\nTraceback: {traceback.format_exc()}"
        status_code = status_code or self.status
        super().__init__(detail=message, status_code=status_code, **kwargs)
        if self.log_error: self.display(message, status_code)
    
    def display(self, message: str, status_code: int):
        """
        Displays the error
        """
        logger.error(f'[{self.__class__.__name__} - {status_code}]: {message}')

    def __str__(self):
        """
        String Representation
        """
        return f'[{self.__class__.__name__} - {self.status_code}]: {self.detail}'
    
    def __repr__(self):
        """
        Representation
        """
        return f'{self.__class__.__name__}(status_code={self.status_code!r}, detail={self.detail!r})'
    

    def json_data(self) -> Dict[str, Union[str, int]]:
        """
        Returns the json data
        """
        return {
            'kind': self.kind,
            'status': self.status_code,
            'problem': self.problem,
            'solution': self.solution,
            'detail': self.detail,
            'error': self.__class__.__name__,
        }



def add_exception_handlers_to_app(
    app: 'FastAPI',
    func: Callable,
    module: Optional[str] = 'default',
    verbose: Optional[bool] = False,
    detailed: Optional[bool] = False,
):
    """
    Adds the exception handlers to the app
    """
    seen = set()
    for error in FASTAPI_ERRORS.get(module, []):
        if error.__name__ in seen: continue
        if verbose and detailed: logger.info(f'Adding Exception Handler: {error.__name__}')
        app.add_exception_handler(error, func)
        seen.add(error.__name__)
    if verbose: logger.info(f'Added {len(seen)} Exception Handlers to {module}')


async def default_validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors
    """
    errors = exc.errors()
    log_errors = jsonable_encoder(errors)
    logger.error(f"Validation error for request {request.url}: {log_errors}")
    return JSONResponse(
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
        content = jsonable_encoder({"detail": errors}),
    )


async def default_exception_handler(request: Request, exc: FastAPIException):
    """
    Default Exception Handler
    """
    logger.error(f"Error: {exc}")
    return PrettyJSONResponse(
        status_code = exc.status_code,
        content = exc.json_data(),
    )


def add_default_exception_handlers_to_app(
    app: 'FastAPI',
    module: Optional[str] = 'default',
    func: Optional[Callable] = None,
    add_validation_handler: Optional[bool] = True,
    verbose: Optional[bool] = False,
    detailed: Optional[bool] = False,
):
    """
    Adds the exception handlers to the app
    """
    seen = set()
    if func is None: func = default_exception_handler
    for error in FASTAPI_ERRORS.get(module, []):
        if error.__name__ in seen: continue
        if verbose and detailed: logger.info(f'Adding Exception Handler: {error.__name__}')
        app.add_exception_handler(error, func)
        seen.add(error.__name__)
    if add_validation_handler: app.add_exception_handler(RequestValidationError, default_validation_exception_handler)
    if verbose: logger.info(f'Added {len(seen)} Exception Handlers to {module}')



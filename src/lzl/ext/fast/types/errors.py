from __future__ import annotations

"""
A FastAPI Exception Helper to register errors
"""

import contextlib
import traceback
from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.encoders import jsonable_encoder
from .responses import JSONResponse, PrettyJSONResponse
from typing import Optional, Dict, Any, Union, Type, List, Callable, Set, TYPE_CHECKING
from lzl.logging import logger


FASTAPI_ERRORS: Dict[str, List[Type['FastAPIException']]] = {}
ADDED_ERRORS: Set['FastAPIException'] = set()

def register_error(error: Type['FastAPIException']):
    """
    Registers an error
    """
    global FASTAPI_ERRORS
    if error.module is None: 
        error.module = error.__module__.split('.')[0]
    if error.module not in FASTAPI_ERRORS: FASTAPI_ERRORS[error.module] = []
    FASTAPI_ERRORS[error.module].append(error)


class FastAPIException(HTTPException):
    """
    FastAPI Exception
    """
    module: Optional[str] = None
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
    

    def __init__(
        self, 
        detail: str = None, 
        error: Optional[Exception] = None, 
        status_code: Optional[int] = None, 
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        Constructor
        """
        self.constr_msg(detail = detail, error = error, **kwargs)
        self.conf(**kwargs)
        self.headers = headers
        self.status_code = status_code or self.status
        self.kwargs = kwargs
        if self.log_error: self.display(self.detail, self.status_code)

    def constr_msg(self, detail: str = None, error: Optional[Exception] = None, **kwargs):
        """
        Constructor
        """
        message = ""
        if (not detail or self.concat_detail) and self.base:
            message += f"{self.base}: " or ''
        if detail: message += detail
        if error and self.verbose is not None:
            if self.verbose >= 1: message += f"\nError: {error}"
            elif self.verbose <= 5: message += f"\nError: {error}\nTraceback: {traceback.format_exc()}"
        with contextlib.suppress(Exception):
            if '{' in message: message = message.format(**kwargs)
        self.detail = message
        with contextlib.suppress(Exception):
            if '{' in self.problem: self.problem = self.problem.format(**kwargs)
            if '{' in self.solution: self.solution = self.solution.format(**kwargs)
        

    def conf(self, **kwargs):
        """
        Configures the error
        """
        for kw in {'verbose', 'concat_detail', 'base', 'kind', 'problem', 'solution'}:
            if kw in kwargs: setattr(self, kw, kwargs.get(kw))
        
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
            'status': 'error',
            'status_code': self.status_code,
            'problem': self.problem,
            'solution': self.solution,
            'detail': self.detail,
            'error': self.__class__.__name__,
        }



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


def add_exception_handlers_to_app(
    app: 'FastAPI',
    func: Optional[Callable] = None,
    module: Optional[str] = None,
    verbose: Optional[bool] = False,
    detailed: Optional[bool] = False,
):
    """
    Adds the exception handlers to the app
    """
    global ADDED_ERRORS
    if module is None: module = list(FASTAPI_ERRORS.keys())[0]
    seen = set()
    func = func or default_exception_handler
    for error in FASTAPI_ERRORS.get(module, []):
        # if error.__name__ in seen: continue
        if error in ADDED_ERRORS: continue
        if verbose and detailed: logger.info(f'Adding Exception Handler: |g|{error.__name__}|e|', colored = True, prefix = f'{module}')
        app.add_exception_handler(error, func)
        ADDED_ERRORS.add(error)
        seen.add(error.__name__)
    if verbose: logger.info(f'Added |g|{len(seen)}|e| Exception Handlers to |g|{module}|e|', colored = True)

def add_all_exceptions_to_app(
    app: 'FastAPI',
    func: Optional[Callable] = None,
    verbose: Optional[bool] = False,
    detailed: Optional[bool] = False,
):
    """
    Adds all the exception handlers to the app
    """
    for module in FASTAPI_ERRORS:
        add_exception_handlers_to_app(app, func = func, module = module, verbose = verbose, detailed = detailed)
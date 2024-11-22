from __future__ import annotations

"""
Oso Exceptions
"""

from lzl.ext.fast.types.errors import FastAPIException

class OsoException(FastAPIException):
    """
    Oso Exception
    """
    base: str = "Oso Error"
    kind: str = "oso_error"
    status: int = 400
    problem: str = "Oso Error"
    solution: str = "Please check the error message for more information"
    module: str = "oso"

class ForbiddenError(OsoException):
    """
    Forbidden Error
    """
    status: int = 403
    kind = "fobidden_action"
    problem: str = "The requested action was not allowed for {actor} for the given resource [{resource}]"
    solution: str = "Please ensure that the proper permissions are set for the resource for the requested action: {action}"

class NotFoundError(OsoException):
    """
    Not Found Error
    """
    status: int = 404
    kind = "not_found"
    problem: str = "The current {actor} does not have permission for the given resource [{resource}]"
    solution: str = "Please ensure that the proper permissions are set for the resource for the requested action: {action}"

from ._base import *
from .models import component_name, rename_if_scope_child_component
from fastapi import status

class BaseError(Exception):
    CODE = None
    MESSAGE = None

    ErrorModel = None
    DataModel = None

    data_required = False
    errors_required = False

    error_model = None
    data_model = None
    resp_model = None

    _component_name = None

    def __init__(self, data=None):
        if data is None: data = {}
        raw_data = data
        data = self.validate_data(raw_data)
        Exception.__init__(self, self.CODE, self.MESSAGE)
        self.data = data
        self.raw_data = raw_data

    @classmethod
    def validate_data(cls, data):
        data_model = cls.get_data_model()
        if data_model: data = data_model.validate(data)
        return data

    def __str__(self):
        s = f"[{self.CODE}] {self.MESSAGE}"
        if self.data: s += f": {self.data!r}"
        return s

    def get_resp_data(self):
        return self.raw_data

    @classmethod
    def get_description(cls):
        s = cls.get_default_description()
        if cls.__doc__: s += "\n\n" + cls.__doc__
        return s

    @classmethod
    def get_default_description(cls):
        return f"[{cls.CODE}] {cls.MESSAGE}"

    def get_resp(self):
        error = {
            'code': self.CODE,
            'message': self.MESSAGE,
        }

        resp_data = self.get_resp_data()
        if resp_data: error['data'] = resp_data

        resp = {
            'jsonrpc': '2.0',
            'error': error,
            'id': None,
        }

        return jsonable_encoder(resp)

    @classmethod
    def get_error_model(cls):
        if cls.__dict__.get('error_model') is not None:
            return cls.error_model
        cls.error_model = cls.build_error_model()
        return cls.error_model

    @classmethod
    def build_error_model(cls):
        if cls.ErrorModel is not None:
            return rename_if_scope_child_component(cls, cls.ErrorModel, 'Error')
        return None

    @classmethod
    def get_data_model(cls):
        if cls.__dict__.get('data_model') is not None:
            return cls.data_model
        cls.data_model = cls.build_data_model()
        return cls.data_model

    @classmethod
    def build_data_model(cls):
        if cls.DataModel is not None:
            return rename_if_scope_child_component(cls, cls.DataModel, 'Data')

        error_model = cls.get_error_model()
        if error_model is None:
            return None

        errors_annotation = List[error_model]
        if not cls.errors_required: errors_annotation = Optional[errors_annotation]

        ns = {
            '__annotations__': {
                'errors': errors_annotation,
            }
        }

        _ErrorData = ModelMetaclass.__new__(ModelMetaclass, '_ErrorData', (BaseModel,), ns)
        _ErrorData = component_name(f'_ErrorData[{error_model.__name__}]', error_model.__module__)(_ErrorData)

        return _ErrorData

    @classmethod
    def get_resp_model(cls):
        if cls.__dict__.get('resp_model') is not None:
            return cls.resp_model
        cls.resp_model = cls.build_resp_model()
        return cls.resp_model

    @classmethod
    def build_resp_model(cls):
        ns = {
            'code': Field(cls.CODE, const=True, example=cls.CODE),
            'message': Field(cls.MESSAGE, const=True, example=cls.MESSAGE),
            '__annotations__': {
                'code': int,
                'message': str,
            }
        }

        data_model = cls.get_data_model()
        if data_model is not None:
            if not cls.data_required: data_model = Optional[data_model]
            # noinspection PyTypeChecker
            ns['__annotations__']['data'] = data_model

        name = cls._component_name or cls.__name__

        _JsonRpcErrorModel = ModelMetaclass.__new__(ModelMetaclass, '_JsonRpcErrorModel', (BaseModel,), ns)
        _JsonRpcErrorModel = component_name(name, cls.__module__)(_JsonRpcErrorModel)

        @component_name(f'_ErrorResponse[{name}]', cls.__module__)
        class _ErrorResponseModel(BaseModel):
            jsonrpc: StrictStr = Field('2.0', const=True, example='2.0')
            id: Union[StrictStr, int] = Field(None, example=0)
            error: _JsonRpcErrorModel
            class Config:
                extra = 'forbid'

        return _ErrorResponseModel

@component_name('_Error')
class ErrorModel(BaseModel):
    loc: List[str]
    msg: str
    type: str
    ctx: Optional[Dict[str, Any]]


class ParseError(BaseError):
    """Invalid JSON was received by the server"""
    CODE = status.HTTP_422_UNPROCESSABLE_ENTITY
    #CODE = -32700
    MESSAGE = "Parse error"


class InvalidRequest(BaseError):
    """The JSON sent is not a valid Request object"""
    #CODE = -32600
    CODE = status.HTTP_400_BAD_REQUEST
    MESSAGE = "Invalid Request"
    error_model = ErrorModel


class MethodNotFound(BaseError):
    """The method does not exist / is not available"""
    #CODE = -32601
    CODE = status.HTTP_405_METHOD_NOT_ALLOWED
    MESSAGE = "Method not found"


class InvalidParams(BaseError):
    """Invalid method parameter(s)"""
    #CODE = -32602
    CODE = status.HTTP_424_FAILED_DEPENDENCY
    MESSAGE = "Invalid params"
    error_model = ErrorModel


class InternalError(BaseError):
    """Internal JSON-RPC error"""
    #CODE = -32603
    CODE = status.HTTP_500_INTERNAL_SERVER_ERROR
    MESSAGE = "Internal error"


class NoContent(Exception):
    pass

def errors_responses(errors: Sequence[Type[BaseError]] = None):
    responses = {'default': {}}
    if errors:
        cnt = 1
        for error_cls in errors:
            #responses[404] = {
            #    'model': error_cls.get_resp_model(),
            #    'description': error_cls.get_description(),
            #}
            responses[error_cls.CODE] = {
                'model': error_cls.get_resp_model(),
                'description': error_cls.get_description(),
            }
            
            #responses[f'200{" " * cnt}'] = {
            #    'model': error_cls.get_resp_model(),
            #    'description': error_cls.get_description(),
            #}
            cnt += 1
    return responses


def invalid_request_from_validation_error(exc: ValidationError) -> InvalidRequest:
    return InvalidRequest(data={'errors': exc.errors()})


def invalid_params_from_validation_error(exc: ValidationError) -> InvalidParams:
    errors = []

    for err in exc.errors():
        if err['loc'][:1] == ('body', ):
            err['loc'] = err['loc'][1:]
        else:
            assert err['loc']
            err['loc'] = (f"<{err['loc'][0]}>", ) + err['loc'][1:]
        errors.append(err)

    return InvalidParams(data={'errors': errors})


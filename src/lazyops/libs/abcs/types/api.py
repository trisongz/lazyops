from __future__ import annotations

import contextlib
from lazyops.types import BaseModel, Field, root_validator
from lazyops.types.models import ConfigDict, schema_extra

from kvdb.types.jobs import Job, JobStatus
from lazyops.libs.logging import logger
from typing import Any, Dict, List, Optional, Type, TypeVar, Literal, Union, Set, TYPE_CHECKING

if TYPE_CHECKING:

    from fastapi.responses import JSONResponse
    from fastapi.exceptions import HTTPException
    from lazyops.libs.abcs.configs.base import AppSettings
    from lazyops.libs.abcs.types.errors import APIException

class BaseSchema(BaseModel):
    """
    BaseModel with some extra features, designed to be used
    for Pydantic Serializability in FastAPI
    """

    @classmethod
    def schema(cls, by_alias: bool = False, ref_template: str = None, **kwargs) -> Dict[str, Any]:
        """
        Returns the schema
        """
        if ref_template is None:
            ref_template = '#/components/schemas/{model}'
        return cls.model_json_schema(by_alias = by_alias, ref_template = ref_template, **kwargs)

    @property
    def settings(self) -> 'AppSettings':
        """
        Returns the app settings
        """
        from lazyops.libs.abcs.configs.lazy import get_module_settings
        return get_module_settings(self.__module__.__name__)
    
    @property
    def status_code(self) -> int:
        """
        Returns the status code
        """
        return 200
    
    @property
    def response_headers(self) -> Optional[Dict[str, Any]]:
        """
        Returns the response headers
        """
        return {}
    
    @property
    def schema_object_index_key(self) -> str:
        """
        Returns the schema object index key
        """
        return None
    
    @property
    def _excluded_fields(self) -> List[str]:
        """
        Returns the excluded fields
        """
        fields = []
        for field_name, field in self.model_fields.items():
            if field_name.startswith('_'): fields.append(field_name)
            elif getattr(field, 'is_excluded', None): fields.append(field_name)
        return fields
    
    def get_excluded_fields(self, exclude: Optional[Set[str]] = None) -> Set[str]:
        """
        Returns the excluded fields
        """
        exclude = exclude or set()
        exclude.update(self._excluded_fields)
        return exclude
    
    def json_response(self, exclude_none: bool = True, exclude: Optional[Set[str]] = None, indent: Optional[int] = 2, **kwargs) -> 'JSONResponse':
        """
        Returns the JSON response
        """
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content = self.dict(
                exclude = self.get_excluded_fields(exclude), 
                exclude_none = exclude_none, 
                **kwargs, 
            ),
            status_code = self.status_code,
            headers = self.response_headers,
        )

    def dict(self, exclude_none: bool = True, **kwargs):
        """
        We want to exclude None values by default
        """
        return self.model_dump(exclude_none = exclude_none, **kwargs)

    @classmethod
    def schema_name(cls) -> str:
        """
        Returns the class name
        """
        return f'{cls.__module__}.{cls.__name__}'
    
    
    @classmethod
    def raise_http_exception(cls, message: str, status_code: int = 400, **kwargs) -> None:
        """
        Raises an HTTPException
        """
        from fastapi.exceptions import HTTPException
        raise HTTPException(
            status_code = status_code,
            detail = message,
            **kwargs
        )
    

    def partial_log(
        self,
        limit: Optional[int] = None,
        fields: Optional[List[str]] = None,
        pretty: Optional[bool] = True,
        colored: Optional[bool] = False,
    ) -> str:
        """
        Returns the partial log as a string
        """
        s = f'[{self.__class__.__name__}]'
        if colored: s = f'|g|{s}|e|'
        if fields is None: fields = self.get_model_field_names()
        for field in fields:
            field_str = f'|g|{field}|e|' if colored else field
            val_s = f'\n\t{field_str}: {getattr(self, field)!r}' if pretty else f'{field_str}={getattr(self, field)!r}, '
            if limit is not None and len(val_s) > limit:
                val_s = f'{val_s[:limit]}...'
            s += val_s
        return s
    

    @contextlib.contextmanager
    def catch(
        self, 
        exc: Type['APIException'], 
        msg: Optional[str] = None, 
        fatal: Optional[bool] = False
    ):
        """
        Catches an exception
        """
        try:
            yield
        except Exception as e:
            logger.trace(f'Handling Error: {msg}', e)
            if fatal: raise exc(msg, error = e) from e

    def prepare_response(self, mode: str = 'python', **kwargs) -> Any:
        """
        Prepares the response
        """
        return self.model_dump(mode = mode, **kwargs)


    model_config = ConfigDict(json_schema_extra=schema_extra, extra='allow', arbitrary_types_allowed=True)



class BaseResponse(BaseSchema):
    """
    Response Schema for Requests
    """
    request_id: Optional[str] = Field(None, description = 'The request ID')
    callback_id: Optional[str] = Field(None, description = 'The callback ID')

    @property
    def response_headers(self) -> Optional[Dict[str, Any]]:
        """
        Returns the response headers
        """
        if not self.request_id and not self.callback_id: return None
        headers = {}
        if self.request_id: headers['X-Request-ID'] = self.request_id
        if self.callback_id: headers['X-Callback-ID'] = self.callback_id
        return headers


class JobResult(BaseResponse):

    status: JobStatus = Field(..., description = 'The job status')
    progress: Optional[float] = Field(None, description = 'The job progress')
    duration: Optional[float] = Field(None, description = 'The job duration in seconds')

    model_config = {'extra': 'ignore', 'arbitrary_types_allowed': True}

    
    @classmethod
    def from_job(
        cls, 
        job: Job, 
        callback_id: Optional[str] = None,
        **kwargs,
    ) -> 'JobResult':
        """
        Returns the JobResult from the Job
        """
        return cls(
            job_id = job.id,
            status = job.status,
            progress = job.progress.completed,
            duration = job.duration / 1000 if job.duration else None,
            callback_id = callback_id,
            **kwargs,
        )


SchemaT = TypeVar('SchemaT', bound = BaseSchema)
ResultT = Union[JobResult, SchemaT, Dict[str, Any], Any]


class BaseResponse(BaseResponse):
    """
    Base Response Schema for Tasks/Services
    """

    object: Optional[str] = Field(None, description = 'The Response Schema object')
    status: Optional[JobStatus] = Field(None, description = 'The Current Task Status')
    result: Optional[Union[Dict[str, Any], List[Union[Dict[str, Any], Any]], str]] = Field(None, description = 'The Result Object')
    error: Optional[Any] = Field(None, description = 'The Error Message or Exception')

    request_id: Optional[str] = Field(None, description = 'The request ID')
    callback_id: Optional[str] = Field(None, description = 'The callback ID')


    @root_validator(pre = True)
    def validate_object_schema(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that the schema is valid
        """
        # logger.info(f'Validating Response Schema: {values}')
        result = values.get('result')
        if result:
            if hasattr(result, 'is_exception') or isinstance(
                result, (Exception, HTTPException)
            ):
                values['object'] = result.__class__.__name__
                values['error'] = f'{result.__class__.__name__}: {str(result)}' 
                result = None

            elif hasattr(result, 'job_id'): result = JobResult(**result.dict())
            values['result'] = result

        if not values.get('object'):
            if result and hasattr(result, '__class__'): values['object'] = result.__class__.__name__
            elif values.get('error'): values['object'] = 'Error'

        if values.get('status') == JobStatus.FAILED:
            values['object'] = 'Error' 
            values['error'] = values.get('result')

        return values
    
    @property
    def response_headers(self) -> Optional[Dict[str, Any]]:
        """
        Returns the response headers
        """
        if not self.request_id and not self.callback_id: return None
        headers = {}
        if self.request_id: headers['X-Request-ID'] = self.request_id
        if self.callback_id: headers['X-Callback-ID'] = self.callback_id
        return headers


    @property
    def job_id(self):
        """
        Returns the job ID
        """
        return getattr(self.result, 'job_id', None) if self.result else None
    
    @property
    def is_error(self):
        """
        Returns True if the response has an error
        """
        return bool(self.error) and self.status == JobStatus.FAILED and \
            (self.result and isinstance(self.result, (Exception, HTTPException)))

    @property
    def has_error(self):
        """
        Returns True if the response has an error
        """
        return bool(self.error)
    
    @property
    def is_job(self):
        """
        Returns True if the response is a job
        """
        return bool(self.job_id)
    
    @property
    def is_result(self):
        """
        Returns True if the response is a result
        """
        return not self.is_job
    
    @property
    def is_complete(self):
        """
        Returns True if the response is complete
        """
        return self.status == JobStatus.COMPLETE and \
            self.is_result
    
    @property
    def status_code(self):
        """
        Returns the status code
        """
        if self.has_error or self.status == JobStatus.FAILED or self.object == "Error": return 400
        return 200 if self.status == JobStatus.COMPLETE else 202
    
    def raise_for_exceptions(self):
        """
        Helper method to raise for exceptions
        """
        if not self.has_error: return
        raise HTTPException(
            status_code = self.status_code,
            detail = f'{self.error}'
        )
    

    def __bool__(self):
        """
        Returns True if the response is successful
        """
        return not self.error and self.status in [
            JobStatus.COMPLETE,
            JobStatus.ACTIVE,
            JobStatus.QUEUED,
            JobStatus.NEW,
        ]


class BaseRequest(BaseSchema):
    """
    Base Request Schema 
    """

    def get_excluded_function_params(
        self,
        key: Optional[str] = 'exclude_param',
    ) -> List[str]:
        """
        Returns the excluded param fields
        """
        return [
            field_name
            for field_name, field in self.model_fields.items()
            if field.json_schema_extra.get(key, False)
        ]



    def get_function_kwargs(
        self,
        exclude_unset: Optional[bool] = True,
        exclude: Optional[Set[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Returns the Function Kwargs
        """
        exclude = exclude or set()
        excluded_params = self.get_excluded_function_params()
        if excluded_params: exclude.update(excluded_params)
        return self.model_dump(
            exclude_unset = exclude_unset,
            exclude = exclude,
            **kwargs,
        )

    @classmethod
    def from_get_request(
        cls,
        **kwargs,
    ) -> 'BaseRequest':
        """
        Builds the BaseRequest from the GET Request
        """
        from lazyops.utils.helpers import build_dict_from_query
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        for key in kwargs:
            if not cls.model_fields.get(key): continue
            # Check if the value is a dict
            annotation = cls.model_fields[key].annotation
            if isinstance(kwargs[key], str) and \
                (
                    annotation.__origin__ == dict or \
                    (
                        annotation.__origin__ == Union and \
                        'typing.Dict' in str(annotation.__args__[0])
                    )
                ):
                kwargs[key] = build_dict_from_query(kwargs[key])

        return cls(**kwargs)
    


class CallbackRequestSchema(BaseRequest):
    """
    Parameters for Callbacks upon Completion
    """
    callback_url: Optional[str] = Field(None, description="If provided, will send a callback notification to this endpoint when the job is complete", exclude = True)
    callback_id: Optional[str] = Field(None, description="If provided, will use this callback id when sending a callback notification to the callback_url", exclude = True)
    callback_method: Optional[str] = Field('POST', description="If provided, will use this method when sending a callback notification to the callback_url", exclude = True)
    callback_params: Optional[Dict[str, Any]] = Field(None, description="If provided, will use these parameters when sending a callback notification to the callback_url", exclude = True)
    callback_headers: Optional[Dict[str, Any]] = Field(None, description="If provided, will use these headers when sending a callback notification to the callback_url", exclude = True)
    callback_retries: Optional[int] = Field(None, description="If provided, will retry the callback this many times before giving up", exclude = True)
    callback_timeout: Optional[int] = Field(None, description="If provided, will timeout the callback after this many seconds", exclude = True)
    callback_refire: Optional[bool] = Field(None, description="If provided, will refire the callback when the result is retrieved again", exclude = True)

    @property
    def callback_enabled(self) -> bool:
        """
        Returns True if callback_url is not None
        """
        return self.callback_url is not None
    
    @property
    def callback_param_fields(self) -> List[str]:
        """
        Returns the param fields
        """
        return [
            'callback_url',
            'callback_id',
            'callback_method',
            'callback_params',
            'callback_headers',
            'callback_retries',
            'callback_timeout',
            'callback_refire',
        ]
    
    @classmethod
    def from_request(
        cls, 
        **kwargs,
    ) -> 'CallbackRequestSchema':
        """
        Parses the keywords from the request
        """
        from lazyops.utils.helpers import build_dict_from_query
        if callback_params := kwargs.pop('callback_params', None):
            kwargs['callback_params'] = build_dict_from_query(callback_params)
        if callback_headers := kwargs.pop('callback_headers', None):
            kwargs['callback_headers'] = build_dict_from_query(callback_headers)
        return cls(**kwargs)
    
    def to_request_kwargs(
        self,
        exclude_none: bool = True,
        exclude_unset: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Returns the request kwargs
        """
        return self.model_dump(
            include = set(self.callback_param_fields),
            exclude_none = exclude_none,
            exclude_unset = exclude_unset,
            **kwargs,
        )

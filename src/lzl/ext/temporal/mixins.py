from __future__ import annotations

"""
Temporal Workflow Mixins
"""

import abc
import uuid
import copy
import functools
import contextlib
import dataclasses
import typing as t
from .utils import logger, null_logger
from lzl.types import eproperty, BaseModel, Field, field_validator

if t.TYPE_CHECKING:
    from lzl.types import AppEnv
    from lzl.logging import Logger
    from .registry import TemporalRegistry
    from lzl.io.file import FileLike
    from temporalio.types import ParamType, ReturnType

MixinKinds = t.Literal['activity', 'workflow']

def default_id_gen_function(obj: 'BaseTemporalMixin', *args, prefix: t.Optional[str] = None, **kwargs) -> str:
    """
    Default ID Generator Function
    """
    # logger.info(f'ID Generator Options: {obj}', prefix = 'Temporal')
    base = prefix or obj.id_gen.prefix or ''
    if obj.id_gen.func: id_gen = obj.id_gen.func(*args, **kwargs)
    else: id_gen = str(uuid.uuid4().int)
    # id_gen = str(uuid.uuid4().int)
    if obj.id_gen.id_length: id_gen = id_gen[:obj.id_gen.id_length]
    base += f'{obj.id_gen.joiner}{id_gen}'
    if obj.id_gen.suffix: base += f'{obj.id_gen.joiner}{obj.id_gen.suffix}'
    base = base.lstrip(obj.id_gen.joiner).rstrip(obj.id_gen.joiner)
    base = base.replace(" ", obj.id_gen.joiner).replace(f'{obj.id_gen.joiner}{obj.id_gen.joiner}', obj.id_gen.joiner)
    if obj.id_gen.lower: base = base.lower()
    if obj.id_gen.max_length and len(base) > obj.id_gen.max_length: base = base[:obj.id_gen.max_length]
    return base

class IDGenOptions(BaseModel):
    """
    ID Generator Options
    """
    prefix: t.Optional[str] = None
    suffix: t.Optional[str] = None
    func: t.Optional[t.Callable[[], str]] = None
    # Field(default = default_id_gen_function, description = "The ID Generator Function")
    max_length: t.Optional[int] = 24
    id_length: t.Optional[int] = 8
    joiner: t.Optional[str] = '-'
    lower: t.Optional[bool] = True

    @field_validator('func', mode = 'before')
    def validate_func(cls, v: str | t.Callable[[], str] | None) -> t.Optional[t.Callable[[], str]]:
        """
        Validates the ID Generator Function
        """
        if v is None: return None
        if isinstance(v, str):
            from lzl.load import lazy_import
            v = lazy_import(v)
        return v

    def merge_from_config(self, config: t.Dict[str, t.Any]) -> 'IDGenOptions':
        """
        Merges the ID Generator Options from the config
        """
        new = self.model_copy(deep = True)
        if config.get('joiner'): new.joiner = config['joiner']
        if config.get('max_length'): new.max_length = config['max_length']
        if config.get('id_length'): new.id_length = config['id_length']
        if config.get('func'):
            if isinstance(config['func'], str):
                from lzl.load import lazy_import
                config['func'] = lazy_import(config['func'])
            new.func = config['func']
        
        if config.get('prefix'):
            if not new.prefix: new.prefix = config['prefix']
            elif config.get('prefix_override', False):
                new.prefix = config['prefix']
            elif config.get('prefix_append', True) and config['prefix'] not in new.prefix:
                if new.joiner not in config['prefix']: new.prefix += f'{new.joiner}{config["prefix"]}'
                else: new.prefix = config['prefix']
            if new.prefix: new.prefix.rstrip(new.joiner)
        
        if config.get('suffix'):
            if not new.suffix: new.suffix = config['suffix']
            elif config.get('suffix_override', False):
                new.suffix = config['suffix']
            elif config.get('suffix_append', True) and config['suffix'] not in new.suffix:
                if new.joiner not in config['suffix']: new.suffix += f'{new.joiner}{config["suffix"]}'
                else: new.suffix = config['suffix']
            if new.suffix: new.suffix.lstrip(new.joiner)
        return new

TemporalInputT = t.TypeVar('TemporalInputT')
TemporalReturnT = t.TypeVar('TemporalReturnT')

class BaseTemporalMixin(abc.ABC):
    """
    [Temporal] Base Mixin that will automatically registered
    """

    name: t.Optional[str] = None
    display_name: t.Optional[str] = None
    mixin_kind: t.Optional[MixinKinds] = None
    namespace: t.Optional[str] = None

    id_gen: t.Optional[IDGenOptions] = None
    config: t.Optional[t.Dict[str, t.Union[t.Dict[str, t.Any], t.Any], t.Any]] = {}
    merge_configs: t.Optional[t.Dict[str, t.Union[t.Dict[str, t.Any], t.Any], t.Any]] = {}
    
    disable_registration: t.Optional[bool] = None
    verbosity: t.Optional[int] = None # If verbosity is < 0, logging is disabled. if verbosity is > 0, logging is enabled

    _is_subclass_: t.Optional[bool] = None
    _steps: t.Dict[str, t.Dict[str, t.Any]] = {}
    _rxtra: t.Dict[str, t.Any] = {}

    def __init_subclass__(cls, **kwargs: t.Dict[str, t.Any]):
        if cls.merge_configs:
            # This merges this subclass config with the parent config
            from lzo.utils.helpers import update_dict
            cls.config = update_dict(cls.config, cls.merge_configs)
            cls.merge_configs = {}
        
        if cls.mixin_kind is not None and not cls.disable_registration: #  and cls.name is not None: 
            if cls._is_subclass_: 
                cls._is_subclass_ = False
            else:
                from lzl.ext.temporal.registry import registry
                registry.register_mixin(cls)
        return super().__init_subclass__(**kwargs)
    

    @classmethod
    def configure_registered(cls, **kwargs):
        """
        Configures the registered workflow
        """
        new = copy.deepcopy(cls)
        if kwargs.get('name'): new.name = kwargs.pop('name')
        if 'namespace' in kwargs: new.namespace = kwargs.pop('namespace')
        if 'mixin_kind' in kwargs: new.mixin_kind = kwargs.pop('mixin_kind')
        if 'config' in kwargs: new.config = kwargs.pop('config')
        if 'disable_registration' in kwargs: new.disable_registration = kwargs.pop('disable_registration')
        if kwargs: new._rxtra.update(kwargs)
        return new

    @classmethod
    def _configure_display_name_(cls) -> str:
        """
        Configures the Display Name for the Mixin

        Allows for more flexible customization of the display name
        """
        if cls.display_name: return cls.display_name
        name_opts: t.Dict[str, bool] = cls.config.get('name_options', {})
        # logger.info(name_opts, prefix = 'Temporal')
        # logger.info(cls._rxtra, prefix = 'Temporal')
        if cls.config.get('disable_full_name'):
            if name_opts.get('use_class_name', not cls.name):
                if name_opts.get('use_full_module_name', False):
                    cls.display_name = f'{cls._rxtra["module_prefix"]}.{cls._rxtra["cls_name"]}'
                else:
                    cls.display_name = cls._rxtra['cls_name']
            else:
                cls.display_name = cls.name or cls._rxtra['base_name']
            return cls.display_name
        
        name = ''
        if name_opts.get('prefix'): name += f'{name_opts["prefix"]}.'
        if name_opts.get('include_module', True) and '__main__' not in cls._rxtra['module']: 
            if name_opts.get('use_full_module_name', False):
                name += f'{cls._rxtra["module_prefix"]}.'
            else:
                name += f'{cls._rxtra["module"]}.'
        # logger.info(f'Pre Name {name}', prefix = 'Temporal')
        if name_opts.get('include_namespace', bool(cls.namespace)) and cls.namespace: name += f'{cls.namespace}.'
        if name_opts.get('name_extra'): name += f'{name_opts["name_extra"]}.'
        if name_opts.get('use_class_name', not cls.name):
            if cls._rxtra['module'] not in name:
                name += f'{cls._rxtra["cls_name"]}'
            else:
                name += f'{cls._rxtra["base_name"]}'
        else:
            name += f'{cls.name or cls._rxtra["base_name"]}'
        if name_opts.get('postfix'): name += f'.{name_opts["postfix"]}'
        # logger.info(f'Name {name}', prefix = 'Temporal')
        cls.display_name = name
        return cls.display_name
    
    @classmethod
    def _configure_gen_id_(cls) -> None:
        """
        Configures the ID Generator Prefix
        """
        gen_opts: t.Dict[str, t.Any] = cls.config.get('id_gen_opts', {})
        if cls.id_gen is None:
            cls.id_gen = IDGenOptions(**gen_opts)
        else:
            cls.id_gen = cls.id_gen.merge_from_config(gen_opts)
        # logger.info(f'ID Generator Options: {cls.id_gen}', prefix = 'Temporal')

    @classmethod
    def generate_id_(cls, *args, **kwargs) -> str:
        """
        Generates the ID
        """
        return default_id_gen_function(cls, *args, **kwargs)

    def generate_id(self, *args, **kwargs) -> str:
        """
        Generates the ID
        """
        return default_id_gen_function(self, *args, **kwargs)

    @classmethod
    def _update_attrs_from_config_(
        cls,
        envvar: str,
        env_mode: t.Literal['global', 'localized'] = 'localized',
        update_attrs: t.Optional[bool] = True,
        key: t.Optional[str] = None,
        app_env: t.Optional['AppEnv' | str] = None,
        **kwargs,
    ) -> t.Dict[str, t.Any] | None:
        """
        Updates the workflow attributes from the config
        """
        import os
        import yaml
        import pathlib

        if not (envfile := os.getenv(envvar)): return
        envfile = pathlib.Path(envfile)
        if not envfile.exists(): 
            logger.warning(f'Environment File does not exist: {envfile}')
            return
        envdata: t.Union[t.Dict[str, t.Any], t.Dict[t.Dict[str, t.Any]]] = yaml.safe_load(envfile.read_text())
        if cls.mixin_kind and cls.mixin_kind in envdata: envdata = envdata[cls.mixin_kind]
        if key: envdata = envdata.get(key, {})
        if env_mode == 'localized' and app_env:
            if hasattr(app_env, 'name'): envdata = envdata.get(app_env.name, {})
            else: envdata = envdata.get(app_env, {})
        if not envdata: return
        if not update_attrs: return envdata
        for key, value in envdata.items():
            if hasattr(cls, key): cls._update_attr_(key, value)

    @classmethod
    def _update_attr_(cls, key: str, value: t.Any):
        """
        Updates an attribute
        """
        attr = getattr(cls, key)
        if not attr:
            setattr(cls, key, value)
            return
        # We only care about merging dicts
        if isinstance(attr, dict):
            from lzo.utils.helpers import update_dict
            value = update_dict(attr, value)
            setattr(cls, key, value)
            return
        setattr(cls, key, value)

    
    def __init__(self, *args, **kwargs):
        """
        Initializes the workflow

        Triggers the following methods in order:

        _ _pre_init_(*args, **kwargs)
        - _init_(*args, **kwargs)
        - _configure_init_(*args, **kwargs)
        - _post_init_(*args, **kwargs)
        - _finalize_init_(*args, **kwargs)
        - _show_init_(*args, **kwargs)
        """
        from lzo.utils import Timer
        self._extra: t.Dict[str, t.Any] = {}
        self.timer = Timer
        self.logger = logger
        self.null_logger = null_logger
        self.app_env: t.Optional['AppEnv'] = None
        self._pre_init_(*args, **kwargs)
        self._init_(*args, **kwargs)
        self._configure_init_(*args, **kwargs)
        self._post_init_(*args, **kwargs)
        self._finalize_init_(*args, **kwargs)
        self._show_init_(*args, **kwargs)
        logger.info(f'Initialized {self.name}', prefix = self.display_name, colored = True)


    def _pre_init_(self, *args, **kwargs):
        """
        Pre-Initializes the Object
        """
        pass

    def _init_(self, *args, **kwargs):
        """
        Initializes the Object
        """
        pass

    def _configure_init_(self, *args, **kwargs):
        """
        Configures the Object
        """
        pass

    def _post_init_(self, *args, **kwargs):
        """
        Post-initializes the Object
        """
        pass

    def _finalize_init_(self, *args, **kwargs):
        """
        Finalizes the Object
        """
        pass

    def _show_init_(self, *args, **kwargs):
        """
        Shows the Object
        """
        self._display_()

    
    def _display_(self, **kwargs):  # sourcery skip: use-join
        """
        Displays the configuration
        """
        pass

    @property
    def autologger(self) -> 'Logger':
        """
        Returns the auto logger
        """
        if self.verbosity:
            if self.verbosity < 0:
                return self.null_logger
            if self.verbosity > 1:
                return self.logger
        return self.logger if self.app_env and self.app_env.is_devel else self.null_logger

    @eproperty
    def registry(self) -> 'TemporalRegistry':
        """
        Returns the Temporal registry
        """
        from .registry import registry
        return registry
    
    @property
    def registry_name(self) -> str:
        """
        Returns the registry name
        """
        return self._rxtra['registry_name']
    
    """
    Common Class Methods
    """
    @classmethod
    def _file(cls, *paths: str) -> 'FileLike':
        """
        Returns the file
        """
        from lzl.io.file import File
        return File(*paths)

    @classmethod
    def _get_tmprl_ref_(
        cls, 
        registry_name: t.Optional[str] = None,
        module: t.Optional[str] = None,
        namespace: t.Optional[str] = None,
        name: t.Optional[str] = None,
        display_name: t.Optional[str] = None,
        as_type: t.Optional[bool] = None,
        kind: t.Optional['MixinKinds'] = 'workflow',
    ) -> t.Union['TemporalWorkflowT', 'TemporalActivityT']:
        """
        Gets a Temporal Object
        """
        from .registry import registry
        return registry.get_ref(
            registry_name = registry_name,
            module = module,
            namespace = namespace,
            name = name,
            display_name = display_name,
            as_type = as_type,
            kind = kind,
        )
        


    """
    Common Helper Methods
    """

    def get_next_cron_run(
        self,
        schedule: str,
        verbose: t.Optional[bool] = None,
        colored: t.Optional[bool] = None,
        **kwargs,
    ) -> t.Optional[t.Dict[str, t.Any]]:
        """
        Returns the next cron run
        """
        import croniter, datetime
        utc_date = datetime.datetime.now(tz = datetime.timezone.utc)
        next_date: datetime.datetime = croniter.croniter(schedule, utc_date).get_next(datetime.datetime)
        total_seconds = (next_date - utc_date).total_seconds()
        next_interval, next_unit = total_seconds, "secs"
        # Reverse the order
        if next_interval > (60 * 60 * 24):
            next_interval /= (60 * 60 * 24)
            next_unit = "days"
        elif next_interval > (60 * 60):
            next_interval /= (60 * 60)
            next_unit = "hrs"
        elif next_interval > 60:
            next_interval /= 60
            next_unit = "mins"
        if colored: msg = f'Next Scheduled Run in |g|{next_interval:.2f} {next_unit}|e| at |g|{next_date}|e|'
        else: msg = f'Next Scheduled Run in {next_interval:.2f} {next_unit} at {next_date}'
        if verbose: self.logger.info(f'Next Scheduled Run in |g|{next_interval:.2f} {next_unit}|e| at |g|{next_date}|e| ({self.workflow_name})', colored = True, hook = log_hook)
        return {
            'next_date': next_date,
            'next_interval': next_interval,
            'next_unit': next_unit,
            'total_seconds': total_seconds,
            'message': msg,
        }
    
    if t.TYPE_CHECKING:
        async def run(self, arg: ParamType, *args, **kwargs) -> ReturnType:
            """
            Runs the Temporal Object
            """
            ...



class TemporalWorkflowMixin(BaseTemporalMixin):
    """
    [Temporal] Workflow Mixin that will automatically registered
    """

    mixin_kind: t.Optional[MixinKinds] = 'workflow'
    _is_subclass_: t.Optional[bool] = True

    # These will be passed to the workflow defn decorator
    sandboxed: t.Optional[bool] = None
    dynamic: t.Optional[bool] = None
    failure_exception_types: t.Optional[t.Sequence[t.Type[BaseException]]] = None
    enable_init: t.Optional[bool] = None

    @classmethod
    def configure_registered(cls, **kwargs):
        """
        Configures the registered workflow
        """
        _kws = {k: kwargs.pop(k) for k in kwargs if k in {'sandboxed', 'dynamic', 'failure_exception_types'}}
        new = super().configure_registered(**kwargs)
        if 'sandboxed' in _kws: new.sandboxed = _kws.pop('sandboxed')
        if 'dynamic' in _kws: new.dynamic = _kws.pop('dynamic')
        if _kws.get('failure_exception_types'): new.failure_exception_types = _kws.pop('failure_exception_types')
        return new

    @classmethod
    def _on_register_hook_(cls):
        """
        Runs the workflow hook
        """
        pass

class TemporalActivityMixin(BaseTemporalMixin):
    """
    [Temporal] Activity Mixin that will automatically registered
    """

    mixin_kind: t.Optional[MixinKinds] = 'activity'
    _is_subclass_: t.Optional[bool] = True

    # These will be passed to the activity defn decorator
    no_thread_cancel_exception: t.Optional[bool] = None
    dynamic: t.Optional[bool] = None

    @classmethod
    def configure_registered(cls, **kwargs):
        """
        Configures the registered activity
        """
        _kws = {k: kwargs.pop(k) for k in kwargs if k in {'no_thread_cancel_exception', 'dynamic'}}
        new = super().configure_registered(**kwargs)
        if 'no_thread_cancel_exception' in _kws: new.no_thread_cancel_exception = _kws.pop('no_thread_cancel_exception')
        if 'dynamic' in _kws: new.dynamic = _kws.pop('dynamic')
        return new

    @classmethod
    def _on_register_hook_(cls):
        """
        Runs the activity hook
        """
        pass



TemporalMixinT = t.TypeVar('TemporalMixinT', bound = BaseTemporalMixin)
TmpMixinT = t.TypeVar('TmpMixinT')

TemporalWorkflowT = t.TypeVar('TemporalWorkflowT', bound = TemporalWorkflowMixin)
TemporalActivityT = t.TypeVar('TemporalActivityT', bound = TemporalActivityMixin)


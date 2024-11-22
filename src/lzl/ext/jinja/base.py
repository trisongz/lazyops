from __future__ import annotations

"""
Base Jinja2 Extension
"""


import jinja2
import typing as t
from jinja2 import FileSystemLoader
from lzl.types import eproperty
from lzl.types import Literal
from .filters import autofilters
from typing import Optional, Generic, TypeVar, TYPE_CHECKING, overload, Dict, Any

if TYPE_CHECKING:
    from jinja2.environment import Template
    from jinja2.environment import (
        BLOCK_START_STRING,
        BLOCK_END_STRING,
        VARIABLE_START_STRING,
        VARIABLE_END_STRING,
        COMMENT_START_STRING,
        COMMENT_END_STRING,
        LINE_STATEMENT_PREFIX,
        LINE_COMMENT_PREFIX,
        TRIM_BLOCKS,
        LSTRIP_BLOCKS,
        NEWLINE_SEQUENCE,
        KEEP_TRAILING_NEWLINE,
        Extension,
        Undefined,
        BaseLoader,
        BytecodeCache,
    )

J2EnvT = TypeVar('J2EnvT', bound = jinja2.Environment)

class Environment(Generic[J2EnvT]):

    include_autofilters: Optional[bool] = True
    default_mode: Optional[Literal['async', 'sync']] = 'sync'


    _extra: Dict[str, Any] = {}

    
    def __init__(
        self,
        include_autofilters: Optional[bool] = None,
        default_mode: Optional[Literal['async', 'sync']] = None,
        **kwargs
    ):
        """
        Initializes the Environment
        """
        if include_autofilters is not None: self.include_autofilters = include_autofilters
        if default_mode is not None: self.default_mode = default_mode
        _ = kwargs.pop('enable_async', None)
        self._env_kwargs = kwargs
    

    if TYPE_CHECKING:

        def __init__(
            self,
            block_start_string: str = BLOCK_START_STRING,
            block_end_string: str = BLOCK_END_STRING,
            variable_start_string: str = VARIABLE_START_STRING,
            variable_end_string: str = VARIABLE_END_STRING,
            comment_start_string: str = COMMENT_START_STRING,
            comment_end_string: str = COMMENT_END_STRING,
            line_statement_prefix: t.Optional[str] = LINE_STATEMENT_PREFIX,
            line_comment_prefix: t.Optional[str] = LINE_COMMENT_PREFIX,
            trim_blocks: bool = TRIM_BLOCKS,
            lstrip_blocks: bool = LSTRIP_BLOCKS,
            newline_sequence: Literal['\\n', '\\r\\n', '\\r'] = NEWLINE_SEQUENCE, 
            keep_trailing_newline: bool = KEEP_TRAILING_NEWLINE,
            extensions: t.Sequence[t.Union[str, t.Type["Extension"]]] = (),
            optimized: bool = True,
            undefined: t.Type[Undefined] = Undefined,
            finalize: t.Optional[t.Callable[..., t.Any]] = None,
            autoescape: t.Union[bool, t.Callable[[t.Optional[str]], bool]] = False,
            loader: t.Optional["BaseLoader"] = None,
            cache_size: int = 400,
            auto_reload: bool = True,
            bytecode_cache: t.Optional["BytecodeCache"] = None,
            include_autofilters: Optional[bool] = None,
            default_mode: Optional[Literal['async', 'sync']] = None,
        ):
            r"""The core component of Jinja is the `Environment`.  It contains
            important shared variables like configuration, filters, tests,
            globals and others.  Instances of this class may be modified if
            they are not shared and if no template was loaded so far.
            Modifications on environments after the first template was loaded
            will lead to surprising effects and undefined behavior.

            Here are the possible initialization parameters:

                `block_start_string`
                    The string marking the beginning of a block.  Defaults to ``'{%'``.

                `block_end_string`
                    The string marking the end of a block.  Defaults to ``'%}'``.

                `variable_start_string`
                    The string marking the beginning of a print statement.
                    Defaults to ``'{{'``.

                `variable_end_string`
                    The string marking the end of a print statement.  Defaults to
                    ``'}}'``.

                `comment_start_string`
                    The string marking the beginning of a comment.  Defaults to ``'{#'``.

                `comment_end_string`
                    The string marking the end of a comment.  Defaults to ``'#}'``.

                `line_statement_prefix`
                    If given and a string, this will be used as prefix for line based
                    statements.  See also :ref:`line-statements`.

                `line_comment_prefix`
                    If given and a string, this will be used as prefix for line based
                    comments.  See also :ref:`line-statements`.

                    .. versionadded:: 2.2

                `trim_blocks`
                    If this is set to ``True`` the first newline after a block is
                    removed (block, not variable tag!).  Defaults to `False`.

                `lstrip_blocks`
                    If this is set to ``True`` leading spaces and tabs are stripped
                    from the start of a line to a block.  Defaults to `False`.

                `newline_sequence`
                    The sequence that starts a newline.  Must be one of ``'\r'``,
                    ``'\n'`` or ``'\r\n'``.  The default is ``'\n'`` which is a
                    useful default for Linux and OS X systems as well as web
                    applications.

                `keep_trailing_newline`
                    Preserve the trailing newline when rendering templates.
                    The default is ``False``, which causes a single newline,
                    if present, to be stripped from the end of the template.

                    .. versionadded:: 2.7

                `extensions`
                    List of Jinja extensions to use.  This can either be import paths
                    as strings or extension classes.  For more information have a
                    look at :ref:`the extensions documentation <jinja-extensions>`.

                `optimized`
                    should the optimizer be enabled?  Default is ``True``.

                `undefined`
                    :class:`Undefined` or a subclass of it that is used to represent
                    undefined values in the template.

                `finalize`
                    A callable that can be used to process the result of a variable
                    expression before it is output.  For example one can convert
                    ``None`` implicitly into an empty string here.

                `autoescape`
                    If set to ``True`` the XML/HTML autoescaping feature is enabled by
                    default.  For more details about autoescaping see
                    :class:`~markupsafe.Markup`.  As of Jinja 2.4 this can also
                    be a callable that is passed the template name and has to
                    return ``True`` or ``False`` depending on autoescape should be
                    enabled by default.

                    .. versionchanged:: 2.4
                    `autoescape` can now be a function

                `loader`
                    The template loader for this environment.

                `cache_size`
                    The size of the cache.  Per default this is ``400`` which means
                    that if more than 400 templates are loaded the loader will clean
                    out the least recently used template.  If the cache size is set to
                    ``0`` templates are recompiled all the time, if the cache size is
                    ``-1`` the cache will not be cleaned.

                    .. versionchanged:: 2.8
                    The cache size was increased to 400 from a low 50.

                `auto_reload`
                    Some loaders load templates from locations where the template
                    sources may change (ie: file system or database).  If
                    ``auto_reload`` is set to ``True`` (default) every time a template is
                    requested the loader checks if the source changed and if yes, it
                    will reload the template.  For higher performance it's possible to
                    disable that.

                `bytecode_cache`
                    If set to a bytecode cache object, this object will provide a
                    cache for the internal Jinja bytecode so that templates don't
                    have to be parsed if they were not changed.

                    See :ref:`bytecode-cache` for more information.
            """



    @eproperty
    def env(self) -> J2EnvT:
        """
        [Non-Async] Returns the Environment
        """
        new_env = jinja2.Environment(**self._env_kwargs)
        if self.include_autofilters:
            new_env.filters.update(autofilters)
        return new_env
    
    @eproperty
    def aenv(self) -> J2EnvT:
        """
        [Async] Returns the Environment
        """
        new_env = jinja2.Environment(**self._env_kwargs, enable_async = True)
        if self.include_autofilters:
            new_env.filters.update(autofilters)
        return new_env
    
    def _get_env(self, mode: Optional[Literal['async', 'sync']] = None) -> J2EnvT:
        """
        Returns the Environment
        """
        if mode is None: mode = self.default_mode
        return self.aenv if mode == 'async' else self.env
    
    def _run_env_func(self, func: str, *args, **kwargs) -> Any:
        """
        Runs a function on the Environment
        """
        getattr(self.env, func)(*args, **kwargs)
        getattr(self.aenv, func)(*args, **kwargs)

            
    def get_template(
        self,
        name: t.Union[str, "Template"],
        parent: t.Optional[str] = None,
        globals: t.Optional[t.MutableMapping[str, t.Any]] = None,
        mode: t.Optional[Literal['async', 'sync']] = None,
        is_raw: t.Optional[bool] = None,
    ) -> "Template":
        """Load a template by name with :attr:`loader` and return a
        :class:`Template`. If the template does not exist a
        :exc:`TemplateNotFound` exception is raised.

        :param name: Name of the template to load. When loading
            templates from the filesystem, "/" is used as the path
            separator, even on Windows.
        :param parent: The name of the parent template importing this
            template. :meth:`join_path` can be used to implement name
            transformations with this.
        :param globals: Extend the environment :attr:`globals` with
            these extra variables available for all renders of this
            template. If the template has already been loaded and
            cached, its globals are updated with any new items.

        .. versionchanged:: 3.0
            If a template is loaded from cache, ``globals`` will update
            the template's globals instead of ignoring the new values.

        .. versionchanged:: 2.4
            If ``name`` is a :class:`Template` object it is returned
            unchanged.
        """
        _env = self._get_env(mode)
        if is_raw:  return _env.from_string(name)
        return _env.get_template(name, parent, globals)

    def add_extension(self, extension: t.Union[str, t.Type["Extension"]]) -> None:
        """Adds an extension after the environment was created.

        .. versionadded:: 2.5
        """
        self._run_env_func('add_extension', extension)

    def extend(self, **attributes: t.Any) -> None:
        """Add the items to the instance of the environment if they do not exist
        yet.  This is used by :ref:`extensions <writing-extensions>` to register
        callbacks and configuration values without breaking inheritance.
        """
        self._run_env_func('extend', **attributes)

    
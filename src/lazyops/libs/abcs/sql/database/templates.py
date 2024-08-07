from __future__ import annotations

"""
Template Manager
"""

import abc
from pathlib import Path
from typing import Optional, Any, Dict, List, Union, Type, TYPE_CHECKING

if TYPE_CHECKING:
    import jinja2
    from lazyops.libs.abcs.configs.base import AppSettings


class SQLTemplates(abc.ABC):
    """
    SQL Template Manager
    """

    name: Optional[str] = None
    base_path: Union[str, Path] = None
    file_suffix: Optional[str] = '.sql'

    def __init__(
        self, 
        
        name: Optional[str] = None,
        base_path: Union[str, Path] = None, 
        file_suffix: Optional[str] = None,
        settings: Optional['AppSettings'] = None,
        module_name: Optional[str] = None,
    ):
        """
        Initializes the SQL Template Manager
        """
        if base_path: self.base_path = base_path
        if file_suffix: self.file_suffix = file_suffix
        if name is not None: self.name = name
        if settings is None:
            from lazyops.libs.abcs.configs.lazy import get_module_settings
            settings = get_module_settings(module_name or self.__module__.__name__)
        
        self.settings = settings
        if self.name is None:
            self.name = f'{self.settings.module_name}_sql'
        self._j2: Optional['jinja2.Environment'] = None
        self._aj2: Optional['jinja2.Environment'] = None

    @property
    def j2(self) -> 'jinja2.Environment':
        """
        Returns the jinja2 context
        """
        if self._j2 is None:
            self._j2 = self.settings.ctx.get_j2_ctx(
                path = self.base_path or 'assets/sql',
                name = self.name,
                enable_async = False,
                comment_start_string='/*',
                comment_end_string='*/',
            )
        return self._j2
    
    @property
    def aj2(self) -> 'jinja2.Environment':
        """
        Returns the jinja2 context
        """
        if self._aj2 is None:
            self._aj2 = self.settings.ctx.get_j2_ctx(
                path = self.base_path or 'assets/sql',
                name = self.name,
                enable_async = True,
                comment_start_string='/*',
                comment_end_string='*/',
            )
        return self._aj2
    
    def get_template(self, *parts: str) -> 'jinja2.Template':
        """
        Gets the template
        """
        if not parts[-1].endswith(self.file_suffix):
            parts = list(parts[:-1]) + [parts[-1] + self.file_suffix]
        return self.j2.get_template('/'.join(parts))
    
    def aget_template(self, *parts: str) -> 'jinja2.Template':
        """
        Gets the template
        """
        if not parts[-1].endswith(self.file_suffix):
            parts = list(parts[:-1]) + [parts[-1] + self.file_suffix]
        return self.aj2.get_template('/'.join(parts))
        

    def render(self, *parts: str, **kwargs) -> str:
        """
        Renders the template
        """
        return self.get_template(*parts).render(**kwargs)
    

    async def arender(self, *parts: str, **kwargs) -> str:
        """
        Renders the template
        """
        # template = self.aget_template(*parts)
        # template.
        return await self.aget_template(*parts).render_async(**kwargs)
    
    def __call__(
        self,
        *parts: str,
        enable_async: bool = False,
        **kwargs,
    ) -> str:
        """
        Renders the template
        """
        if enable_async:
            return self.arender(*parts, **kwargs)
        return self.render(*parts, **kwargs)
    
    def __getitem__(self, name: str) -> 'jinja2.Template':
        """
        Gets the template
        """
        parts = name.split('.')
        return self.get_template(*parts)
    
    @property
    def sql_path(self) -> Path:
        """
        Returns the SQL Path
        """
        if self.base_path and isinstance(self.base_path, Path):
            return self.base_path
        p = self.base_path or 'assets/sql'
        if isinstance(p, str):
            p = self.settings.module_path.joinpath(p)
        return p
    
    def get_migration_sqls(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        path: Optional[Union[str, Path]] = None,
    ) -> List[str]:
        """
        Returns the migration sqls
        """
        sqls = []
        path = path or 'migrations'
        if isinstance(path, str):
            path = self.sql_path.joinpath(path)
        if not path.exists(): return sqls
        for name in path.iterdir():
            if name.suffix != '.sql': continue
            name_stem = name.stem.split('.', 1)[0]
            if include and name_stem not in include: continue
            if exclude and name_stem in exclude: continue
            sqls.append(name_stem)
        return sqls






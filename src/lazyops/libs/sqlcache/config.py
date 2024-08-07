import dill
from pydantic import BaseModel, Field, root_validator
from pydantic.types import ByteSize
from typing import Union, Any, Dict, Optional
from lazyops.configs.base import DefaultSettings
from lazyops.types import lazyproperty
from lazyops.libs.sqlcache.constants import DEFAULT_SETTINGS, OPTIMIZED_SETTINGS, DBNAME

def get_eviction_policies(table_name: str):
    return {
        'none': {
            'init': None,
            'get': None,
            'cull': None,
        },
        'least-recently-stored': {
            'init': (
                f'CREATE INDEX IF NOT EXISTS {table_name}_store_time ON'
                f' {table_name} (store_time)'
            ),
            'get': None,
            'cull': 'SELECT {fields} FROM ' + table_name + ' ORDER BY store_time LIMIT ?',
        },
        'least-recently-used': {
            'init': (
                f'CREATE INDEX IF NOT EXISTS {table_name}_access_time ON'
                f' {table_name} (access_time)'
            ),
            'get': 'access_time = {now}',
            'cull': 'SELECT {fields} FROM ' + table_name + ' ORDER BY access_time LIMIT ?',
        },
        'least-frequently-used': {
            'init': (
                f'CREATE INDEX IF NOT EXISTS {table_name}_access_count ON'
                f' {table_name} (access_count)'
            ),
            'get': 'access_count = access_count + 1',
            'cull': 'SELECT {fields} FROM ' + table_name + ' ORDER BY access_count LIMIT ?',
        },
    }


class SqlCacheSettings(DefaultSettings):
    """
    Settings for the SqlCache.
    """

    class Config(DefaultSettings.Config):
        env_prefix = 'SQLCACHE_'
        case_sensitive = False
    

class SqlCacheConfig(BaseModel):

    table_name: str = 'sqlcache'
    db_name: str = DBNAME
    statistics: Union[int, bool] = False
    tag_index: Union[int, bool] = False
    eviction_policy: str = 'least-recently-stored'
    size_limit: ByteSize = Field(default = OPTIMIZED_SETTINGS['standard']['size_limit'])
    cull_limit: int = 10
    sqlite_auto_vacuum: int = 1  # FULL
    cache_size: int = 2 ** 13  # 8,192 pages
    sqlite_journal_mode: str = 'wal'
    mmap_size: ByteSize = Field(default = OPTIMIZED_SETTINGS['standard']['mmap_size']) # 2**26  # 64mb
    sqlite_synchronous: int = 1  # NORMAL
    disk_min_file_size: ByteSize = Field(default = OPTIMIZED_SETTINGS['standard']['min_file_size']) # 2**15  # 32kb
    disk_pickle_protocol: int = 4
    compression_level: int = Field(default = OPTIMIZED_SETTINGS['standard']['compression_level'])
    dataset_mode: bool = False # if enabled, will start Index at 0 rather than 500 trill

    @root_validator(pre = True)
    def validate_config(cls, values: Dict) -> Dict:
        """
        Ensures that the configuration is valid.
        """
        if 'statistics' in values and isinstance(values['statistics'], bool):
            values['statistics'] = int(values['statistics'])
        if 'tag_index' in values and isinstance(values['tag_index'], bool):
            values['tag_index'] = int(values['tag_index'])
        return values

    @classmethod
    def from_optimized(cls, table_name: str, optim: Optional[str] = 'standard', config: Optional[Dict[str, Any]] = None) -> 'SqlCacheConfig':
        """
        Allows for the creation of a SqlCacheConfig object from a pre-defined
        optimized configuration. The `config` parameter allows for the
        """

        assert optim in OPTIMIZED_SETTINGS, f'Invalid optimization: {optim}'
        base_config = OPTIMIZED_SETTINGS[optim].copy()
        if config: base_config.update(config)
        return cls(table_name = table_name, **base_config)

    @property
    def start_index_n(self):
        return 0 if self.dataset_mode else 500000000000000

    @property
    def sql_settings(self) -> Dict[str, Any]:
        return {
            'statistics': self.statistics,  # False
            'tag_index': self.tag_index,  # False
            'eviction_policy': self.eviction_policy,
            'size_limit': self.size_limit,
            'cull_limit': self.cull_limit,
            'sqlite_auto_vacuum': self.sqlite_auto_vacuum, 
            'sqlite_cache_size': self.cache_size,
            'sqlite_journal_mode': self.sqlite_journal_mode,
            'sqlite_mmap_size': self.mmap_size,
            'sqlite_synchronous': self.sqlite_synchronous,  # NORMAL
            'disk_min_file_size': self.disk_min_file_size,
            'disk_pickle_protocol': self.disk_pickle_protocol,
        }

    @property
    def eviction_policy_config(self):
        return get_eviction_policies(self.table_name)[self.eviction_policy]
    


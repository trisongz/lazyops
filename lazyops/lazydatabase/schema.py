import sys
from ._base import *
from ._base import _lazydb_logger, _lazydb_picker

logger = _lazydb_logger
pkler = _lazydb_picker

# Base Class for the File-backed LazyDB Cache.
class LazyDBCacheBase(abc.ABC):
    def __init__(self, save_path=None, cache_name='lazycache', *args, **kwargs):
        self._cachename = cache_name
        self.save_path = save_path or _lazydb_default_cache_path
        fio.mkdirs(self.save_path)
        self.lock = threading.RLock()
        self._args = args
        self._kwargs = kwargs

    @property
    def cache_file(self):
        return self._cachename + '.lazydb'

    @property
    def cache_filepath(self):
        return fio.join(self.save_path, self.cache_file)
    
    @property
    def exists(self):
        return fio.exists(self.cache_filepath)

    @abc.abstractmethod
    def dumps(self, data, *args, **kwargs):
        pass
    
    @abc.abstractmethod
    def loads(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def restore(self, *args, **kwargs):
        pass
    
    @abc.abstractmethod
    def save(self, db, *args, **kwargs):
        pass

class JSONDBCache(LazyDBCacheBase):
    def dumps(self, data, *args, **kwargs):
        pass
    
    def loads(self, *args, **kwargs):
        pass

    def restore(self, *args, **kwargs):
        pass
    
    def save(self, db, *args, **kwargs):
        pass

class PklDBCache(LazyDBCacheBase):
    def dumps(self, data, *args, **kwargs):
        return pkler.dumps(data, *args, **kwargs)
    
    def loads(self, data, *args, **kwargs):
        return pkler.loads(data, *args, **kwargs)

    def restore(self, *args, **kwargs):
        self.lock.acquire()
        dbdata = {}
        with self.lock:
            try:
                dbdata = fio.pklload(self.cache_filepath)
                logger.info(dbdata)
                logger.info(dbdata.items())
            except Exception as e:
                logger.error(f'Failed to Restore DB {self._cachename}: {str(e)}')
                logger.error(f'Copying DB to Backup')
                tempfn = fio.mod_fname(self.cache_filepath, suffix='_' + tstamp())
                fio.copy(self.cache_filepath, tempfn)
                logger.error(f'DB saved to {tempfn}')
        self.lock.release()
        return dbdata
    
    def save(self, dbdata, *args, **kwargs):
        _saved = False
        self.lock.acquire()
        with self.lock:
            try:
                fio.pklsave(dbdata, self.cache_filepath)
                _saved = True
            except Exception as e:
                logger.error(f'Failed to Save DB {self._cachename}: {str(e)}')
                _saved = False
        self.lock.release()
        return _saved



LazyDBCacheType = TypeVar("LazyDBCacheType", bound=LazyDBCacheBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class LazyDBIndex:
    def __init__(self, name, schema):
        self.name = name
        self.base_schema = schema
        self.create_schema()
        self.index = {}
        self.lookup = {}
        self.idx = 0
    
    def create_schema(self):
        if isinstance(self.base_schema, str):
            self.base_schema = sjson_loads(self.base_schema)
        assert isinstance(self.base_schema, dict), 'Schema must be a Dict or String that is JSON Decodable'
        self.schema = create_model(self.name, **self.id_schema, **self.base_schema)
        self.schema_props = list(self.schema.schema()['properties'].keys())
        setattr(sys.modules[self.schema.__module__], self.schema.__name__, self.schema)


    def validate_idx(self, id: int = None, dbid: str = None, *args, **kwargs):
        if id and self.index.get(id):
            return id
        if dbid and self.lookup.get(dbid):
            return self.lookup[dbid]
        return None

    def get_by_id(self, id: int = None, dbid: str = None, *args, **kwargs):
        idx = self.validate_idx(id, dbid, *args, **kwargs)
        if not idx:
            return None
        return self.index.get(idx)
    
    def match_props(self, item, name, val, *args, **kwargs):
        item_data = jsonable_encoder(item)
        if not item_data.get(name):
            return False
        by_type = kwargs.get('ByType', False)
        if by_type:
            return isinstance(item_data[name], val)
        # Prop in list
        if isinstance(val, list) and isinstance(item_data[name], str):
            return bool(item_data[name] in val)
        # val in item's list
        if isinstance(val, str) and isinstance(item_data[name], list):
            return bool(val in item_data[name])
        # not NoneType
        if isinstance(val, str) and val == 'NotNone':
            return bool(item_data[name] is not None)
        if isinstance(val, str) and val == 'NotNoneType':
            return isinstance(item_data[name], NoneType)
        return item_data[name] == val

    def get_by_props(self, props: Dict[str, Any], forward=True, *args, **kwargs):
        if not props:
            return None
        search_range = range(self.idx) if forward else range(self.idx, 0, -1)
        for idx in search_range:
            if self.index.get(idx):
                item = self.index[idx]
                for name, val in props.items():
                    if name not in self.schema_props:
                        continue
                    if self.match_props(item, name, val, *args, **kwargs):
                        return item
        
        return None

    def get(self, id: int = None, dbid: str = None, props: Dict[str, Any] = None, *args, **kwargs):
        return self.get_by_props(props=props, *args, **kwargs) if props else self.get_by_id(id, dbid, *args, **kwargs)

    def filter_items(self, item_list: List[Any], props: Dict[str, Any] = None, *args, **kwargs):
        res_list = []
        for item in item_list:
            for name, val in props.items():
                if name not in self.schema_props:
                    continue
                if self.match_props(item, name, val, *args, **kwargs):
                    res_list.append(item)
        return res_list

    def get_many(self, id_list: List[int] = None, dbid_list: List[int] = None, props: Dict[str, Any] = None, *args, **kwargs):
        if not id_list and not dbid_list:
            return None
        get_res = [self.get(id=idx) for idx in id_list] if id_list else [self.get(dbid=dbid) for dbid in dbid_list]
        get_res = [i for i in get_res if i]
        if props:
            get_res = self.filter_items(get_res, props, *args, **kwargs)
        return get_res

    def create(self, data, *args, **kwargs):
        new_item = self.schema(id=self.get_idx(), dbid=self.get_dbid(), *args, **data, **kwargs)
        self.index[self.idx] = new_item
        self.lookup[self.current_id] = self.idx
        self.idx += 1
        return new_item
        
    def remove(self, id: int = None, dbid: str = None, *args, **kwargs):
        rm_id = self.validate_idx(id, dbid, *args, **kwargs)
        if not rm_id:
            return None
        item = self.index.pop(rm_id, None)
        _ = self.lookup.pop(item.dbid)
        return rm_id
    
    def update(self, data: Union[UpdateSchemaType, Dict[str, Any]], id: int = None, dbid: str = None, prop_name: str = None, prop_val: Any = None, *args, **kwargs):
        item = self.get(id, dbid, prop_name=prop_name, prop_val=prop_val, *args, **kwargs)
        if not item:
            return None
        obj_data = jsonable_encoder(item)
        update_data = data if isinstance(data, dict) else data.dict(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(item, field, update_data[field])
        idx = item.id
        item.updated = self.get_timestamp()
        self.index[idx] = item
        return self.index[idx]

    @property
    def id_schema(self):
        return {
            'id': (int, Field(default_factory=self.get_idx)),
            'dbid': (str, Field(default_factory=self.get_dbid)),
            'created': (str, Field(default_factory=self.get_timestamp)),
            'updated': (str, Field(default_factory=self.get_timestamp))
        }

    @property
    def current_id(self):
        return f'{self.name}_{self.idx}'
    
    def get_idx(self):
        return self.idx
    
    def get_dbid(self):
        return self.current_id
    
    def get_timestamp(self):
        return tstamp()


@lazyclass
@dataclass
class LazyDBConfig:
    dbschema: Dict[str, Any]
    autosave: bool = True
    savefreq: float = 15.0
    seeddata: Optional[Dict[str, Any]] = None

@dataclass
class LazyDBSaveMetrics:
    created: Optional[str] = None
    num_saved: Optional[int] = 0
    num_loaded: Optional[int] = 0
    last_load: Optional[str] = None
    last_save: Optional[str] = None
    time_alive: Optional[float] = 0

class LazyAny(object):
    def __init__(self, data):
        for k,v in data.items():
            self.__dict__[k] = v

class LazyDBBase(abc.ABC):
    def __init__(self, dbcache: Any, config: LazyDBConfig):
        self.config = config
        self.cache = dbcache
        self.alive = True
        self.lock = threading.RLock()
        self.setup_db_schema()
        self.init_db()
        self.migrate_db()
        self.finalize_init()
    
    def init_db(self):
        if self.cache.exists: 
            dbdata = self.cache.restore()
            self._db = dbdata['db']
            self._alivetime = dbdata['timer']
            self.metrics = dbdata['metrics']
            self.metrics.num_loaded += 1
            self.metrics.last_load = tstamp()
        else:
            self._alivetime = timer()
            self.metrics = LazyDBSaveMetrics(created=tstamp())
    
    def setup_db_schema(self):
        self._db = {}
        logger.info(f'Setting Up DB Schema')
        for name, schema in self.config.dbschema.items():
            self._db[name] = LazyDBIndex(name, schema)
        

            if not self._db.get(name):
                self._db[name] = LazyDBIndex(name, schema)
                logger.info(f'New Schema Added for: {name}')
                if self.cache.exists:
                    self._needs_migrate.append(name)
                else:
                    self._needs_setup.append(name)
                if self.config.seeddata:
                    logger.info(f'Migration Scheduled for New Schema : {name}')
    
    def migrate_db(self):
        if not self.config.seeddata:
            logger.info('No SeedData Provided. Skipping Migration')
        for schema_name, index in  self._db.items():
            if index.idx == 0 and self.config.seeddata.get(schema_name):
                logger.info(f'Running Migration for {schema_name}')
                for item in self.config.seeddata[schema_name]:
                    i = self._db[schema_name].create(data=item)
                    logger.info(f'Created Item [{schema_name}] = ID: {i.id}, DBID: {i.dbid}')

        logger.info(f'Completed all Setup and Migration Tasks')
        self.save_db()

    def save_db(self):
        self.metrics.last_save = tstamp()
        self.metrics.num_saved += 1
        self.metrics.time_alive = self._alivetime.ablstime
        dbdata = {'db': self._db, 'timer': self._alivetime, 'metrics': self.metrics}
        self.cache.save(dbdata)

    def finalize_init(self):
        self.db = LazyAny(self._db)
        self.env = LazyEnv
        if self.config.autosave:
            self.env.enable_watcher()
            self.t = threading.Thread(target=self.background)
            self.t.start()
            self.env.add_thread(self.t)

    def background(self):
        logger.info(f'DB AutoSaver Active. Saving Every: {self.config.savefreq} secs')
        microsleep = self.config.savefreq / 20
        while self.alive:
            for _ in range(20):
                time.sleep(microsleep)
                if self.env.killed:
                    self.alive = False
                    break
            
            self.save_db()
            if not self.alive:
                break


class LazyDB(LazyDBBase):
    pass





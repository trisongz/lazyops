from ._base import *
import operator as op

logger = get_logger('LazyDB', module='models')

# Base Class for the File-backed LazyDB Backend.
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

@lazyclass
@dataclass
class LazyDBConfig:
    dbschema: Dict[str, Any]
    autosave: bool = True
    autouser: bool = True
    is_dev: bool = True
    savefreq: float = 15.0
    seeddata: Optional[Dict[str, Any]] = None
    userconfigs: Optional[Dict[str, Any]] = None
    hashschema: Optional[Dict[str, Any]] = None
    dbname: Optional[str] = None
    

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
            setattr(self, k, v)


class LazyHasher:
    hasher = CryptContext(schemes=["argon2"], deprecated="auto")
    
    @classmethod
    def create(cls, pass_string: str):
        return LazyHasher.hasher.hash(pass_string)

    @classmethod
    def verify(cls, pass_hash: str, pass_string: str):
        return LazyHasher.hasher.verify(pass_string, pass_hash)
    
    @classmethod
    def update(cls, old_hash: str, old_pass: str, new_pass: str, do_verify: bool = True):
        if (do_verify and LazyHasher.verify(old_hash, old_pass)) or not do_verify:
            return LazyHasher.create(new_pass)
        return None
    
    @classmethod
    def create_token(cls):
        return str(uuid4())


class LazyUserSchema(BaseModel):
    role: str = ...
    is_super: bool = False
    username: str = ...
    password: str = ...
    hash_password: str = None

    @classmethod
    def get_schema(cls, config: Dict[str, Any] = None, is_dev: bool = True, *args, **kwargs):
        current_schema = LazyUserSchema.__fields__
        schema_data = {
            field: (vals.type_, ...)
            if vals.required
            else (vals.type_, vals.default)
            for field, vals in current_schema.items()
        }
        if not is_dev: schema_data.pop('password')
        if not config:
            return schema_data
        new_schema = config if isinstance(config, dict) else config.dict(exclude_unset=True)
        for field, values in new_schema.items():
            schema_data[field] = values
        return schema_data
    
    @classmethod
    def get_hash_schema(cls):
        return {'password': 'hash_password'}

# IS = a [val] == b [val]
# NOT = a [val] != b [val]
# IN = a [val, dict.key] in b [list, dict.keys]
# HAS = a [list, dict.values] has b [val, dict.key]


class LazyLink(Enum):
    IS = 0
    NOT = 1
    IN = 2
    HAS = 3


# 

class LazyDBLink:
    def __init__(
        self,
        name: str,
        index,
        method: Optional[LazyLink] = LazyLink.HAS,
        *args, **kwargs):
        pass

    def __ne__(self, o: object) -> bool:
        pass

    def __eq__(self, o: object) -> bool:
        pass

    def __ge__(self, o):
        pass

    def __gt__(self, o):
        pass

    def __lt__(self, o):
        pass

    def __le__(self, o):
        pass


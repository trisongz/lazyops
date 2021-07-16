from ._base import *

class LazyJson:
    serializer = json
    parser = json.Parser()

    @classmethod
    def dumps(cls, obj, *args, **kwargs):
        return LazyJson.serializer.dumps(obj, *args, **kwargs)
    
    @classmethod
    def dump(cls, obj, fileio, indent=2, *args, **kwargs):
        return LazyJson.serializer.dump(obj, fp=fileio, indent=indent, *args, **kwargs)

    @classmethod
    def loads(cls, jsonstring, use_parser=True, recursive=False, ignore_errors=True, *args, **kwargs):
        if use_parser:
            try:
                return LazyJson.parser.parse(jsonstring, recursive=recursive)
            except Exception as e:
                if not ignore_errors:
                    raise ValueError(str(e))
        try:
            return LazyJson.serializer.loads(jsonstring, *args, **kwargs)
        except Exception as e:
            if not ignore_errors:
                raise ValueError(str(e))
        return None

    @classmethod
    def load(cls, fileio, use_parser=True, recursive=False, ignore_errors=True, *args, **kwargs):
        if use_parser:
            try:
                return LazyJson.parser.parse(fileio, recursive=recursive)
            except Exception as e:
                if not ignore_errors:
                    raise ValueError(str(e))
        try:
            return LazyJson.serializer.load(fileio, *args, **kwargs)
        except Exception as e:
            if not ignore_errors:
                raise ValueError(str(e))
        return None

class LazyPickler:
    serializer = pickler
    protocol = pickler.HIGHEST_PROTOCOL

    @classmethod
    def dumps(cls, obj, *args, **kwargs):
        return LazyPickler.serializer.dumps(obj, protocol=LazyPickler.protocol, *args, **kwargs)
    
    @classmethod
    def loads(cls, data, *args, **kwargs):
        return LazyPickler.serializer.loads(data, *args, **kwargs)
    
    @classmethod
    def dump(cls, obj, fileio, *args, **kwargs):
        data = LazyPickler.dumps(obj,  *args, **kwargs)
        fileio.write(data)
        fileio.flush()

    @classmethod
    def load(cls, fileio, *args, **kwargs):
        return LazyPickler.loads(fileio.read(), *args, **kwargs)



class ModeIO(Enum):
    r = 'r'
    rb = 'rb'
    read = 'r'
    read_binary = 'rb'
    a = 'a'
    append = 'a'
    w = 'w'
    wb = 'wb'
    write = 'w'
    write_binary = 'wb'
    rw = 'r+'
    rwb = 'rb+'
    readwrite = 'r+'
    readwrite_binary = 'rb+'
    auto = 'auto'

class FileExtIO(Enum):
    TXT = ['txt', 'text']
    JSON = ['json']
    JSONLINES = ['jsonl', 'jsonlines', 'jlines']
    TORCH = ['bin', '.model']
    PICKLE = ['pkl', 'pickle', 'pb']
    NUMPY = ['numpy', 'npy']
    TFRECORDS = ['tfrecord', 'tfrecords', 'tfr']


class ExtIO:
    def __init__(self, ext: str):
        self._ext = None
        self._src_ext = ext
        for e in FileExtIO:
            if ext in e.value:
                self._ext = FileExtIO[e.name]
                break

    @property
    def appendable_fs(self):
        return [FileExtIO.TXT, FileExtIO.JSONLINES, FileExtIO.TFRECORDS]
    
    @property
    def appendable(self):
        return self._ext in self.appendable_fs 



class LazyIOBase(object):
    __metaclass__ = ABCMeta

    def __init__(
        self,
        filename: str,
        mode: ModeIO = ModeIO.auto,
        allow_deletion: bool = False,
        *args, **kwargs):
        self._setup_file(filename)
        self._mode = ModeIO.append if mode == 'auto' and self.exists else mode
        
        self._io = None
        self._io_closed = True
        self._allow_rm = allow_deletion

        self._args, self._kwargs = args, kwargs
        self.open()
    

    def _setup_file(self, filename: str = None):
        if filename is None:
            return
        self._filename = filename
        self._basename = File.base(filename)
        self._directory = File.getdir(filename)
        File.mkdirs(self._directory)
        self._fext = File.ext(self._filename)
        self._ext = ExtIO(self._fext)


    def open(self, filename: str = None, mode: ModeIO = None):
        mode = mode.value or self.mode
        filename = filename or self._filename
        if not self.is_closed:
            self.close()
        self._io = gfile(self._filename, mode)
        self._io_closed = False
        if not self.exists:
            self._io.write()
            self.flush()

    def close(self):
        if self._io is None:
            return
        self._io.flush()
        self._io.close()
        self._io_closed = True
        self._io = None
    
    def flush(self):
        self._io.flush()
    
    # actual write method per class
    def _write(self, data, *args, **kwargs):
        self._io.write(data)

    def write(self, data, *args, **kwargs):
        self._ensure_open()
        self._write(data, *args, **kwargs)

    def _read(self, *args, **kwargs):
        return self._io.read(*args, **kwargs)
    
    def read(self, *args, **kwargs):
        self._ensure_open()
        return self._read(*args, **kwargs)

    def _readlines(self, *args, **kwargs):
        return self._io.readlines()

    def readlines(self,  *args, **kwargs):
        self._ensure_open()
        return self._readlines(*args, **kwargs)
    
    @timed_cache(120)
    def get_num_lines(self):
        return sum(1 for _ in File.tflines(self._filename))

    @timed_cache(10)
    @property
    def filesize(self):
        self._ensure_open()
        return self._io.size()

    @timed_cache(10)
    def seek(self, offset=None, whence=0, position=None):
        self._ensure_open()
        return self._io.seek(offset, whence, position)

    def _readline(self, *args, **kwargs):
        return self._io.readline()

    def readline(self, *args, **kwargs):
        self._ensure_open()
        return self._readline(*args, **kwargs)

    def _readlines(self, *args, **kwargs):
        return self._io.readline()

    def readlines(self, *args, **kwargs):
        self._ensure_open()
        return self._readlines(*args, **kwargs)
    
    def _tell(self, *args, **kwargs):
        return self._io.tell()

    def tell(self, *args, **kwargs):
        self._ensure_open()
        return self._tell(*args, **kwargs)
    
    def _iterator(self):
        return self

    def __iter__(self):
        return self._iterator()
    
    def _getnext(self):
        return self._io.next()

    def __next__(self):
        return self._getnext()
    
    @property
    def seekable(self):
        self._ensure_open()
        return self._io.seekable()


    def setmode(self, mode: ModeIO = ModeIO.auto):
        if mode.value != self._mode:
            self.close()
        self._mode = mode.value
        self.open()
    
    def setfile(self, filename: str, mode: ModeIO = None, allow_deletion: bool = False, *args, **kwargs):
        self.close()
        self._setup_file(filename)
        if mode is not None:
            self.setmode(mode)
        self._allow_rm = self._allow_rm or allow_deletion
        self._args = args
        if kwargs: self._kwargs.update(kwargs)
        self.open()

    @classmethod
    def modify(cls, filename, new_filename=None, prefix=None, suffix=None, extension=None, directory=None, create_dirs=True, filename_only=False, space_replace=None):
        return File.mod_fname(filename=filename, newname=new_filename, prefix=prefix, suffix=suffix, ext=extension, directory=directory, create_dirs=create_dirs, filename_only=filename_only, space_replace=space_replace)

    # ensures file is still open to do op. Caches clear every 15 secs.
    @timed_cache(15)
    def _ensure_open(self):
        if self.is_closed:
            raise ValueError('File is closed.')

    def compare(self, target_filename):
        from tensorflow.python.lib.io.file_io import filecmp
        return filecmp(self._filename, target_filename)

    @property
    def exists(self):
        return File.exists(self._filename)
    
    @property
    def mode(self):
        return self._mode.value
    
    @property
    def is_closed(self):
        return self._io_closed
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        self.backend = None

    def __del__(self):
        self.close()
        if not self._allow_rm:
            raise ValueError('Config allow_deletion = True must be set to allow del')
        File.rm(self._filename)
    
    def backup(self, filepath: str = None, directory: str = None, suffix: str = 'timestamp', overwrite: bool = False):
        if suffix == 'timestamp': suffix = tstamp()
        backup_fname = self.modify(self._filename, filepath=filepath, directory=directory, suffix=suffix)
        try:
            File.copy(self._filename, backup_fname, overwrite=overwrite)
        except Exception as e:
            logger.error(str(e))
            return None
        return backup_fname


class LazyIOText(LazyIOBase):
    newline = '\n'
    num_write_flush = 1000 # write ops before flushing
    
    def __init__(
        self, 
        filename: str,
        mode: ModeIO = ModeIO.auto,
        allow_deletion: bool = False,
        newline = None,
        num_write_flush = None,
        *args, **kwargs):

        self._io_writes = 0
        self.newline = newline or LazyIOText.newline
        self._num_write_flush = num_write_flush or LazyIOText.num_write_flush
        super(LazyIOText, self).__init__(filename, mode, allow_deletion, *args, **kwargs)
    
    def close(self):
        super(LazyIOText, self).close()
        self._io_writes = 0
    
    def _write(self, data, newline=None, flush=False, *args, **kwargs):
        newline = newline or self.newline
        self._io.write(data)
        self._io.write(newline)
        self._io_writes += 1
        if flush or (self._io_writes % self._num_write_flush == 0):
            self.flush()
    
    def _readlines(self, as_list=True, strip_newline=True, remove_empty_lines=True, *args, **kwargs):
        if not as_list:
            return self._read()
        texts = self._io.readlines()
        if strip_newline:
            texts = [t.strip() for t in texts]
        if remove_empty_lines:
            texts = [t for t in texts if t]
        return texts

class LazyIOJson(LazyIOBase):
    serializer = LazyJson
    
    def __init__(
        self, 
        filename: str,
        mode: ModeIO = ModeIO.read,
        allow_deletion: bool = False,
        serializer = None,
        *args, **kwargs):
        self.serializer = serializer or LazyIOJson.serializer
        super(LazyIOJson, self).__init__(filename, mode, allow_deletion, *args, **kwargs)
    
    def _write(self, data, dump_kwargs={}, *args, **kwargs):
        if self.mode.value not in ['w', 'wb']:
            self.setmode(mode=(ModeIO.write_binary if 'b' in self.mode.value else ModeIO.write))
        self.serializer.dump(data, self._io, **dump_kwargs)
        self.flush()
    
    def _read(self, load_kwargs={}, *args, **kwargs):
        return self.serializer.load(self._io, **load_kwargs)


class LazyIOJsonLines(LazyIOBase):
    newline = '\n'
    num_write_flush = 1000 # write ops before flushing
    serializer = LazyJson

    def __init__(
        self, 
        filename: str,
        mode: ModeIO = ModeIO.auto,
        allow_deletion: bool = False,
        newline = None,
        num_write_flush = None,
        serializer = None,
        *args, **kwargs):

        self._io_writes = 0
        self._line_map = []
        self.newline = newline or LazyIOJsonLines.newline
        self._num_write_flush = num_write_flush or LazyIOJsonLines.num_write_flush
        self.serializer = serializer or LazyIOJsonLines.serializer
        super(LazyIOJsonLines, self).__init__(filename, mode, allow_deletion, *args, **kwargs)

    def close(self):
        super(LazyIOJsonLines, self).close()
        self._io_writes = 0
    
    def _build_line_mapping(self):
        self._line_map.append(0)
        while self._io.readline():
            self._line_map.append(self._io.tell())
    
    def _write(self, data, newline=None, flush=False, dumps_kwargs={}, *args, **kwargs):
        newline = newline or self.newline
        self._io.write(self.serializer.dumps(data, **dumps_kwargs))
        self._io.write(newline)
        self._io_writes += 1
        if flush or (self._io_writes % self._num_write_flush == 0):
            self.flush()
    
    def _iterator(self, ignore_errors=True, loads_kwargs={}, *args, **kwargs):
        for line in self._io:
            try:
                line = self.serializer.loads(line, ignore_errors=ignore_errors, **loads_kwargs)
                if line: yield line
            except StopIteration:
                break
            except Exception as e:
                if not ignore_errors:
                    raise ValueError(str(e))
        

    def _readlines(self, as_iter=False, as_list=True, ignore_errors=True, loads_kwargs={}, *args, **kwargs):
        if as_iter:
            return self._iterator(ignore_errors=ignore_errors, loads_kwargs=loads_kwargs)
        if as_list:
            return [i for i in self._iterator(ignore_errors=ignore_errors, loads_kwargs={'recursive': True})]
        return self._io.readlines()

    def __len__(self):
        if not self._line_map:
            self._build_line_mapping()
        return len(self._line_map)

    @timed_cache(120)
    def get_num_lines(self):
        return self.__len__

    @timed_cache(120)
    def __getitem__(self, idx):
        if not self._line_map:
            self._build_line_mapping()
        self._f.seek(self._line_map[idx])
        return self.serializer.loads(self._f.readline(), ignore_errors=True, recursive=True)


class LazyIOPickle(LazyIOBase):
    
    serializer = LazyPickler
    num_write_flush = 1000 # write ops before flushing
    
    def __init__(
        self, 
        filename: str,
        mode: ModeIO = ModeIO.readwrite_binary,
        allow_deletion: bool = False,
        serializer = None,
        num_write_flush = None,
        *args, **kwargs):

        self._line_map = []
        self._io_writes = 0
        self.serializer = serializer or LazyIOPickle.serializer
        self._num_write_flush = num_write_flush or LazyIOPickle.num_write_flush
        super(LazyIOPickle, self).__init__(filename, mode, allow_deletion, *args, **kwargs)
    
    def _write(self, data, flush=False, dump_kwargs={}, *args, **kwargs):
        if self.mode.value not in ['wb', 'rb+']:
            self.setmode(mode=ModeIO.readwrite_binary)
        #self.serializer.dump(data, self._io, **dump_kwargs)
        self._io.write(self.serializer.dumps(data, **dump_kwargs))
        self._io_writes += 1
        if flush or (self._io_writes % self._num_write_flush == 0):
            self.flush()
    
    def _read(self, load_kwargs={}, *args, **kwargs):
        return self.serializer.load(self._io, **load_kwargs)
    
    def close(self):
        super(LazyIOPickle, self).close()
        self._io_writes = 0
    
    def _build_line_mapping(self):
        self._line_map.append(0)
        while self._io.readline():
            self._line_map.append(self._io.tell())
    
    def __len__(self):
        if not self._line_map:
            self._build_line_mapping()
        return len(self._line_map)

    @timed_cache(120)
    def get_num_lines(self):
        return self.__len__

    @timed_cache(120)
    def __getitem__(self, idx):
        if not self._line_map:
            self._build_line_mapping()
        self._f.seek(self._line_map[idx])
        return self.serializer.loads(self._f.readline(), ignore_errors=True, recursive=True)
    

LazyIOType = TypeVar("LazyIOType", str, LazyIOBase, LazyIOText, LazyIOJson, LazyIOJsonLines, LazyIOPickle)

class LazyIOMultiFile:    
    def __init__(
        self,
        filenames: List[LazyIOType],
        mode: ModeIO = ModeIO.read,
        ):
        self._multi_io = []
        for filename in filenames:
            if isinstance(filename, str):
                pass
        pass


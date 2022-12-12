from ._base import *
from .models import LazyDBCacheBase

logger = get_logger('LazyDB', module='backends')

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

class GSheetsDBCache(LazyDBCacheBase):
    def __init__(self, sheets_url=None, cache_name='LazyCacheDB', auth_path=None, *args, **kwargs):
        self.url = sheets_url
        self.auth = auth_path
        self.cache_name = cache_name
        self.indexes = {}
        self.setup_client()

    def setup_client(self):
        gspread = lazy_init('gspread')
        self.gc = gspread.service_account(filename=self.auth)
        if self.url:
            self.sheet = self.gc.open_by_url(self.url)
            logger.info(f'Loaded GSheetsDB from URL: {self.url}')
        else:
            try:
                self.sheet = self.gc.open(self.cache_name)
                logger.info(f'Loaded GSheetsDB from Name: {self.cache_name}')
            
            except Exception as e:
                self.sheet = None
                logger.error(f'Failed to Load GSheetsDB from Name: {self.cache_name}')
        
        if not self.sheet:
            self.sheet = self.gc.create(self.cache_name)
            logger.info(f'Created GSheetsDB by Name: {self.cache_name}')
            self.url = self.sheet.url
        self.refresh_index()
    
    def create_indexes(self, dbdata):
        for n, i in enumerate(dbdata):
            if i not in self.all_wks:
                idx = dbdata[i]
                wks = self.sheet.add_worksheet(i, index=n)
                # Create row 0 - header
                wks.append_row(idx.schema_props)

    def dump_indexes(self, dbdata):
        for schema, idx in dbdata.items():
            wks = self.sheet.worksheet(schema)
            items = []
            for i in idx.index.values():
                d = i.dict()
                items.append(list(d.values()))
            wks.insert_rows(items, row=2)
        self.refresh_index()

    def refresh_index(self):
        self.index = self.all_wks_dict
    
    def get_header(self, wks):
        return wks.row_values(1)

    @property
    def all_wks(self):
        return list(self.sheet.worksheets())
    
    @property
    def all_wks_dict(self):
        return {n: s for n,s in enumerate(self.all_wks)}
    
    @property
    def cache_file(self):
        return None

    @property
    def cache_filepath(self):
        return None
    
    @property
    def exists(self):
        return bool(self.url)
    
    # Need to figure out how to reconstruct the data
    def dumps(self, data, *args, **kwargs):
        pass
    
    def loads(self, *args, **kwargs):
        pass

    def restore(self, *args, **kwargs):
        pass
    
    def save(self, db, *args, **kwargs):
        pass

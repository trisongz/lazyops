from __future__ import annotations

import os
import abc
from lazyops.libs.pooler import ThreadPooler
from typing import Optional, List, Dict, Any, Union, Type, Tuple, Generator, TYPE_CHECKING
from lazyops.imports._gspread import resolve_gspread
resolve_gspread(required = True)

import gspread


class WorksheetContext(abc.ABC):
    """
    The Current Worksheet Context
    """
    def __init__(
        self,
        gc: 'gspread.Client',
        url: str,
    ):
        """
        Initializes the Worksheet Context
        """
        self.gc = gc
        self.url = url
        self.sheet = self.gc.open_by_url(self.url)
        self.name = self.sheet.title
        self.sheet_name: self.sheet_name = self.sheet.sheet1.title
        self.wks = self.sheet.worksheet(self.sheet_name)
        self.header_index: Dict[str, Dict[str, str]] = {
            self.sheet_name: self.wks.row_values(1)
        }
        # self.headers = self.wks.row_values(1)
        self._worksheet_names: Optional[List[str]] = None

    @property
    def worksheet_names(self) -> List[str]:
        """
        Return the list of worksheet names
        """
        if self._worksheet_names is None:
            self._worksheet_names = [sheet.title for sheet in self.sheet.worksheets(False)]
        return self._worksheet_names
    
    @property
    def headers(self):
        """
        Returns the current sheet headers
        """
        return self.header_index[self.sheet_name]
    
    def duplicate_worksheet(self, name: str, src_name: Optional[str] = None) -> 'gspread.worksheet.Worksheet':
        """
        Duplicate the current worksheet
        """
        src_name = src_name or self.sheet_name
        wks = self.sheet.worksheet(src_name)
        self._worksheet_names = None
        return wks.duplicate(new_sheet_name = name)
        # self.header_index[name] = new_wks.row_values(1)
        # return new_wks
    
    async def aduplicate_worksheet(self, name: str, src_name: Optional[str] = None) -> 'gspread.worksheet.Worksheet':
        """
        Duplicate a worksheet
        -> _template -> name
        """
        src_name = src_name or self.sheet_name
        wks = self.sheet.worksheet(src_name)
        self._worksheet_names = None
        return await ThreadPooler.run_async(wks.duplicate, new_sheet_name = name)
        # self.header_index[name] = new_wks.row_values(1)
        # return new_wks

    def get_worksheet(self, key: Optional[Union[str, int]] = None) -> 'gspread.worksheet.Worksheet':
        """
        Returns a sheet by name or index
        """
        if key is None: key = self.sheet_name
        if key == self.sheet_name: return self.wks
        if isinstance(key, int):
            return self.sheet.worksheet(self.worksheet_names[key])
            # sn = self.worksheet_names[key]
            # wks = self.sheet.worksheet(self.worksheet_names[key])
            # if sn not in self.header_index:
            #     self.header_index[sn] = wks.row_values(1)
            # return wks
        if isinstance(key, str) and key not in self.worksheet_names:
            return self.duplicate_worksheet(key)
        return self.sheet.worksheet(key)
        # if key not in self.header_index:
        #     self.header_index[key] = wks.row_values(1)
        # return wks

    async def aget_worksheet(self, key: Union[str, int]) -> 'gspread.worksheet.Worksheet':
        """
        Returns a sheet by name or index
        """
        if key is None: key = self.sheet_name
        if key == self.sheet_name: return self.wks
        if isinstance(key, int):
            return await ThreadPooler.run_async(self.sheet.worksheet, self.worksheet_names[key])
            # sn = self.worksheet_names[key]
            # wks = await ThreadPooler.run_async(self.sheet.worksheet, self.worksheet_names[key])
            # if sn not in self.header_index:
            #     self.header_index[sn] = wks.row_values(1)
            # return wks
        if isinstance(key, str) and key not in self.worksheet_names:
            return await self.aduplicate_worksheet(key)
        return await ThreadPooler.run_async(self.sheet.worksheet, key)
        # wks = await ThreadPooler.run_async(self.sheet.worksheet, key)
        # if key not in self.header_index:
        #     self.header_index[key] = wks.row_values(1)
        # return wks

    def append_row(self, data: List[Any], sheet_name: Optional[str] = None) -> None:
        """
        Append a row into the worksheet
        """
        if isinstance(data, dict): data = list(data.values())
        wks = self.get_worksheet(sheet_name)
        wks.append_row(data)

    async def aappend_row(
        self, 
        data: Union[Dict[str, Any], List[Any]],
        sheet_name: Optional[str] = None,
        **kwargs
    ):
        """
        Append a row into the worksheet
        """
        if isinstance(data, dict): data = list(data.values())
        # wks = self[sheet_name]
        wks = await self.aget_worksheet(sheet_name)
        await ThreadPooler.run_async(wks.append_row, data)

    def append_rows(self, data: List[List[Any]], sheet_name: Optional[str] = None) -> None:
        """
        Append rows into the worksheet
        """
        if not isinstance(data, list) or not isinstance(data[0], (list, dict)):
            return self.append_row(data, sheet_name = sheet_name)
        data = [list(d.values()) if isinstance(d, dict) else d for d in data]
        wks = self.get_worksheet(sheet_name)
        wks.append_rows(data)
    
    async def aappend_rows(
        self, 
        data: Union[List[Dict[str, Any]], List[List[Any]]],
        sheet_name: Optional[str] = None,
        **kwargs
    ):
        """
        Append rows into the worksheet
        """
        if not isinstance(data, list) or not isinstance(data[0], (list, dict)):
            return await self.aappend_row(data, sheet_name = sheet_name)
        data = [list(d.values()) if isinstance(d, dict) else d for d in data]
        wks = await self.aget_worksheet(sheet_name)
        await ThreadPooler.run_async(wks.append_rows, data)

    
    def insert_row(
        self,
        data: Union[Dict[str, Any], List[Any]],
        index: int= 1,
        value_input_option: str = 'raw',
        inherit_from_before: bool = True,
        sheet_name: Optional[str] = None,
    ):
        """
        Insert a row into the worksheet
        """
        if isinstance(data, dict): data = list(data.values())
        wks = self.get_worksheet(sheet_name)
        wks.insert_row(data, index = index, value_input_option = value_input_option, inherit_from_before = inherit_from_before)

    async def ainsert_row(
        self,
        data: Union[Dict[str, Any], List[Any]],
        index: int= 1,
        value_input_option: str = 'raw',
        inherit_from_before: bool = True,
        sheet_name: Optional[str] = None,
    ):
        """
        Insert a row into the worksheet
        """
        if isinstance(data, dict): data = list(data.values())
        wks = await self.aget_worksheet(sheet_name)
        await ThreadPooler.run_async(wks.insert_row, data, index = index, value_input_option = value_input_option, inherit_from_before = inherit_from_before)

    def insert_rows(
        self,
        data: Union[List[Dict[str, Any]], List[List[Any]]],
        index: int= 1,
        value_input_option: str = 'raw',
        inherit_from_before: bool = True,
        sheet_name: Optional[str] = None,
    ):
        """
        Insert rows into the worksheet
        """
        if not isinstance(data, list) or not isinstance(data[0], (list, dict)):
            return self.insert_row(data, index = index, value_input_option = value_input_option, inherit_from_before = inherit_from_before, sheet_name = sheet_name)
        data = [list(d.values()) if isinstance(d, dict) else d for d in data]
        wks = self.get_worksheet(sheet_name)
        wks.insert_rows(data, index = index, value_input_option = value_input_option, inherit_from_before = inherit_from_before)
    
    async def ainsert_rows(
        self,
        data: Union[List[Dict[str, Any]], List[List[Any]]],
        index: int= 1,
        value_input_option: str = 'raw',
        inherit_from_before: bool = True,
        sheet_name: Optional[str] = None,
    ):
        """
        Insert rows into the worksheet
        """
        if not isinstance(data, list) or not isinstance(data[0], (list, dict)):
            return await self.ainsert_row(data, index = index, value_input_option = value_input_option, inherit_from_before = inherit_from_before, sheet_name = sheet_name)
        data = [list(d.values()) if isinstance(d, dict) else d for d in data]
        wks = await self.aget_worksheet(sheet_name)
        await ThreadPooler.run_async(wks.insert_rows, data, index = index, value_input_option = value_input_option, inherit_from_before = inherit_from_before)

    def get_row(self, index: int, sheet_name: Optional[str] = None, raw_values: Optional[bool] = False) -> Union[List[Any], Dict[str, Any]]:
        """
        Get a row from the worksheet
        """
        wks = self.get_worksheet(sheet_name)
        values = wks.row_values(index)
        if raw_values: return values
        if wks.title not in self.header_index:
            self.header_index[wks.title] = wks.row_values(1)
        return dict(zip(self.header_index[wks.title], values))
    
    async def aget_row(self, index: int, sheet_name: Optional[str] = None, raw_values: Optional[bool] = False) -> Union[List[Any], Dict[str, Any]]:
        """
        Get a row from the worksheet
        """
        wks = await self.aget_worksheet(sheet_name)
        values = await ThreadPooler.run_async(wks.row_values, index)
        if raw_values: return values
        if wks.title not in self.header_index:
            self.header_index[wks.title] = wks.row_values(1)
        return dict(zip(self.header_index[wks.title], values))
    
    def update_row(self, data: Union[Dict[str, Any], List[Any]], index: Optional[int] = None, sheet_name: Optional[str] = None) -> None:
        """
        Update a row in the worksheet
        """
        if isinstance(data, dict): 
            if index is None and 'idx' in data: index = data.pop('idx')
            data = list(data.values())
        assert index is not None, 'Index must be provided'
        wks = self.get_worksheet(sheet_name)
        wks.update(range_name=f'A{index}', values = [data])

    async def aupdate_row(
        self, 
        data: Union[Dict[str, Any], List[Any]],
        index: Optional[int] = None,
        sheet_name: Optional[str] = None,
        **kwargs
    ):
        """
        Update a row in the worksheet
        """
        if isinstance(data, dict): 
            if index is None and 'idx' in data: index = data.pop('idx')
            data = list(data.values())
        assert index is not None, 'Index must be provided'
        wks = await self.aget_worksheet(sheet_name)
        await ThreadPooler.run_async(wks.update, range_name=f'{index}:{index}', values = data)

    def resize_height(self, height: int, wks: Optional[gspread.worksheet.Worksheet] = None) -> None:
        """
        Resize the height of the worksheet
        """
        if not wks: wks = self.wks
        sheet_id = wks._properties['sheetId']
        body = {
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id, "dimension": "ROWS",
                            "startIndex": 0, "endIndex": wks.row_count
                        },
                        "properties": {"pixelSize": height}, "fields": "pixelSize"
                    }
                }
            ]
        }
        wks.batch_update(body)
    
    async def aresize_height(
        self, 
        height: int = 22,
        wks: Optional['gspread.worksheet.Worksheet'] = None,
    ):
        """
        Resize the height of the worksheet
        """
        # https://stackoverflow.com/questions/57177998/gspread-column-sizing
        if not wks: wks = self.wks
        sheet_id = wks._properties['sheetId']
        body = {
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id, "dimension": "ROWS",
                            "startIndex": 0, "endIndex": wks.row_count
                        },
                        "properties": {"pixelSize": height}, "fields": "pixelSize"
                    }
                }
            ]
        }
        return await ThreadPooler.run_async(wks.batch_update, body)

    def get_items(self, sheet_name: Optional[str] = None, include_idx: Optional[bool] = True) -> Dict[int, Any]:
        """
        Gets all the items in the worksheet
        """
        wks = self.get_worksheet(sheet_name)
        headers = wks.row_values(1)
        results = {}
        for n, row in enumerate(wks.get()):
            if n == 0: continue
            if len(row) != len(headers):  row.extend([None] * (len(headers) - len(row)))
            data = dict(zip(headers, row))
            if include_idx: data['idx'] = n + 1
            results[n + 1] = data
        return results
    
    def items(self, sheet_name: Optional[str] = None, include_idx: Optional[bool] = True) -> Generator[Tuple[int, Dict[str, Any]], None, None]:
        """
        Returns a tuple of (idx, item)
        """
        wks = self.get_worksheet(sheet_name)
        if wks.title not in self.header_index:
            self.header_index[wks.title] = wks.row_values(1)
        headers = self.header_index[wks.title]
        for n, row in enumerate(wks.get(major_dimension='ROWS')):
            if n == 0: continue
            if len(row) != len(headers):  row.extend([None] * (len(headers) - len(row)))
            data = dict(zip(headers, row))
            if include_idx: data['idx'] = n + 1
            yield n + 1, data
        
    def __setitem__(self, index: int, value: Union[Dict[str, Any], List[Any]]):
        """
        Set an item in the worksheet
        """
        self.update_row(value, index = index)

    def __getitem__(self, index: int) -> Union[Dict[str, Any], List[Any]]:
        """
        Get an item from the worksheet
        """
        return self.get_row(index)
    
    def __len__(self) -> int:
        """
        Get the length of the worksheet
        """
        return self.wks.row_count


class WorksheetManager(abc.ABC):
    """
    The Worksheet Manager
    """
    def __init__(
        self,
        adc: Optional[str] = None,
        url: Optional[str] = None,
        **kwargs,
    ):
        """
        The Worksheet Manager
        """
        self.adc = adc or os.getenv('GSPREAD_ADC', os.getenv('GOOGLE_APPLICATION_CREDENTIALS', None))
        self._gc: Optional[gspread.Client] = None
        self.default_url: Optional[str] = url
        self.url_to_ctx: Dict[str, str] = {} 
        self.ctxs: Dict[str, WorksheetContext] = {}
        self._ctx: Optional[WorksheetContext] = None
    
    @property
    def gc(self) -> gspread.Client:
        """
        Returns the gspread client
        """
        if self._gc is None:
            if self.adc: 
                self._gc = gspread.service_account(filename = self.adc)
            else: self._gc = gspread.oauth()
            self._gc.http_client.set_timeout(timeout = 60 * 60)
        return self._gc
    

    @property
    def ctx(self) -> WorksheetContext:
        """
        The default context
        """
        if self._ctx is None:
            self.init_ctx()
        return self._ctx

    def init_ctx(
        self, 
        name: Optional[str] = None,
        url: Optional[str] = None,
        set_as_default: Optional[bool] = False,
    ):
        """
        Initializes the context
        """
        name = name or "default"
        if name not in self.ctxs:
            url = url or self.default_url
            assert url, 'No URL provided'
            self.ctxs[name] = WorksheetContext(self.gc, url)
            self.url_to_ctx[url] = name
        if self._ctx is None or set_as_default: self._ctx = self.ctxs[name]
    
    def get_ctx(
        self, 
        name: Optional[str] = None,
        url: Optional[str] = None,
        set_as_default: Optional[bool] = False,
        **kwargs
    ) -> WorksheetContext:
        """
        Returns a context
        """
        if name is None or name == "default": return self.ctx
        self.init_ctx(name = name, url = url, set_as_default = set_as_default, **kwargs)
        return self.ctxs[name]
    

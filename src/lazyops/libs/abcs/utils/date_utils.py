from __future__ import annotations

"""
Parse Date Utils
"""

import datetime
import contextlib
from dateutil import parser as datetimeparser
from dateutil.tz import gettz
from lazyops.libs import lazyload
from typing import Optional, List, Union, Dict
from .hashing import create_hash_from_kwargs

if lazyload.TYPE_CHECKING:
    import pytz
    import dateparser
    from dateparser.date import DateDataParser
else:
    dateparser = lazyload.LazyLoad("dateparser")
    pytz = lazyload.LazyLoad("pytz")

"""
General Datetime Utils
"""

tz_map = {
    'PST': 'US/Pacific', 
    'EST': 'US/Eastern',
    'EDT': 'US/Eastern',
    'CST': 'US/Central',
    'CDT': 'US/Central',
    'MST': 'US/Mountain',
    'MDT': 'US/Mountain',
    'PDT': 'US/Pacific',
    'AKST': 'US/Alaska',
    'AKDT': 'US/Alaska',
    'HST': 'US/Hawaii',
    'HAST': 'US/Hawaii',
    'HADT': 'US/Hawaii',
    'SST': 'US/Samoa',
    'SDT': 'US/Samoa',
    'CHST': 'Pacific/Guam',
    'CHDT': 'Pacific/Guam',
    'UTC': 'UTC',
}
tz_map_reversed = {v: k for k, v in tz_map.items()}
dtz_map = {k: gettz(v) for k, v in tz_map.items()}

def _parse_date(dt: Optional[str] = None) -> Optional[datetime.datetime]:
    # Need to parse to datetime
    # "2023-05-26T10:00:00+09:00"
    # "2023-04-17 21:57:14.756-04"
    # '2023-06-10'
    # 2022-12-05T00:00:00
    # Sep 18, 2014 09:01:09 AM EDT
    # - 2023-08-25T13:00:00-04:00
    # - 2023-07-24 16:10:35.723-04
    # - 2023-08-07T16:00:00-06:00


    # 2019-01-14T15:00:00-05:00
    if not dt: return None
    dt = dt.strip()
    if not dt: return None
    # print(f'WARNING: Could not parse date: {dt}')
    if dt[:2].isalpha():
        # Remove the timezone
        _tz = None
        if dt[-2:] not in {'AM', 'PM'}:
            dt, _tz = dt.rsplit(' ', 1)
            _tz = tz_map.get(_tz)
            if _tz: _tz = pytz.timezone(_tz)
        dt_val = datetime.datetime.strptime(dt, "%b %d, %Y %H:%M:%S %p")
        if _tz: dt_val = _tz.localize(dt_val).astimezone(pytz.utc)
        return dt_val

    if 'T' in dt:
        if '+' in dt:
            return datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S%z")
        if '-' in dt[-7:]:
            # 2019-01-14T15:00:00-05:00 -> 2019-01-14T15:00:00
            dt = dt.rsplit('-', 1)[0]
            
        return datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
    if ' ' in dt and '.' in dt:
        # "posted_date": "2023-04-17 21:57:14.756-04" -> "2023-04-17 21:57:14"
        dt = dt.split('.')[0]
        return datetime.datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    
    if '-' in dt:
        return datetime.datetime.strptime(dt, "%Y-%m-%d")
    
    if '/' in dt:
        return datetime.datetime.strptime(dt, "%m/%d/%Y")
    # 20230418
    return datetime.datetime.strptime(dt, '%m%d%Y')


def __parse_date(dt: Optional[str] = None) -> Optional[datetime.datetime]:
    """
    Wrapper around dateparser.parse to handle some edge cases
    """
    if isinstance(dt, datetime.datetime): return dt
    try:
        return _parse_date(dt)
    except Exception as e:
        # print(f'WARNING: Could not parse date: {dt}')
        return dateparser.parse(dt)


def parse_datetime(dt: Optional[Union[str, List[str]]] = None, timeaware: bool = True) -> Optional[Union[datetime.datetime, List[datetime.datetime]]]:
    # Need to parse to datetime
    # "response_deadline": "2023-05-26T10:00:00+09:00"
    # "posted_date": "2023-04-17 21:57:14.756-04"
    # "archive_date": '2023-06-10'
    if not dt: return None
    if isinstance(dt, datetime.datetime):
        return dt.replace(tzinfo=datetime.timezone.utc) if timeaware \
            else dt
    if isinstance(dt, list): 
        dts = [__parse_date(d) for d in dt]
        if timeaware:
            return [d.replace(tzinfo=datetime.timezone.utc) for d in dts]
        return dts

    dt = __parse_date(dt)
    if not dt: return None
    return dt.replace(tzinfo=datetime.timezone.utc) if timeaware \
        else dt


_dtparsers: Dict[str, 'DateDataParser'] = {}
_dtformats: List[str] = [
    '%Y-%m-%d %H:%M:%S.%f%z',
    '%Y-%m-%d %H:%M:%S%z',
]

def get_dtparser(
    timezone: Optional[str] = 'UTC',
    timeaware: bool = True,
    prefer: str = 'past',
) -> 'DateDataParser':
    """
    Gets the dateparser
    """
    global _dtparsers
    _hash = create_hash_from_kwargs(timezone = timezone, timeaware = timeaware, prefer = prefer)
    if _hash not in _dtparsers:
        _dtparsers[_hash] = dateparser.DateDataParser(
            languages=None,
            locales=None,
            region=None,
            settings = {
                'PREFER_DATES_FROM': prefer, 
                'TIMEZONE': timezone, 
                'RETURN_AS_TIMEZONE_AWARE': timeaware
            },
            detect_languages_function=None,
        )
    return _dtparsers[_hash]

def add_dt_formats(formats: List[str]):
    """
    Adds the date formats
    """
    global _dtformats
    _dtformats.extend(formats)
    _dtformats = list(set(_dtformats))

def extract_datetime(
    dt: Optional[Union[str, List[str]]] = None, 
    timezone: Optional[str] = 'UTC',
    timeaware: bool = True,
    prefer: str = 'past',
) -> Optional[Union[datetime.datetime, List[datetime.datetime]]]:
    """
    Extracts the datetime from the input

    - If `dt` is a string, it will be parsed as a datetime
    - If `dt` is a list, it will be parsed as a list of datetimes
    - If `dt` is None, None will be returned

    Args:
        dt (Optional[Union[str, List[str]]]): The input to extract the datetime from
        timezone (Optional[str], optional): The timezone to use. Defaults to 'UTC'.
        timeaware (bool, optional): Whether to return a timezone aware datetime. Defaults to True.
        prefer (str, optional): The prefer method to use. Defaults to 'past'.

    Returns:
        Optional[Union[datetime.datetime, List[datetime.datetime]]]: The extracted datetime
    """
    if not dt: return None
    if isinstance(dt, datetime.datetime): return dt
    if isinstance(dt, list):
        return [extract_datetime(d, timezone, timeaware, prefer) for d in dt]
    
    if timezone and timezone not in tz_map:
        if timezone not in tz_map_reversed:
            raise ValueError(f'Invalid timezone: {timezone}')
        timezone = tz_map_reversed[timezone]
    
    # Try using native datetimeparser
    with contextlib.suppress(Exception):
        dv = datetimeparser.parse(dt, tzinfos = dtz_map)
        if timeaware: 
            dtz = pytz.timezone(tz_map[timezone]) if timezone != 'UTC' else pytz.utc
            dv = dv.astimezone(dtz)
        return dv

    dp = get_dtparser(timezone = timezone, timeaware = timeaware, prefer = prefer)
    try:
        result =  dp.get_date_data(dt, _dtformats)
        return result['date_obj'] if result else None
    except Exception as e:
        from lazyops.utils.logs import logger
        logger.error(f'[{type(dt).__name__}] Error Extracting Date: {e}')
        raise e
        # return None

def parse_datetime_from_timestamp(
    timestamp: Optional[int],
) -> Optional[datetime.datetime]:
    """
    Parses the timestamp into a datetime

    Format: 1666699200000 -> 2022-12-24T00:00:00.000Z
    """
    if timestamp is None: return None
    return datetime.datetime.fromtimestamp(timestamp / 1000, tz = datetime.timezone.utc)


def get_est_datetime() -> datetime.datetime:
    """
    Gets the current EST datetime
    """
    return datetime.datetime.now(pytz.timezone('US/Eastern'))

def is_expired_datetime(dt: datetime.datetime, delta_days: Optional[int] = None, now: Optional[datetime.datetime] = None) -> bool:
    """
    Checks if the datetime is expired
    """
    if not now: now = get_est_datetime()
    if not delta_days: return now > dt
    dt = dt + datetime.timedelta(days = delta_days)
    return now > dt
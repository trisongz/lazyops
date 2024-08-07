from __future__ import annotations


import datetime
from lazyops.imports._dateparser import (
    dateparser, pytz, resolve_dateparser
)
from typing import Optional, List, Union

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
    
}

def convert_possible_date(
    dt: Optional[str] = None
) -> Optional[datetime.datetime]:
    """
    Converts a possible date string into a datetime
    """
    # Handles various date formats

    if not dt: return None
    dt = dt.strip()
    if not dt: return None
    
    resolve_dateparser(True)
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

def convert_date(
    dt: Optional[str] = None
) -> Optional[datetime.datetime]:
    """
    Wrapper around dateparser.parse to handle some edge cases
    """
    if isinstance(dt, datetime.datetime): return dt
    
    try:
        return convert_possible_date(dt)
    except Exception as e:
        return dateparser.parse(dt)


def parse_datetime(
    dt: Optional[Union[str, List[str]]] = None, 
    timeaware: bool = True,
    tz: Optional[str] = None,
) -> Optional[Union[datetime.datetime, List[datetime.datetime]]]:
    """
    Parses the datetime string into a datetime
    """
    if not dt: return None
    resolve_dateparser(True)
    tz_info = None
    if tz:  tz_info = pytz.timezone(tz_map.get(tz.upper(), tz))
    elif timeaware: tz_info = datetime.timezone.utc

    if isinstance(dt, datetime.datetime):
        return dt.replace(tzinfo=tz_info) if tz_info \
            else dt

    if isinstance(dt, list): 
        dts = [convert_date(d) for d in dt]
        return [d.replace(tzinfo=tz_info) for d in dts] if tz_info else dts
    dt = convert_date(dt)
    if not dt: return None
    return dt.replace(tzinfo=tz_info) if tz_info \
        else dt
    

def parse_datetime_from_timestamp(
    timestamp: Optional[int],
) -> Optional[datetime.datetime]:
    """
    Parses the timestamp into a datetime

    Format: 1666699200000 -> 2022-12-24T00:00:00.000Z
    """
    if timestamp is None: return None
    return datetime.datetime.fromtimestamp(timestamp / 1000, tz = datetime.timezone.utc)


def get_current_datetime(
    tz: Optional[str] = None,
) -> datetime.datetime:
    """
    Gets the current datetime in the specified timezone
    """
    resolve_dateparser(True)
    if tz: tz = pytz.timezone(tz_map.get(tz.upper(), tz))
    return datetime.datetime.now(tz)


def is_expired_datetime(
    dt: datetime.datetime, 
    delta_days: Optional[int] = None, 
    now: Optional[datetime.datetime] = None,
    tz: Optional[str] = None,
) -> bool:
    """
    Checks if the datetime is expired
    """
    if not now: now = get_current_datetime(tz = tz)
    if not delta_days: return now > dt
    dt = dt + datetime.timedelta(days = delta_days)
    return now > dt
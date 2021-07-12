import time
import dateparser

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, List, Optional, Union, Callable

@dataclass
class LazyData:
    string: str = None
    value: Any = None
    dtype: str = None



TimeValues = {
    'secs': 60,
    'mins': 60,
    'hrs': 60,
    'days': 24,
    'wks': 7,
    'mnths': 4
}

class TimeItem:
    secs: float

    @property
    def mins(self):
        return self.secs / 60
    
    @property
    def hrs(self):
        return self.mins / 60
    
    @property
    def days(self):
        return self.hrs / 24
    
    @property
    def wks(self):
        return self.days / 7
    
    @property
    def mnths(self):
        return self.wks / 4
    
    @property
    def ablstime(self):
        curr_val = self.secs
        dict_val, str_val = {}, ''
        for tkey, tnum in TimeValues.items():
            if curr_val >= 1:
                tval = tkey[0] if self.short else tkey
                curr_val, curr_num = divmod(curr_val, tnum)
                if type(curr_num) == float:
                    str_val = f'{curr_num:.1f} {tval} ' + str_val
                else:
                    str_val = f'{curr_num} {tval} ' + str_val
                dict_val[tkey] = curr_num
        str_val = str_val.strip()
        return LazyData(string=str_val, value=dict_val, dtype='time')



class LazyTime:
    def __init__(self, t=None, short=False, *args, **kwargs):
        self.t = time.time() if not t else t
        self.short = short
        self._now = None

    @property
    def now(self):
        if self._now:
            return self._now
        return time.time()

    def stop(self):
        self._now = time.time()

    @property
    def diff(self):
        return self.now - self.t

    @property
    def secs(self):
        return self.diff

    @property
    def mins(self):
        return self.secs / 60
    
    @property
    def hrs(self):
        return self.mins / 60
    
    @property
    def days(self):
        return self.hrs / 24
    
    @property
    def wks(self):
        return self.days / 7
    
    @property
    def mnths(self):
        return self.wks / 4
    
    @property
    def ablstime(self):
        curr_val = self.secs
        dict_val, str_val = {}, ''
        for tkey, tnum in TimeValues.items():
            if curr_val >= 1:
                tval = tkey[0] if self.short else tkey
                curr_val, curr_num = divmod(curr_val, tnum)
                if type(curr_num) == float:
                    str_val = f'{curr_num:.1f} {tval} ' + str_val
                else:
                    str_val = f'{curr_num} {tval} ' + str_val
                dict_val[tkey] = curr_num
        str_val = str_val.strip()
        return LazyData(string=str_val, value=dict_val, dtype='time')
        
    @property
    def s(self):
        return self.secs
    
    @property
    def seconds(self):
        return self.secs

    @property
    def m(self):
        return self.mins
    
    @property
    def minutes(self):
        return self.mins
    
    @property
    def h(self):
        return self.hrs
    
    @property
    def hr(self):
        return self.hrs
    
    @property
    def hour(self):
        return self.hrs
    
    @property
    def hours(self):
        return self.hrs

    @property
    def d(self):
        return self.days
    
    @property
    def day(self):
        return self.days
    
    @property
    def w(self):
        return self.wks
    
    @property
    def wk(self):
        return self.wks
    
    @property
    def week(self):
        return self.wks

    @property
    def weeks(self):
        return self.wks
    
    @property
    def month(self):
        return self.mnths
    
    @property
    def mons(self):
        return self.mnths
    
    @property
    def months(self):
        return self.mnths



class LazyDate:
    @classmethod
    def dtime(cls, dt: str = None, prefer: str = 'past'):
        if not dt:
            return datetime.now(timezone.utc).isoformat('T')
        pdt = dateparser.parse(dt, settings={'PREFER_DATES_FROM': prefer, 'TIMEZONE': 'UTC', 'RETURN_AS_TIMEZONE_AWARE': True})
        if prefer == 'past': 
            r = (datetime.now(timezone.utc) - pdt)
        else:
            r = (pdt - datetime.now(timezone.utc))
        return TimeItem(r.total_seconds())

    @classmethod
    def date(cls, dt: str = None, prefer: str = 'past'):
        if not dt:
            return datetime.now(timezone.utc)
        return dateparser.parse(dt, settings={'PREFER_DATES_FROM': prefer, 'TIMEZONE': 'UTC', 'RETURN_AS_TIMEZONE_AWARE': True})    

    @classmethod
    def fmt(cls, secs, **kwargs):
        return TimeItem(secs)
    
    @property
    def now(self):
        return self.dtime()

    def __call__(self, **kwargs):
        return self.dtime(**kwargs)

class LazyFormatter:
    def size(cls, bvalue, suffix="B"):
        factor = 1024
        for unit in ["", "K", "M", "G", "T", "P"]:
            if bvalue < factor:
                return LazyData(string=f"{bvalue:.2f} {unit}{suffix}", value=bvalue, dtype="size")
            bvalue /= factor

    def ftime(cls, t: time.time = None, short: bool = True):
        return LazyTime(t, short=short)
    
    def dtime(cls, dt: str = None, prefer: str = 'past'):
        return LazyDate.dtime(dt, prefer)


class LazyTimer:
    timers = {}
    def stop_timer(self, name):
        assert name in LazyTimer.timers
        LazyTimer.timers[name].stop()
        return LazyTimer.timers[name]

    def __getitem__(self, name, t = None, *args, **kwargs):
        return LazyTimer.timers.get(name, None)

    def __call__(self, name, t = None, *args, **kwargs):
        if name not in LazyTimer.timers:
            LazyTimer.timers[name] = LazyTime(t=t, *args, **kwargs)
        return LazyTimer.timers[name]



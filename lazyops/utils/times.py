from __future__ import annotations

"""
Timing Utils
"""

import abc
import time
from .logs import logger, null_logger
from typing import Optional, List, Dict, Any, Union


class Timer(abc.ABC, dict):
    start: Optional[float] = None

    def __init__(
        self,
        start: Optional[float] = None,
        
        auto_checkpoint: Optional[bool] = True,
        format_ms: Optional[bool] = False,
        format_pretty: Optional[bool] = True,
        format_short: Optional[int] = 0,
        verbose: bool = None,
    ):
        """
        Timer class for timing code

        Args:
            start (Optional[float], optional):
                The starting time of the timer. Defaults to None.
            auto_checkpoint (Optional[bool], optional):
                Whether to automatically add a checkpoint when accessing the duration.
                Defaults to True.
            format_ms (Optional[bool], optional):
                Whether to include milliseconds in the string representation of the duration.
                Defaults to False.
            format_pretty (Optional[bool], optional):
                Whether to use a pretty format for the string representation of the duration.
                Defaults to True.
            format_short (Optional[int], optional):
                0: Default format (full unit with spaces) 
                    2 days, 18 hours, 49 minutes, 15.01 seconds
                1: Pretty format (shortened unit with spaces)
                    2 days 18 hrs 49 mins 15.01 secs
                2: Short format (1 letter unit, single space)
                    2d 18h 49m 15s
                3: Short format (1 letter unit, no space)
                    2d18h49m15s
                Defaults to 1.

        """
        if not start:
            self.start = time.time()
        else:
            # If we're starting from a duration, we need to subtract the duration
            # from the current time
            curr_ts = time.time()
            if len(str(start)) == len(str(curr_ts)):
                self.start = float(start)
            else:
                self.start = curr_ts - float(start)
        
        self.durations: List[float] = []
        self.auto_checkpoint = auto_checkpoint
        self.verbose = verbose
        self.format_ms = format_ms
        self.format_pretty = format_pretty
        self.format_short = format_short
        # We do this to make the timer compatible with json.dumps
        # and initialize the dict
        # so that it won't be assumed to be empty
        self['_start'] = self.start

    @classmethod
    def dformat_duration(
        cls,
        duration: float,
        pretty: bool = True,
        short: int = 0,
        include_ms: bool = False,
        as_int: bool = False,
    ) -> Dict[str, Union[float, int]]:    # sourcery skip: low-code-quality
        """
        Formats a duration (secs) into a dict
        """
        if not pretty:
            unit = 'secs' if short else 'seconds'
            value = int(duration) if as_int else duration
            return {unit: value}
        data = {}
        if duration >= 86400:
            unit = 'd' if short > 1 else 'day'
            days = (duration // 86400)
            if short < 2 and days > 1: unit += 's'
            duration -= days * 86400
            data[unit] = int(days) if as_int else days
        if duration >= 3600:
            unit = 'hr' if short else 'hour'
            if short > 1: unit = unit[0]
            hours = (duration // 3600)
            if short < 2 and hours > 1: unit += 's'
            duration -= hours * 3600
            data[unit] = int(hours) if as_int else hours
        if duration >= 60:
            unit = 'min' if short else 'minute'
            if short > 1: unit = unit[0]
            minutes = (duration // 60)
            if short < 2 and minutes > 1: unit += 's'
            duration -= minutes * 60
            data[unit] = int(minutes) if as_int else minutes
        if duration >= 1:
            unit = 'sec' if short else 'second'
            if short > 1: unit = unit[0]
            if short < 2 and duration > 1: unit += 's'
            if include_ms:
                seconds = int(duration)
                duration -= seconds
                data[unit] = seconds
            elif short > 1:
                data[unit] = int(duration) if as_int else duration
            else:
                data[unit] = float(f'{duration:.2f}')
        if include_ms and duration > 0:
            unit = 'ms' if short else 'millisecond'
            milliseconds = int(duration * 1000)
            data[unit] = milliseconds
        return data
    
    @classmethod
    def pformat_duration(
        cls,
        duration: float,
        pretty: bool = True,
        short: int = 0,
        include_ms: bool = False,
    ) -> str:  # sourcery skip: low-code-quality
        """
        Formats a duration (secs) into a string

        535003.0 -> 5 days, 5 hours, 50 minutes, 3 seconds
        3593.0 -> 59 minutes, 53 seconds
        """
        data = cls.dformat_duration(
            duration = duration,
            pretty = pretty,
            short = short,
            include_ms = include_ms,
            as_int = True
        )
        if not data: return '0 secs'
        sep = '' if short > 1 else ' '
        if short > 2: return ''.join([f'{v}{sep}{k}' for k, v in data.items()])
        return ' '.join([f'{v}{sep}{k}' for k, v in data.items()]) if short else ', '.join([f'{v}{sep}{k}' for k, v in data.items()])

    def dformat(
        self,
        duration: float,
        pretty: bool = None,
        short: int = None,
        include_ms: bool = None,
        as_int: bool = False,
    ) -> Dict[str, Union[float, int]]:    # sourcery skip: low-code-quality
        """
        Formats a duration (secs) into a dict
        """
        pretty = pretty if pretty is not None else self.format_pretty
        short = short if short is not None else self.format_short
        include_ms = include_ms if include_ms is not None else self.format_ms
        return self.dformat_duration(
            duration,
            pretty = pretty,
            short = short,
            include_ms = include_ms,
            as_int = as_int,
        )

    def pformat(
        self, 
        duration: float,
        pretty: bool = None,
        short: int = None,
        include_ms: bool = None,
    ) -> str:  # sourcery skip: low-code-quality
        """
        Formats a duration (secs) into a string

        535003.0 -> 5 days, 5 hours, 50 minutes, 3 seconds
        3593.0 -> 59 minutes, 53 seconds
        """
        pretty = pretty if pretty is not None else self.format_pretty
        short = short if short is not None else self.format_short
        include_ms = include_ms if include_ms is not None else self.format_ms
        return self.pformat_duration(
            duration,
            pretty = pretty,
            short = short,
            include_ms = include_ms,
        )


    def checkpoint(self):
        """
        Adds a checkpoint to the timer
        """
        duration = time.time() - self.start
        self.durations.append(duration)
        self.start = time.time()

    def get_duration(self, checkpoint: Optional[bool] = None) -> float:
        """
        Returns the latest duration of the timer
        """
        checkpoint = checkpoint if checkpoint is not None else self.auto_checkpoint
        if checkpoint: self.checkpoint()
        return self.durations[-1] if self.durations else self.elapsed
    
    @property
    def duration(self) -> float:
        """
        Returns the latest duration of the timer
        """
        return self.get_duration()
        
    @property
    def duration_s(self) -> str:
        """
        Returns the latest duration of the timer as a string
        """
        # this is designed to prevent additional snapshotting
        # when duration is called and then duration_s is called
        # in logging.
        return self.pformat(self.get_duration(False))

    def duration_average(self, count: int, checkpoint: Optional[bool] = False) -> float:
        """
        Returns the average duration of the timer
        """
        return self.get_duration(checkpoint) / count

    def duration_average_s(self, count: int, checkpoint: Optional[bool] = False) -> str:
        """
        Returns the average duration of the timer as a string
        """
        return self.pformat(self.duration_average(count, checkpoint))

    def duration_average_iter(self, count: int, checkpoint: Optional[bool] = False) -> float:
        """
        Returns the average count/duration of the timer
        """
        return count / self.get_duration(checkpoint)
    
    def duration_average_iter_s(self, count: int, unit: Optional[str] = None, checkpoint: Optional[bool] = False) -> str:
        """
        Returns the average count/duration of the timer as a string
        """
        avg = self.duration_average_iter(count, checkpoint)
        return f'{avg:.2f}/sec' if unit is None else f'{avg:.2f} {unit}/sec'
    

    @property
    def total(self) -> float:
        """
        Returns the total duration of the timer
        """
        return sum(self.durations + [self.elapsed]) \
            if self.durations else self.elapsed
    
    @property
    def total_s(self) -> str:
        """
        Returns the total duration of the timer as a string
        """
        return self.pformat(self.total)
    
    def total_average(self, count: int) -> float:
        """
        Returns the average total duration/count of the timer
        """
        return self.total / count
    
    def total_average_s(self, count: int) -> str:
        """
        Returns the average duration of the timer as a string
        """
        return self.pformat(self.total_average(count or 1))
    
    def total_average_iter(self, count: int) -> float:
        """
        Returns the average count/total duration of the timer
        """
        return count / self.total
    
    def total_average_iter_s(self, count: int, unit: Optional[str] = None) -> str:
        """
        Returns the average count/total duration of the timer as a string
        """
        avg = self.total_average_iter(count)
        return f'{avg:.2f}/sec' if unit is None else f'{avg:.2f} {unit}/sec'

    @property
    def elapsed(self) -> float:
        """
        Returns the elapsed time since the timer was started
        Does not add a checkpoint
        """
        return time.time() - self.start
    
    @property
    def elapsed_s(self) -> str:
        """
        Returns the elapsed time since the timer was started as a string
        Does not add a checkpoint
        """
        return self.pformat(self.elapsed)
    
    def elapsed_average(self, count: int) -> float:
        """
        Returns the average duration of the timer
        """
        return self.elapsed / count
    
    def elapsed_average_s(self, count: int) -> str:
        """
        Returns the average duration of the timer as a string
        """
        return self.pformat(self.elapsed_average(count))

    def elapsed_average_iter(self, count: int) -> float:
        """
        Returns the average count/elapsed duration of the timer
        """
        return count / self.elapsed
    
    def elapsed_average_iter_s(self, count: int, unit: Optional[str] = None) -> str:
        """
        Returns the average count/elapsed duration of the timer as a string
        """
        avg = self.elapsed_average_iter(count)
        return f'{avg:.2f}/sec' if unit is None else f'{avg:.2f} {unit}/sec'


    @property
    def average(self) -> float:
        """
        Returns the average duration of the timer
        """
        if not self.durations: return self.elapsed
        return self.total / (len(self.durations)  + 1)
    
    @property
    def average_s(self) -> str:
        """
        Returns the average duration of the timer as a string
        """
        return self.pformat(self.average)

    @property
    def autologger(self):
        """
        Returns the logger to use
        """
        return logger if self.verbose else null_logger
    
    def __len__(self) -> int:
        """
        Returns the number of checkpoints
        """
        return len(self.durations)
    
    def __float__(self) -> float:
        """
        Returns the total duration of the timer
        """
        return self.total
    
    def __int__(self) -> int:
        """
        Returns the total duration of the timer
        """
        return int(self.total)
    
    def __str__(self) -> str:
        """
        Returns a string representation of the timer
        """
        return self.total_s
    
    def __repr__(self) -> str:
        """
        Returns a string representation of the timer
        """
        return f"Time({self.total_s})"
    
    def __getitem__(self, index: int) -> float:
        """
        Returns the duration at the given index
        """
        return self.durations[index] if self.durations else self.elapsed
    
    def __iadd__(self, other: Union[float, int]) -> 'Timer':
        """
        Adds the other to the values
        """
        self.durations.append(other)
        return self
    
    def __isub__(self, other: Union[float, int]) -> 'Timer':
        """
        Subtracts the other from the values
        """
        self.durations.append(-other)
        return self

    @property
    def data_dict(self) -> Dict[str, Any]:
        """
        Returns a dict representation of the timer
        """
        return {
            'duration': self.duration,
            'total': self.total,
            'elapsed': self.elapsed,
            'average': self.average,
            'data': self.dformat(self.total)
        }

    def dict(self, **kwargs) -> Dict[str, float]:
        """
        Returns a dict representation of the timer
        """
        return {
            'duration': self.duration,
            'total': self.total,
            'elapsed': self.elapsed,
            'average': self.average,
            'data': self.dformat(self.total)
        }
    
    def items(self) -> Dict[str, Union[str, float]]:
        """
        Returns a dict representation of the timer 
        that is compatible with json.dumps
        """
        return [
            ('duration', self.duration),
            ('total', self.total),
            ('elapsed', self.elapsed),
            ('average', self.average),
            ('data', self.dformat(self.total))
        ]

    
    def __eq__(self, other: Union[Timer, float, int]) -> bool:
        """
        Returns whether the timer is equal to the other value
        """
        if isinstance(other, Timer):
            return self.total == other.total
        return self.total == other
    
    def __ne__(self, other: Union[Timer, float, int]) -> bool:
        """
        Returns whether the timer is not equal to the other value
        """
        if isinstance(other, Timer):
            return self.total != other.total
        return self.total != other
    
    def __lt__(self, other: Union[Timer, float, int]) -> bool:
        """
        Returns whether the timer is less than the other value
        """
        if isinstance(other, Timer):
            return self.total < other.total
        return self.total < other
    
    def __le__(self, other: Union[Timer, float, int]) -> bool:
        """
        Returns whether the timer is less than or equal to the other value
        """
        if isinstance(other, Timer):
            return self.total <= other.total
        return self.total <= other
    
    def __gt__(self, other: Union[Timer, float, int]) -> bool:
        """
        Returns whether the timer is greater than the other value
        """
        if isinstance(other, Timer):
            return self.total > other.total
        return self.total > other
    
    def __ge__(self, other: Union[Timer, float, int]) -> bool:
        """
        Returns whether the timer is greater than or equal to the other value
        """
        if isinstance(other, Timer):
            return self.total >= other.total
        return self.total >= other
    
    
    def __add__(self, other: Union[Timer, float, int]) -> float:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            return self.total + other.total
        return self.total + other
    
    def __sub__(self, other: Union[Timer, float, int]) -> float:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            return self.total - other.total
        return self.total - other
    
    def __mul__(self, other: Union[Timer, float, int]) -> float:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            return self.total * other.total
        return self.total * other
    
    def __truediv__(self, other: Union[Timer, float, int]) -> float:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            return self.total / other.total
        return self.total / other
    
    def __floordiv__(self, other: Union[Timer, float, int]) -> float:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            return self.total // other.total
        return self.total // other
    

    """
    Mutations
    """
    
    def __iadd__(self, other: Union[Timer, float, int]) -> Timer:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            self.durations.extend(other.durations)
        else:
            self.durations.append(other)
        return self
    
    def __isub__(self, other: Union[Timer, float, int]) -> Timer:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            self.durations.extend([-d for d in other.durations])
        else:
            self.durations.append(-other)
        return self
    
    def __imul__(self, other: Union[Timer, float, int]) -> Timer:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            self.durations.extend([d * other.total for d in self.durations])
        else:
            self.durations.append(other * self.total)
        return self
    
    def __itruediv__(self, other: Union[Timer, float, int]) -> Timer:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            self.durations.extend([d / other.total for d in self.durations])
        else:
            self.durations.append(self.total / other)
        return self
    
    def __ifloordiv__(self, other: Union[Timer, float, int]) -> Timer:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            self.durations.extend([d // other.total for d in self.durations])
        else:
            self.durations.append(self.total // other)
        return self
    
    def __imod__(self, other: Union[Timer, float, int]) -> Timer:
        """
        Returns the total duration of the timer
        """
        if isinstance(other, Timer):
            self.durations.extend([d % other.total for d in self.durations])
        else:
            self.durations.append(self.total % other)
        return self
    

    def __hash__(self):
        """
        Returns the hash of the timer
        """
        return hash(self.start or self.total)
from __future__ import annotations

"""
Persistent Dict Addons
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Union, Tuple, Dict, Iterator, Any, Type, Set, Iterable, TYPE_CHECKING
from .debug import get_autologger

autologger = get_autologger('addons')

class NumericValuesContainer(BaseModel):
    """
    Container for numeric values
    """
    values: Optional[List[float]] = Field(default_factory=list, description="The Values of the container")

    @property
    def average(self) -> float:
        """
        Returns the average
        """
        return sum(self.values) / len(self.values) if self.values else 0
    
    @property
    def median(self) -> float:
        """
        Returns the median
        """
        return sorted(self.values)[len(self.values) // 2] if self.values else 0
    
    @property
    def count(self) -> int:
        """
        Returns the count
        """
        return len(self.values) if self.values else 0
    
    @property
    def min(self) -> float:
        """
        Returns the min
        """
        return min(self.values) if self.values else 0
    
    @property
    def max(self) -> float:
        """
        Returns the max
        """
        return max(self.values) if self.values else 0
    
    @property
    def total(self) -> float:
        """
        Returns the total
        """
        return sum(self.values) if self.values else 0

    @property
    def p90(self) -> float:
        """
        Returns the p90
        """
        return self.percentile(90)
    
    @property
    def p95(self) -> float:
        """
        Returns the p95
        """
        return self.percentile(95)
    
    def percentile(self, percentile: float) -> float:
        """
        Returns the percentile
        """
        return sorted(self.values)[int(len(self.values) * (percentile / 100))] if self.values else 0

    def __len__(self) -> int:
        """
        Returns the length
        """
        return len(self.values) if self.values else 0

    def __iadd__(self, other: Union[float, int]) -> 'NumericValuesContainer':
        """
        Adds the other to the values
        """
        self.values.append(other)
        return self
    
    def __isub__(self, other: Union[float, int]) -> 'NumericValuesContainer':
        """
        Subtracts the other from the values
        """
        self.values.append(other * -1)
        return self
    
    def __add__(self, other: Union[float, int]) -> float:
        """
        Adds the other to the values
        """
        return self.total + other
    
    def __sub__(self, other: Union[float, int]) -> float:
        """
        Subtracts the other from the values
        """
        return self.total - other
    
    def __mul__(self, other: Union[float, int]) -> float:
        """
        Multiplies the other to the values
        """
        return self.total * other
    
    def __truediv__(self, other: Union[float, int]) -> float:
        """
        Divides the other to the values
        """
        return self.total / other
    
    def __floordiv__(self, other: Union[float, int]) -> float:
        """
        Divides the other to the values
        """
        return int(self.total / other)
    
    def __mod__(self, other: Union[float, int]) -> float:
        """
        Divides the other to the values
        """
        return (self.total % other)
    
    def __divmod__(self, other: Union[float, int]) -> Tuple[float, float]:
        """
        Divides the other to the values
        """
        return divmod(self.total, other)
    
    def pop(self, index: int) -> float:
        """
        Pops the item at the index
        """
        return self.values.pop(index)
    
    def append(self, value: float) -> None:
        """
        Appends the value
        """
        self.values.append(value)

    def extend(self, values: List[float]) -> None:
        """
        Extends the values
        """
        self.values.extend(values)

    def __getitem__(self, index: int) -> float:
        """
        Gets the item at the index
        """
        return self.values[index]
    
    def __setitem__(self, index: int, value: float) -> None:
        """
        Sets the item at the index
        """
        self.values[index] = value

    def __delitem__(self, index: int) -> None:
        """
        Deletes the item at the index
        """
        del self.values[index]

    def __iter__(self) -> Iterator[float]:
        """
        Iterates over the values
        """
        return iter(self.values)
    
    def __contains__(self, value: float) -> bool:
        """
        Checks if the value is in the values
        """
        return value in self.values

    def __reversed__(self) -> Iterator[float]:
        """
        Reverses the values
        """
        return reversed(self.values)
    
    def __bool__(self) -> bool:
        """
        Checks if the values are not empty
        """
        return bool(self.values)
    
    def __eq__(self, other: float) -> bool:
        """
        Checks if the values are equal
        """
        return self.total == other
    
    def __ne__(self, other: float) -> bool:
        """
        Checks if the values are not equal
        """
        return self.total != other
    
    def __lt__(self, other: float) -> bool:
        """
        Checks if the values are less than
        """
        return self.total < other
    
    def __le__(self, other: float) -> bool:
        """
        Checks if the values are less than or equal to
        """
        return self.total <= other
    
    def __gt__(self, other: float) -> bool:
        """
        Checks if the values are greater than
        """
        return self.total > other
    
    def __ge__(self, other: float) -> bool:
        """
        Checks if the values are greater than or equal to
        """
        return self.total >= other
    
    def __hash__(self) -> int:
        """
        Returns the hash of the values
        """
        return hash(self.values)
    
    def __repr__(self) -> str:
        """
        Returns the representation of the values
        """
        return f'<{self.__class__.__name__}>(total={self.total}, average={self.average}, count={self.count})'

    def __str__(self) -> str:
        """
        Returns the string representation of the values
        """
        return f'{self.total}, {self.average}, {self.count}'
    
    @property
    def data_values(self) -> Dict[str, Union[float, int]]:
        """
        Returns the data view
        """
        return {
            'total': self.total,
            'average': self.average,
            'median': self.median,
            'count': self.count,
        }

class MonetaryMetric(NumericValuesContainer):
    """
    A container for monetary values
    """
    name: Optional[str] = 'costs'
    unit: Optional[str] = 'USD'
    symbol: Optional[str] = '$'

    def pretty(self, value: float) -> str:
        """
        Returns the pretty representation of the value
        """
        return f'{self.symbol}{value:.2f}'
    
    @property
    def total_s(self) -> str:
        """
        Returns the total in s
        """
        return self.pretty(self.total)
    
    @property
    def average_s(self) -> str:
        """
        Returns the average in s
        """
        return self.pretty(self.average)
    
    @property
    def median_s(self) -> str:
        """
        Returns the median in s
        """
        return self.pretty(self.median)
    
    def __repr__(self) -> str:
        """
        Returns the representation of the values
        """
        d = {
            self.name: {
                'total': self.total_s,
                'average': self.average_s,
                'median': self.median_s,
                'count': self.count,
            }
        }
        return str(d)
    
    def __str__(self) -> str:
        """
        Returns the string representation of the values
        """
        return f'{self.total_s}, {self.average_s}, {self.count}'



class DurationMetric(NumericValuesContainer):
    """
    A container for duration metrics
    """

    name: Optional[str] = 'duration'


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

    def pretty(
        self,
        short: int = 0,
        include_ms: bool = False,
    ) -> str:
        """
        Returns the pretty representation of the values
        """
        return self.pformat_duration(self.total, short = short, include_ms = include_ms)

    def __repr__(self) -> str:
        """
        Returns the representation of the values
        """
        name = self.name or self.__class__.__name__
        return f'<{name}>(total: {self.pformat_duration(self.total)}, average: {self.average:.2f}/sec)'

    def __str__(self) -> str:
        """
        Returns the string representation of the values
        """
        return f'{self.pformat_duration(self.total)}'
    
    @property
    def total_s(self) -> str:
        """
        Returns the total in seconds
        """
        return self.pformat_duration(self.total, short = 1, include_ms = False)
    
    @property
    def average_s(self) -> str:
        """
        Returns the average in seconds
        """
        return self.pformat_duration(self.average, short = 1, include_ms = False)
    
    @property
    def median_s(self) -> str:
        """
        Returns the median in seconds
        """
        return self.pformat_duration(self.median, short = 1, include_ms = False)


class CountMetric(BaseModel):
    """
    A container for count metrics
    This is a generic metric that can be used to track individual counts of keys

    {
        'website.com': 1,
        'www.website.com': 2,
    }
    """

    name: Optional[str] = 'count'
    data: Dict[str, Union[int, float]] = Field(default_factory = dict, description = 'The count values')

    def incr(self, key: str, value: Union[int, float] = 1) -> None:
        """
        Increments the value for the given key
        """
        if key not in self.data: self.data[key] = value
        else: self.data[key] += value

    def decr(self, key: str, value: Union[int, float] = 1) -> None:
        """
        Decrements the value for the given key
        """
        if key not in self.data: self.data[key] = value
        else: self.data[key] -= value

    def reset(self, key: Optional[str] = None) -> None:
        """
        Resets the values
        """
        if key is not None: self.data[key] = 0
        else: self.data.clear()

    def add(self, key: str) -> None:
        """
        Adds the value to the count
        """
        return self.incr(key)

    def sub(self, key: str) -> None:
        """
        Subtracts the value from the count
        """
        return self.decr(key)
    
    def append(self, key: str) -> None:
        """
        Appends the value to the count
        """
        return self.incr(key, value = 1)
    
    def extend(self, *keys: str) -> None:
        """
        Extends the count
        """
        for key in keys: self.incr(key, value = 1)
    
    def __getitem__(self, key: str) -> Union[int, float]:
        """
        Gets the value for the given key
        """
        return self.data[key]
    
    def __setitem__(self, key: str, value: Union[int, float]) -> None:
        """
        Sets the value for the given key
        """
        self.data[key] = value

    def __delitem__(self, key: str) -> None:
        """
        Deletes the value for the given key
        """
        del self.data[key]

    def __contains__(self, key: str) -> bool:
        """
        Checks if the key is in the values
        """
        # print(f'[{self.name}] Checking if {key} is in {self.data} = {key in self.data}')
        return key in self.data
    
    def __len__(self) -> int:
        """
        Gets the length of the values
        """
        return len(self.data)
    
    def items(self, sort: Optional[bool] = None): #  -> List[Tuple[str, Union[int, float, CountMetric]]]:
        """
        Gets the items of the values
        """
        if sort: return sorted(self.data.items(), key = lambda x: x[1], reverse = True)
        return list(self.data.items())
    
    def keys(self, sort: Optional[bool] = None) -> List[str]:
        """
        Gets the keys of the values
        """
        if sort: return sorted(self.data.keys(), key = lambda x: x, reverse = True)
        return list(self.data.keys())
    
    def values(self, sort: Optional[bool] = None) -> List[Union[int, float]]:
        """
        Gets the values of the values
        """
        if sort: return sorted(self.data.values(), key = lambda x: x, reverse = True)
        return list(self.data.values())
    
    def __iter__(self) -> Iterable[str]:
        """
        Iterates over the values
        """
        return iter(self.data.keys())
    
    def __iadd__(self, key: Union[str, List[str]]) -> 'CountMetric':
        """
        Adds a key to the values
        """
        if not isinstance(key, list): key = [key]
        for k in key:
            self.incr(k)
        return self
    
    def __isub__(self, key: Union[str, List[str]]) -> 'CountMetric':
        """
        Subtracts a key from the values
        """
        if not isinstance(key, list): key = [key]
        for k in key:
            self.decr(k)
        return self

    @property
    def count(self) -> int:
        """
        Gets the count of the values
        """
        return len(self.data)
    
    @property
    def total(self) -> Union[int, float]:
        """
        Gets the total value
        """
        return sum(self.data.values())
    
    @property
    def average(self) -> Union[int, float]:
        """
        Gets the average value
        """
        return self.total / self.count
    
    def top_n(self, n: int, sort: Optional[bool] = None) -> List[Tuple[str, Union[int, float]]]:
        """
        Gets the top n values
        """
        if sort: return sorted(self.data.items(), key = lambda x: x[1], reverse = True)[:n]
        return list(self.data.items())[:n]
    
    def top_n_keys(self, n: int, sort: Optional[bool] = None) -> List[str]:
        """
        Gets the top n keys
        """
        if sort: return sorted(self.data.keys(), key = lambda x: x, reverse = True)[:n]
        return list(self.data.keys())[:n]
    
    def top_n_values(self, n: int, sort: Optional[bool] = None) -> List[Union[int, float]]:
        """
        Gets the top n values
        """
        if sort: return sorted(self.data.values(), key = lambda x: x, reverse = True)[:n]
        return list(self.data.values())[:n]
    
    def top_n_items(self, n: int, sort: Optional[bool] = None) -> Dict[str, Union[int, float]]:
        """
        Gets the top n items
        """
        if sort: return dict(sorted(self.data.items(), key = lambda x: x[1], reverse = True)[:n])
        return dict(list(self.data.items())[:n])
    
    def sum_keys(self, *keys: str) -> int:
        """
        Sums the values of the keys
        """
        keys = [key for key in keys if key]
        return sum(self.data.get(key, 0) for key in keys)
    
    def __repr__(self) -> str:
        """
        Representation of the object
        """
        return f'{dict(self.items())}'

    @property
    def key_list(self) -> List[str]:
        """
        Returns the list of keys
        """
        return list(self.data.keys())


MetricModel = Union[CountMetric, DurationMetric, MonetaryMetric, NumericValuesContainer, BaseModel]


class BaseNestedMetric(BaseModel):
    """
    The base class for nested metrics

    - This is a base class for metrics that contain nested metrics
    """
    name: Optional[str] = None
    data: Dict[str, MetricModel] = Field(default_factory = dict, description = 'The nested metric values')

    @property
    def metric_class(self) -> Type[MetricModel]:
        """
        Returns the metric class
        """
        raise NotImplementedError

    def items(self, sort: Optional[bool] = None):
        """
        Returns the dict_items view of the data
        """
        return {k: dict(v.items(sort = sort)) for k, v in self.data.items()}.items()

    def __getitem__(self, key: str) -> MetricModel:
        """
        Gets the value for the given key
        """
        if key not in self.data: self.data[key] = self.metric_class(name = key)
        return self.data[key]
    
    def __setitem__(self, key: str, value: MetricModel):
        """
        Sets the value for the given key
        """
        self.data[key] = value

    def __getattr__(self, name: str) -> MetricModel:
        """
        Gets the value for the given key
        """
        if name not in self.data: self.data[name] = self.metric_class(name = name)
        return self.data[name]
    
    def __setattr__(self, name: str, value: MetricModel) -> None:
        """
        Sets the value for the given key
        """
        self.data[name] = value
    
    def __repr__(self) -> str:
        """
        Representation of the object
        """
        return f'{dict(self.items())}'
        
    def __str__(self) -> str:
        """
        Representation of the object
        """
        return self.__repr__()

    def __contains__(self, key: str) -> bool:
        """
        Checks if the key is in the data
        """
        return key in self.data
    
    
    
    if TYPE_CHECKING:
        def __getattribute__(self, name: str) -> MetricModel:
            """
            Gets the value for the given key
            """
            ...


class NestedCountMetric(BaseNestedMetric):
    """
    Nested Count Metric Container

    {
        'website.com': {
            '2022-01-01': 1,
            '2022-01-02': 2,
        },
        'www.website.com': {
            '2022-01-01': 3,
            '2022-01-02': 4,
        },
    }
    """

    name: Optional[str] = 'nested_count'
    data: Dict[str, CountMetric] = Field(default_factory = dict, description = 'The nested count values')


    @property
    def metric_class(self) -> Type[CountMetric]:
        """
        Returns the metric class
        """
        return CountMetric

    def items(self, sort: Optional[bool] = None):
        """
        Returns the dict_items view of the data
        """
        return {k: dict(v.items(sort = sort)) for k, v in self.data.items()}.items()

    if TYPE_CHECKING:
        def __getitem__(self, key: str) -> CountMetric:
            """
            Gets the value for the given key
            """
            ...
        def __getattr__(self, name: str) -> CountMetric:
            """
            Gets the value for the given key
            """
            ...


class NestedDurationMetric(BaseNestedMetric):
    """
    Nested Duration Metric Container

    {
        'operation_a': 240.0,
        'operation_b': 120.0,
    }
    """
    name: Optional[str] = 'nested_duration'
    data: Dict[str, DurationMetric] = Field(default_factory = dict, description='The nested duration metric data')

    @property
    def metric_class(self) -> Type[DurationMetric]:
        """
        Returns the metric class
        """
        return DurationMetric

    @property
    def data_values(self) -> Dict[str, float]:
        """
        Returns the data values
        """
        return {k: v.total for k, v in self.data.items()}

    def items(self, sort: Optional[bool] = None):
        """
        Returns the dict_items view of the data
        """
        if sort: return dict(sorted(self.data.items(), key = lambda x: x[1].total, reverse = sort))
        return self.data_values.items()

    if TYPE_CHECKING:
        def __getitem__(self, key: str) -> DurationMetric:
            """
            Gets the value for the given key
            """
            ...
        def __getattr__(self, name: str) -> DurationMetric:
            """
            Gets the value for the given key
            """
            ...

    
class NestedMonetaryMetric(BaseNestedMetric):
    """
    Nested Monetary Metric Container
    {
        'operation_a': {
            'total': 100.0,
            'average': 50.0,
            'median': 25.0,
            'count': 10,
        },
        'operation_b': {
            'total': 200.0,
            'average': 100.0,
            'median': 50.0,
            'count': 10,
        }
    }
    """
    name: Optional[str] = 'nested_monetary'
    data: Dict[str, MonetaryMetric] = Field(default_factory = dict, description='The nested monetary metric data')

    @property
    def metric_class(self) -> Type[MonetaryMetric]:
        """
        Returns the metric class
        """
        return MonetaryMetric

    @property
    def data_values(self) -> Dict[str, float]:
        """
        Returns the data values

        {
            'operation_a': {
                'total': 100.0,
                'average': 50.0,
                'median': 25.0,
                'count': 10,
            },
            'operation_b': {
                'total': 200.0,
                'average': 100.0,
                'median': 50.0,
                'count': 10,
            }
        }
        """
        return {k: v.data_values for k, v in self.data.items()}


    def items(self, **kwargs):
        """
        Returns the dict_items view of the data
        """
        return self.data_values.items()

    if TYPE_CHECKING:
        def __getitem__(self, key: str) -> MonetaryMetric:
            """
            Gets the value for the given key
            """
            ...
        def __getattr__(self, name: str) -> MonetaryMetric:
            """
            Gets the value for the given key
            """
            ...


class NestedCountMetricV1(BaseModel):
    """
    Nested Count Metric Container

    {
        'website.com': {
            '2022-01-01': 1,
            '2022-01-02': 2,
        },
        'www.website.com': {
            '2022-01-01': 3,
            '2022-01-02': 4,
        },
    }
    """

    name: Optional[str] = 'nested_count'
    data: Dict[str, CountMetric] = Field(default_factory = dict, description = 'The nested count values')

    def items(self, sort: Optional[bool] = None):
        """
        Returns the dict_items view of the data
        """
        return {k: dict(v.items(sort = sort)) for k, v in self.data.items()}.items()

    def __getitem__(self, key: str) -> CountMetric:
        """
        Gets the value for the given key
        """
        if key not in self.data: self.data[key] = CountMetric(name = key)
        return self.data[key]
    
    def __setitem__(self, key: str, value: CountMetric):
        """
        Sets the value for the given key
        """
        # autologger.info(f'Setting {key} to {value}', prefix = self.name, colored = True)
        self.data[key] = value

    def __getattr__(self, name: str) -> CountMetric:
        """
        Gets the value for the given key
        """
        if name not in self.data: self.data[name] = CountMetric(name = name)
        return self.data[name]
    
    def __setattr__(self, name: str, value: CountMetric) -> None:
        """
        Sets the value for the given key
        """
        self.data[name] = value
    
    def __repr__(self) -> str:
        """
        Representation of the object
        """
        return f'{dict(self.items())}'
        
    def __str__(self) -> str:
        """
        Representation of the object
        """
        return self.__repr__()
    

class NestedDurationMetricV1(BaseModel):
    """
    Nested Duration Metric Container

    {
        'operation_a': 240.0,
        'operation_b': 120.0,
    }
    """
    name: Optional[str] = 'nested_duration'
    data: Dict[str, DurationMetric] = Field(default_factory = dict, description='The nested duration metric data')

    @property
    def data_values(self) -> Dict[str, float]:
        """
        Returns the data values
        """
        return {k: v.total for k, v in self.data.items()}

    def items(self, sort: Optional[bool] = None):
        """
        Returns the dict_items view of the data
        """
        if sort: return dict(sorted(self.data.items(), key = lambda x: x[1].total, reverse = sort))
        return self.data_values.items()

    def __getitem__(self, key: str) -> DurationMetric:
        """
        Gets the value for the given key
        """
        if key not in self.data: self.data[key] = DurationMetric(name = key)
        return self.data[key]
    
    def __setitem__(self, key: str, value: DurationMetric):
        """
        Sets the value for the given key
        """
        self.data[key] = value

    def __getattr__(self, name: str) -> DurationMetric:
        """
        Gets the value for the given key
        """
        if name not in self.data: self.data[name] = DurationMetric(name = name)
        return self.data[name]
    
    def __setattr__(self, name: str, value: DurationMetric) -> None:
        """
        Sets the value for the given key
        """
        self.data[name] = value
    
    def __repr__(self) -> str:
        """
        Representation of the object
        """
        return f'{dict(self.items())}'
        
    def __str__(self) -> str:
        """
        Representation of the object
        """
        return self.__repr__()
    

MetricT = Union[
    CountMetric, 
    DurationMetric, 
    MonetaryMetric, 
    NestedDurationMetric, 
    NestedCountMetric, 
    NestedMonetaryMetric,
    NumericValuesContainer, 
]
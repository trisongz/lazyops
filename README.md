# lazyops
 A collection of Lazy Python Functions that aim to balance functionality, performance, and utility.

 ** Why **
After the nth time of rewriting and/or copying existing functions, I figured it was easier to maintain them all in a single library.

### Dependencies
- Python 3.7+
- [pysimdjson](https://github.com/TkTech/pysimdjson): simdjson's C++ JSON parser can handle 2 GB/s+ of throughput, allowing millions of JSON docs to be parsed per sec/per core.
- [fileio](https://github.com/trisongz/fileio): My personal file lib that wraps many useful I/O ops, allowing you to work with cloud objects faster, and in less lines of code.
- [aiohttp](https://github.com/aio-libs/aiohttp): Enables async http calls, maximizing throughput for web requests.
- [dateparser](https://github.com/scrapinghub/dateparser): Makes working with natural query dates easier `5 days ago`.
- [six](): Enables functionality in `retryable` decorator.

### Installation
Install directory from pypi

`pip install --upgrade lazyops`

### API Usage

**Time/Timer/Date Functionalities**

```python
import time
# as easy to remember aliases
from lazyops import timer, ttime, dtime

# or direct imports
from lazyops import LazyTimer, LazyTime, LazyDate

# Initialize a new Time
x = start_time(short=False) # Shorthand, secs = s, mins = m, etc.
time.sleep(5)

print(x.ablstime) # absolute time, which will return
# This allows you to access both a string value (aka no more formatting) and the actual value
# LazyData(string='5.0 secs', value={'secs': 5.046847105026245}, dtype='time')

# You can also call any of the properties 
print(x.secs)
# 5.046847105026245

# The time will continue unless x.stop() is called, which will stop the time from incrementing.
x.stop()

# Timer allows you to initialize and manage a collection of timers

# since it's not initialized yet, calling it will create a new timer and return a LazyTime.
timer('benchmark_1')

# Calling it again will return the same LazyTime object that's been initialized
timer('benchmark_1')

# This will now stop the timer, as the same method as x.stop()
timer.stop_timer('benchmark_1')

# You can access all the timers through the class's global properties
timer.timers()

```

**Lazyclass Functionalities** [WIP]

*To Do:*
- Implement `many=True` found in `dataclasses_json`


```python
from dataclass import dataclass
from lazyops import lazyclass

from typing import Optional, Dict

@lazyclass
@dataclass
class HeroPower:
    desc: str
    strength: float


@lazyclass
@dataclass
class NewHero:
    name: str
    desc: str
    powers: Optional[Dict[str, HeroPower]]

    @classmethod
    def load(cls, data):
        if isinstance(data, dict):
            return NewHero.from_dict(data)
        return NewHero.from_json(data)


hero_config = {
    'name': 'Batman',
    'desc': 'Gothams Dark Knight',
    'powers': {
        'Rich': {
            'desc': 'Money enables Batman to do many things',
            'strength': 1000.0
        },
        'Ingenuity': {
            'desc': 'Batman invents lots of things',
            'strength': 500.0
        }
    }
}

Batman = NewHero.load(hero_config)

```

**LazyAPI Functionalities**

Build JIT API Models from a JSON / Dict, leveraging lazyclass

```python
from lazyops import LazyAPI

api_config = {
    'url': 'https://model.api.domain.com',
    'token': 'supersecuretoken',
    'default_params': {'model': 'nlpmodel'},
    'params_key': 'params',
    'data_key': 'inputs',
    'default_fetch': 'predict',
    'default_async': None,
    'route_config': {
        'predict': {
            'method': 'POST',
            'path': '/predict/',
            'params': {'model': 'nlpmodel'},
            'params_key': 'params',
            'data_key': 'inputs',
            'is_async': False,
            'prefix_payload': 'payload',
            'decode_json': True,
        },
        'status': {
            'method': 'GET',
            'path': '/status/',
            'params': None,
            'params_key': None,
            'data_key': None,
            'decode_json': True,
        },
    }
}

api = LazyAPI.build(api_config)
res = api.predict(data='api model task data ...')
print(res)

```

TBC
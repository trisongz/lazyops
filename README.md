# Lazy Op(eration)s or lazyops

A collection Python modules and submodules focused on balancing functionality, 
performance, utility and Lazyiness.

---

### Installation
Install directory from pypi

`pip install --upgrade lazyops`

Install from Github

`pip install --upgrade git+https://github.com/trisongz/lazyops`

---

## The `LazyOps` Philosophy

**Minimalistic**:  Minimal External Libraries/Dependencies. Minimal imports.

**Automatic and JIT**: Use a `Just-in-Time` approach for loading dependencies. 
Auto-Install external libraries `as needed` for submodules.

**Minimal Lines of Code to Accomplish Goal**: Tries to handle as many use-cases 
as possible with minimal limitations on end-user in how its defined.

**High Performant**: Carefully selected, battle-tested libraries providing the 
highest level of performance, while consuming as little resources as needed (RAM)
or scale to as many resources allowed (Threads)

**(Mostly) Filesystem Agnostic**: Cloud Object _(GCS atm)_ or Local files are 
supported automatically. 

**Reduce Redudancy**: Handle redundant user logic automatically unless explicitly
defined. 

**Object Oriented**: Clean Classes and Objects allow for out-of-the-box usage or 
for customizability.

**Builtin Async**: If it needs to be done fast or many times, `async` should probably
be available.

Counter-intuitively, building `lazyops` was anything-but-lazy. To (try) to accomplish 
all the above, every class, object, or function had to be designed to be written once
with the idea that they can stand on their own for as many use cases as possible.

This project is a work in process and will continue to evolve over time.


---

### The Minimal Dependencies (and rationale)

- Python 3.7+
- [pysimdjson](https://github.com/TkTech/pysimdjson): simdjson's C++ JSON parser can 
handle 2 GB/s+ of throughput, allowing millions of JSON docs to be parsed per sec/per core.
- [fileio](https://github.com/trisongz/fileio): My personal file lib that wraps many 
useful I/O ops, allowing you to work with cloud objects faster, and in less lines of code.
- [aiohttp](https://github.com/aio-libs/aiohttp): Enables async http calls, maximizing 
throughput for web requests.
- [dateparser](https://github.com/scrapinghub/dateparser): Makes working with natural 
query dates easier `5 days ago`.
- [six](): Enables functionality in `retryable` decorator.

---

### LazyOps API Usage

WIP often means documentation itself is WIP, while module is fully functional. 
Feel free to dig into the source code or try it out in examples.

Unfortunately documentation doesn't write itself... yet. And well. Lazyiness.

- [LazyOps Core](#lazyops-core)
- [LazyClassses](#lazyclasses)
- [LazyAPI](#lazyapi)
- [LazyDatabase](#) - WIP
- [LazyRPC](#) - WIP
- [LazyIO](#) - WIP
- [LazySources](#) - WIP
- [LazyBloom](#) - WIP


---

#### LazyOps Core

LazyOps' Core APIs that can be used to handle most common functionalities that can often
be redundant to constantly define.

**Utilities**

Useful functions that speed up development.

```python
from lazyops import lazy_init

# Lazily initialize Tensorflow and ensure Tensorflow == 2.5.0 
# before importing
# tf can now be used as you would if you called `import tensorflow as tf`

tf = lazy_init('tensorflow==2.5.0', 'tensorflow')
physical_devices = tf.config.list_physical_devices('GPU')
print("Num GPUs:", len(physical_devices))

from lazyops import get_logger

# This will create a logger that handles stderr / stdout for Notebook envs
# This logger is also threadsafe as it creates a threadlock to prevent duplication

logger = get_logger('MyLib', submodule = __file__)

from lazyops import timed_cache, retryable, lazymultiproc, lazyproc

def get_dataset(*args, **kwargs):
    # do stuff
    return dataset

# default num_processes = CPU Cores
@lazymultiproc(dataset_callable=get_dataset, num_procs=10) 
def process_dataset(item, *args, **kwargs):
    # do stuff
    return item

# LRU Cache with timed expiration
@timed_cache(seconds=60, maxsize=600) 
def load_dataset(*args, **kwargs):
    # do stuff
    return dataset

# turns this function into a thread.Thread function, returning thread obj.
@lazyproc(name = 'monitoring_x', start = True, daemon = False) 
def monitor_x(*args, **kwargs):
    # do stuff
    return

# Retries this function call 
@retryable(stop_max_attempt_number = 5) 
def call_api(*args, **kwargs):
    # do stuff
    return response

# Utils for running shell commands and cloning repo projects
from lazyops import run_cmd, clone_repo

# clones lazyops to relative /cwd/lops. 
# if add_to_syspath = True, will append repo path to $PATH
clone_repo(repo='https://github.com/trisongz/lazyops', path='lops', absl=False, add_to_syspath=True)

# returns system response of `df -h` as string
res = run_cmd('df -h') 

```


**Time/Timer/Date**

Handle time, timers and datetime mostly automatically.

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
---

#### LazyClasses

LazyClasses are an extension of `dataclasses`, building on top of [fastclasses-json](https://github.com/cakemanny/fastclasses-json), 
and inspired by heavy usage of [dataclasses-json](https://github.com/lidatong/dataclasses-json). `LazyClass` utilizes `simdjson` as
the default `JSON` serializer for faster performance.


Example Usage:

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
# Or directly
Batman = NewHero(**hero_config)

```

**Roadmap**
- Implement `many=True` found in `dataclasses_json`

---

#### LazyAPI

Define and Create API Endpoints as a Class with just a `Dict` with
builtin `async` support. API Models are compiled `JIT` with endpoints
set as the `LazyAPI` class attribute, enabling them to be called as
a function.

Example Usage

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
---

#### LazyRPC

WIP

---

#### LazyDatabase

WIP

---

#### LazyIO

WIP

---

#### LazySources

WIP

---

#### LazyBloom

WIP 

---


#### Credits & Acknowledgements

`LazyOps` heavily builds & borrows on the work of others in many instances.
In order to maintain minimalism and not have unneeded libraries added to dependencies,
some parts of the library have been added into `LazyOps`. The original works often inspired
new ideas from studying the code and are definitely worth checking out.


In no particular order:

- [retrying](https://github.com/rholder/retrying)
- [fastapi-jsonrpc](https://github.com/smagafurov/fastapi-jsonrpc)
- [fastclasses-json](https://github.com/cakemanny/fastclasses-json)
- [dataclasses-json](https://github.com/lidatong/dataclasses-json)
- [gdelt-doc-api](https://github.com/alex9smith/gdelt-doc-api)

TBC
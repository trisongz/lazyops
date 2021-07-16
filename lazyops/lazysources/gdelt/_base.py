
from lazyops import lazy_init, get_logger, timed_cache, LazyObject
lazy_init('pandas')

import pandas as pd

from enum import Enum
from typing import Dict, Optional, List, Union, Tuple

from dataclasses import dataclass
from lazyops.apis import LazySession, async_req
from lazyops.lazyio import LazyJson
from lazyops.lazyclasses import lazyclass


logger = get_logger('LazySources', 'GDELT')


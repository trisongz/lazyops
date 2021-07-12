import os
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings('ignore', message='RequestsDependencyWarning')

lazyops_root = os.path.abspath(os.path.dirname(__file__))
from .lazyclasses import lazyclass

from .envs import LazyEnv, get_logger
from .models import LazyData, LazyTime, LazyDate, LazyFormatter, LazyTimer
from .common import lazylibs, lazy_init, run_cmd, clone_repo, File
from .utils import find_binary_in_path, timed_cache, latest_tf_ckpt, require_module
from .utils import build_chunks, retryable, list_to_dict
from .apis import LazyAPI, LazyAPIConfig

env = LazyEnv
item = LazyData
timer = LazyTimer
ttime = LazyTime
formatter = LazyFormatter
dtime = LazyDate
libs = lazylibs
fio = File
lazyapi = LazyAPI
apiconfig = LazyAPIConfig
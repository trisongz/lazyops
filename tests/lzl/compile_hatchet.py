import sys
import inspect
import pathlib
import jinja2
from hatchet_sdk.worker import Worker

here = pathlib.Path(__file__).parent
output_file = here.joinpath('worker.py')

base_string = """
from __future__ import annotations

from hatchet_sdk.worker import Worker as BaseWorker
from typing import Any, Dict, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from hatchet_sdk.worker import *

class Worker(BaseWorker):
    
{% for func in new_funcs %}
{{ func }}
{% endfor %}
"""

def get_new_init():
    
    init_string = inspect.getsource(Worker.__init__)
    init_string = init_string.replace(
        'config: ClientConfig = {},',
        "config: ClientConfig = {},\n\
        session: Optional['HatchetSession'] = None,\n\
        context_class: Type[Context] = Context,\n"
    )
    init_string = init_string.replace(
        'labels: dict[str, str | int] = {},', 
        "labels: dict[str, str | int] = {}\n, \
        session: Optional['HatchetSession'] = None,\n \
        context_class: Type[Context] = Context,\n"
    )
    init_string = init_string.replace(
        'self.client = new_client_raw(config)', 
        "self.session = session\n\
        self.client = self.session.client if self.session else new_client(config)\n\
        self._context_cls = context_class\n"
    )
    return init_string

def get_patched_wrapped_action():
    action_string = inspect.getsource(Worker.handle_start_step_run)
    action_string = action_string.replace(
        'context = Context(',
        'context = self._context_cls(',
    )
    return action_string



new_funcs = [get_new_init(), get_patched_wrapped_action()]
temp = jinja2.Template(base_string)


# worker_string = inspect.getsource(Worker)
# worker_string = worker_string.replace('context = Context(', 'context = self._context_cls(', 1)

# output = base_string.format(worker_string = worker_string)
output_file.write_text(temp.render(new_funcs = new_funcs))
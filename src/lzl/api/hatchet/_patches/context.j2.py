from __future__ import annotations

"""
The Hatchet Context Object

Patched: {{ timestamp }}
Version: {{ version }}
Last Version: {{ last_version }}

"""

import copy
from concurrent.futures import ThreadPoolExecutor
{%- if version == '0.31.0' %}
from hatchet_sdk.context import Context as BaseContext, ContextAioImpl
{%- else %}
from hatchet_sdk.context.context import Context as BaseContext, ContextAioImpl
{%- endif %}
# from hatchet_sdk.context import Context as BaseContext
from hatchet_sdk.logger import logger
from lazyops.libs.abcs.utils.format_utils import clean_html
from ..utils import json_serializer
from typing import TypeVar, Dict, Any, Optional, List, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from hatchet_sdk.clients.dispatcher import Action
    from hatchet_sdk.clients.events import EventClientImpl
    from hatchet_sdk.clients.run_event_listener import RunEventListenerClient
    from hatchet_sdk.clients.workflow_listener import PooledWorkflowRunListener
    from hatchet_sdk.clients.admin import AdminClientImpl
    from hatchet_sdk.clients.dispatcher import Action, DispatcherClientImpl
{%- if version != '0.31.0' %}
    from hatchet_sdk.context.worker_context import WorkerContext
{%- endif %}

ContextT = TypeVar('ContextT', bound = 'Context')

class Context(BaseContext):
    """
    The Context Object
    """

    if TYPE_CHECKING:
        input: Dict[str, Any]
{% for name, func in new_funcs.items() %}
{{ func }}
{% endfor %}
    @property
    def parents(self) -> Dict[str, Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict, List]]]]]:
        """
        Gets the parents
        """
        return self.data.get('parents', {})

    def get_kwargs(self) -> Dict[str, Any]:
        """
        Gets the kwargs
        """
        return copy.deepcopy(self.input)

    @property
    def event_trigger(self) -> str:
        """
        Gets the event trigger
        """
        return self.input.get('trigger', self.data.get('triggered_by', 'manual'))

    
    @property
    def is_cron(self) -> bool:
        """
        Checks if the event is a cron event
        """
        return self.event_trigger == 'cron'
    
    @property
    def workflow_id(self) -> str:
        """
        Gets the workflow run id
        """
        return self.action.workflow_run_id
    
    def log(self, line: str):
        """
        Logs a line
        """
        # Need to clean up any colored formatting
        # Remove the last 4 characters
        line = clean_html(line)
        if line.endswith('[0m'): line = line[:-4]
        return super().log(line)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Gets the value
        """
        return self.input.get(key, default)
from __future__ import annotations

"""
The Hatchet Context Object
"""
import copy
from concurrent.futures import ThreadPoolExecutor
from hatchet_sdk.context import Context as BaseContext, ContextAioImpl
from hatchet_sdk.clients.dispatcher import Action
from hatchet_sdk.clients.events import EventClientImpl
from hatchet_sdk.clients.run_event_listener import (
    RunEventListenerClient,
)
from hatchet_sdk.clients.workflow_listener import PooledWorkflowRunListener

from hatchet_sdk.clients.admin import AdminClientImpl
from hatchet_sdk.clients.dispatcher import Action, DispatcherClientImpl
from hatchet_sdk.logger import logger
from lazyops.libs.abcs.utils.format_utils import clean_html
from .utils import json_serializer
from typing import TypeVar, Dict, Any, Optional, List, Union, TYPE_CHECKING


ContextT = TypeVar('ContextT', bound = 'Context')

class Context(BaseContext):
    """
    The Context Object
    """

    if TYPE_CHECKING:
        input: Dict[str, Any]
    
    def __init__(
        self,
        action: Action,
        dispatcher_client: DispatcherClientImpl,
        admin_client: AdminClientImpl,
        event_client: EventClientImpl,
        workflow_listener: PooledWorkflowRunListener,
        workflow_run_event_listener: RunEventListenerClient,
        namespace: str = "",
    ):
        """
        Initializes the Context
        """
        self.aio = ContextAioImpl(
            action,
            dispatcher_client,
            admin_client,
            event_client,
            workflow_listener,
            workflow_run_event_listener,
            namespace,
        )
        if isinstance(action.action_payload, (str, bytes, bytearray)):
            try:
                self.data = json_serializer.loads(action.action_payload)
            except Exception as e:
                logger.error(f"Error parsing action payload: {e}")
                # Assign an empty dictionary if parsing fails
                self.data = {}
        else:
            # Directly assign the payload to self.data if it's already a dict
            self.data = (
                action.action_payload if isinstance(action.action_payload, dict) else {}
            )


        self.action = action
        self.stepRunId = action.step_run_id
        self.exit_flag = False
        self.dispatcher_client = dispatcher_client
        self.admin_client = admin_client
        self.event_client = event_client
        self.workflow_listener = workflow_listener
        self.workflow_run_event_listener = workflow_run_event_listener
        self.namespace = namespace

        # FIXME: this limits the number of concurrent log requests to 1, which means we can do about
        # 100 log lines per second but this depends on network.
        self.logger_thread_pool = ThreadPoolExecutor(max_workers=1)
        self.stream_event_thread_pool = ThreadPoolExecutor(max_workers=1)

        # store each key in the overrides field in a lookup table
        # overrides_data is a dictionary of key-value pairs
        self.overrides_data = self.data.get("overrides", {})

        if action.get_group_key_run_id != "":
            self.input = self.data
        else:
            self.input = self.data.get("input", {})


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
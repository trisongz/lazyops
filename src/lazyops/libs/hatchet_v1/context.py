from __future__ import annotations

"""
The Hatchet Context Object
"""
import copy
import contextlib
from aiostream.stream import merge
from multiprocessing import Event
from concurrent.futures import ThreadPoolExecutor
from hatchet_sdk.client import ClientImpl
from hatchet_sdk.context import Context as BaseContext, ChildWorkflowRef as BaseChildWorkflowRef
from hatchet_sdk.clients.dispatcher import Action
from hatchet_sdk.clients.listener import StepRunEvent, WorkflowRunEventType
from hatchet_sdk.clients.admin import ScheduleTriggerWorkflowOptions, TriggerWorkflowOptions
from hatchet_sdk.clients.rest.models.workflow_run_status import WorkflowRunStatus
from hatchet_sdk.logger import logger
from lazyops.utils.serialization import Json
from lazyops.libs.abcs.utils.format_utils import clean_html
from .utils import json_serializer
from .types import DotDict
from typing import TypeVar, Dict, Any, Optional, List, Union, TYPE_CHECKING

ContextT = TypeVar('ContextT', bound = 'Context')

class ChildWorkflowRef(BaseChildWorkflowRef):
    """
    The Child Workflow Ref
    """
    
    def getResult(self) -> StepRunEvent:
        """
        Gets the result
        """
        # sourcery skip: raise-specific-error
        try:
            res = self.client.rest.workflow_run_get(self.workflow_run_id)
            step_runs = res.job_runs[0].step_runs if res.job_runs else []

            step_run_output = {}
            for run in step_runs:
                stepId = run.step.readable_id if run.step else ""
                step_run_output[stepId] = json_serializer.loads(run.output) if run.output else {}

            statusMap = {
                WorkflowRunStatus.SUCCEEDED: WorkflowRunEventType.WORKFLOW_RUN_EVENT_TYPE_COMPLETED,
                WorkflowRunStatus.FAILED: WorkflowRunEventType.WORKFLOW_RUN_EVENT_TYPE_FAILED,
                WorkflowRunStatus.CANCELLED: WorkflowRunEventType.WORKFLOW_RUN_EVENT_TYPE_CANCELLED,
            }

            if res.status in statusMap:
                return StepRunEvent(
                    type=statusMap[res.status], payload = json_serializer.dumps(step_run_output)
                )

        except Exception as e:
            raise Exception(str(e)) from e
        
    
    def handle_event(self, event: StepRunEvent):
        # sourcery skip: merge-comparisons
        if (
            event.type == WorkflowRunEventType.WORKFLOW_RUN_EVENT_TYPE_FAILED
            or event.type == WorkflowRunEventType.WORKFLOW_RUN_EVENT_TYPE_CANCELLED
            or event.type == WorkflowRunEventType.WORKFLOW_RUN_EVENT_TYPE_TIMED_OUT
        ):
            self.close()
            raise RuntimeError(event.type)

        if event.type == WorkflowRunEventType.WORKFLOW_RUN_EVENT_TYPE_COMPLETED:
            self.close()
            return json_serializer.loads(event.payload)
    

    @contextlib.asynccontextmanager
    async def stream(self):
        """
        Streams the workflow run
        """
        listener_stream = self.client.listener.stream(self.workflow_run_id)
        polling_stream = self.polling()
        try:
            async with merge(listener_stream, polling_stream).stream() as stream:
                async for event in stream:
                    if not self.poll: break
                    if event.payload is None:
                        res = self.getResult()
                        if res: yield res
                    else:
                        yield event
        finally:
            pass
                

    async def until_complete(self):
        """
        Waits until the workflow is complete
        """
        with contextlib.suppress(Exception, RuntimeError, GeneratorExit):
            async for event in self.stream():
                res = self.handle_event(event)
                if res: return


class Context(BaseContext):
    """
    The Context Object
    """

    if TYPE_CHECKING:
        input: Dict[str, Any]
    
    def __init__(self, action: Action, client: ClientImpl):
        """
        Initializes the context
        """
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
        self.exit_flag = Event()
        self.client = client

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
        
        # self._parents: Optional[DotDict] = None

    @property
    def parents(self) -> Dict[str, Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict, List]]]]]:
        """
        Gets the parents
        """
        return self.data.get('parents', {})
        # if self._parents is None:
        #     self._parents = DotDict(**self.data.get('parents', {}))
        # return self._parents


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
    

    def spawn_workflow(self, workflow_name: str, input: dict = None, key: str = None):
        # sourcery skip: avoid-builtin-shadow
        """
        Spawns a workflow
        """
        input = input or {}
        workflow_run_id = self.action.workflow_run_id
        step_run_id = self.action.step_run_id

        options: ScheduleTriggerWorkflowOptions = {
            "parent_id": workflow_run_id,
            "parent_step_run_id": step_run_id,
            "child_key": key,
            "child_index": self.spawn_index,
        }

        self.spawn_index += 1
        child_workflow_run_id = self.client.admin.run_workflow(
            workflow_name, input, options
        )
        return ChildWorkflowRef(child_workflow_run_id, self.client)

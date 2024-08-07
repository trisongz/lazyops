from __future__ import annotations

import gc
import niquests
from urllib.parse import urljoin
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Union, Literal, TYPE_CHECKING

"""
PostHog Context Type
{
    "event": "my_event",
    "properties": {
        "$set": ...,
        "my_property": "my_value",
    },
    "distinct_id": "my_distinct_id",
}
"""

PHCtxT = Dict[str, Union[Dict[str, Any], str]]

class PostHogAuth(niquests.auth.BearerTokenAuth):
    """
    The PostHog Auth
    """

    def __init__(self, api_key: str):
        """
        Initializes the PostHog Auth
        """
        self.api_key = api_key
        super().__init__(token = api_key)

    def __call__(self, r: 'niquests.Request') -> 'niquests.Request':
        """
        The Call Method
        """
        r.headers["Authorization"] = f"Bearer {self.api_key}"
        r.headers["Accept"] = "application/json"
        r.headers["Content-Type"] = "application/json"
        return r



class PostHogEndpoint(BaseModel):
    endpoint: str
    
    def get_url(self, *paths: str) -> str:
        """
        Returns the URL
        """
        return urljoin(self.endpoint, '/'.join(paths)).rstrip('/')
    
    @property
    def capture(self) -> str:
        """
        Returns the Capture URL
        """
        return self.get_url('capture')
    
    @property
    def batch(self) -> str:
        """
        Returns the Batch URL
        """
        return self.get_url('batch')
    
    @property
    def identify(self) -> str:
        """
        Returns the Identify URL
        """
        return self.get_url('identify')


class BaseEvent(BaseModel):
    """
    Base Event
    """

    model_config = ConfigDict(extra = 'allow', arbitrary_types_allowed = True)

    @property
    def is_valid(self) -> bool:
        """
        Returns True if the event is valid
        """
        return True 
    

    def prepare_request(
        self,
        exclude_none: Optional[bool] = True,
        batched: Optional[bool] = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Formats the event for batching
        """
        return self.model_dump(exclude_none = exclude_none, **kwargs)


class CaptureEvent(BaseEvent):
    """
    The Capture Event
    """
    event: str
    properties: Optional[Dict[str, Any]] = Field(default_factory = dict)
    distinct_id: Optional[str] = None
    timestamp: Optional[int] = None
    token: Optional[str] = None
    context: Optional[Dict[str, Any]] = Field(None)
    
    @property
    def is_valid(self) -> bool:
        """
        Returns True if the event is valid
        """
        return self.event and self.distinct_id
    

    def prepare_request(
        self,
        exclude_none: Optional[bool] = True,
        batched: Optional[bool] = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Formats the event for batching
        """
        data = self.model_dump(exclude_none = exclude_none, **kwargs)
        if batched:
            data['properties']['distinct_id'] = data.pop('distinct_id')
            if 'timestamp' in data: data['properties']['timestamp'] = data.pop('timestamp')
        return data



class IdentifyEvent(BaseEvent):
    """
    The Identify Event
    """
    distinct_id: str
    properties: Optional[Dict[str, Any]] = Field(default_factory = dict)
    token: Optional[str] = None
    context: Optional[Dict[str, Any]] = Field(default_factory = dict)
    
    @property
    def is_valid(self) -> bool:
        """
        Returns True if the event is valid
        """
        return self.distinct_id
    

    def prepare_request(
        self,
        exclude_none: Optional[bool] = True,
        batched: Optional[bool] = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Formats the event for batching
        """
        data = self.model_dump(exclude_none = exclude_none, **kwargs)
        if batched:
            data['properties']['distinct_id'] = data.pop('distinct_id')
            if 'timestamp' in data: data['properties']['timestamp'] = data.pop('timestamp')
        return data


EventT = Union[CaptureEvent, IdentifyEvent]

class EventQueue(BaseModel):
    """
    The Event Handler
    """
    capture_events: Optional[List[CaptureEvent]] = Field(default_factory = list, description = 'The capture events')
    identify_events: Optional[List[IdentifyEvent]] = Field(default_factory = list, description = 'The identify events')

    def add_event(
        self,
        event: Union[EventT, str],
        **kwargs,
    ):
        """
        Adds an event to the queue
        """
        if isinstance(event, str): event = CaptureEvent(event = event, **kwargs)
        if isinstance(event, CaptureEvent): self.capture_events.append(event)
        elif isinstance(event, IdentifyEvent): self.identify_events.append(event)

    def __len__(self):
        """
        Returns the length of the event queue
        """
        return len(self.capture_events) + len(self.identify_events)
    
    def clear(self):
        """
        Clears the event queue
        """
        self.capture_events.clear()
        self.identify_events.clear()
        # gc.collect()
    
    def prepare_events(
        self, 
        kind: Literal['capture', 'identify'] = 'capture',
        batched: Optional[bool] = False,
        exclude_none: Optional[bool] = True,
        clear_after: Optional[bool] = True,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Prepares the events for serialization
        """
        if kind == 'capture': 
            events = [e.prepare_request(exclude_none = exclude_none, batched = batched, **kwargs) for e in self.capture_events]
            if clear_after: self.capture_events.clear()
            # gc.collect()
            return events
            
    def __bool__(self):
        """
        Returns whether the queue is empty
        """
        return len(self) > 0
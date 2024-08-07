"""
The PostHog Client

An Asyncronous PostHog Client that utilizes Intelligent Batching and Asynchronous Task Queues
to send events to PostHog in a more efficient and scalable manner.

This client is designed with the following features in mind:
- Intelligent Batching: The client automatically batches events based on the configured batch size and sends them in batches once the batch size is reached or the maximum batch interval has been reached.
- Asynchronous Task Queues: The client uses asynchronous task queues to handle the sending of events. This allows the client to send events in parallel and improves the overall performance of the client.
- Context Manager: The client provides a context manager that can be used to force sending of events immediately after exiting the context rather than waiting for the batching logic to complete.
- Non-Blocking: By utilizing asynchronous task queues and non-blocking requests, the client can handle a large number of events without blocking the main thread.
- Lazily Initializes: The client lazily initializes the PostHog client and only initializes it when the first event is added.


Usage:

# Initialize the PostHog Client
# you can capture events explicitly by using the client.capture method or by using the @capture decorator
# to defer until the function is called. If `POSTHOG_API_KEY` is not set, then the client will not be initialized

from lazyops.libs.posthog import PostHogClient, capture, PHCtxT

# This will lazily initialize the client since the client is not yet defined

@capture(event = 'lazy_event')
async def lazy_event(*args, x: Optional[int] = None, y: Optional[int] = None, ph_ctx: PHCtxT, **kwargs):
    
    ph_ctx['properties']['event_name'] = 'lazy_event'
    ph_ctx['properties']['random_id'] = create_unique_id()
    if x: ph_ctx['properties']['x'] = x
    if y: ph_ctx['properties']['y'] = y
    ph_ctx['distinct_id'] = f'xxx-{create_unique_id()}'
    return 'test'


client = PostHogClient(api_key = 'xxx', project_id = 'xxx')

# Explicitly Capture an Event with the Client since it has been initialized

@client.capture(event = 'test_event')
async def capture_event(*args, x: Optional[int] = None, y: Optional[int] = None, ph_ctx: PHCtxT, **kwargs):
    
    ph_ctx['properties']['event_name'] = 'test_event'
    ph_ctx['properties']['random_id'] = create_unique_id()
    if x: ph_ctx['properties']['x'] = x
    if y: ph_ctx['properties']['y'] = y
    ph_ctx['distinct_id'] = f'xxx-{create_unique_id()}'
    
    return 'test'


"""

from .config import PostHogSettings
from .client import PostHogClient
from .types import PostHogEndpoint, CaptureEvent, IdentifyEvent, EventQueue, EventT, PHCtxT
from .utils import get_posthog_client, get_posthog_settings, capture


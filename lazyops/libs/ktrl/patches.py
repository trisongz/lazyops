from __future__ import annotations

import kopf
import copy
import datetime
import aiohttp

from kopf._cogs.clients import api, errors
from kopf._cogs.configs import configuration
from kopf._cogs.helpers import typedefs
from kopf._cogs.structs import bodies, references
import kopf._cogs.clients.events
from typing import Dict, Any, TYPE_CHECKING
from lazyops.utils.logs import default_logger as _logger

async def post_event(
    *,
    ref: bodies.ObjectReference,
    type: str,
    reason: str,
    message: str = '',
    resource: references.Resource,
    settings: configuration.OperatorSettings,
    logger: typedefs.Logger,
) -> None:
    """
    Issue an event for the object.
    This is where they can also be accumulated, aggregated, grouped,
    and where the rate-limits should be maintained. It can (and should)
    be done by the client library, as it is done in the Go client.
    """

    # Prevent "event explosion", when core v1 events are handled and create other core v1 events.
    # This can happen with `EVERYTHING` without additional filters, or by explicitly serving them.
    from .config import get_ktrl_settings
    _settings = get_ktrl_settings()
    conf = _settings.get_kopf_config()
    if ref['apiVersion'] == 'v1' and ref['kind'] == 'Event':
        return

    # See #164. For cluster-scoped objects, use the current namespace from the current context.
    # It could be "default", but in some systems, we are limited to one specific namespace only.
    namespace_name: str = ref.get('namespace') or (await api.get_default_namespace()) or 'default'
    namespace = references.NamespaceName(namespace_name)
    full_ref: bodies.ObjectReference = copy.copy(ref)
    full_ref['namespace'] = namespace

    # Prevent a common case of event posting errors but shortening the message.
    if len(message) > conf['MAX_MESSAGE_LENGTH']:
        infix = conf['CUT_MESSAGE_INFIX']
        prefix = message[:conf['MAX_MESSAGE_LENGTH'] // 2 - (len(infix) // 2)]
        suffix = message[-conf['MAX_MESSAGE_LENGTH'] // 2 + (len(infix) - len(infix) // 2):]
        message = f'{prefix}{infix}{suffix}'

    now = datetime.datetime.now(tz = datetime.timezone.utc)
    body = {
        'metadata': {
            'namespace': namespace,
            'generateName': conf['GENERATE_EVENT_NAME'],
        },

        'action': 'Action?',
        'type': type,
        'reason': reason,
        'message': message,

        'reportingComponent': _settings.component_name,
        'reportingInstance': _settings.component_instance,
        'source' : {'component': _settings.component_name}, # used in the "From" column in `kubectl describe`.

        'involvedObject': full_ref,

        'firstTimestamp': f'{now.isoformat()}Z',  # '2019-01-28T18:25:03.000000Z' -- seen in `kubectl describe ...`
        'lastTimestamp': f'{now.isoformat()}Z',  # '2019-01-28T18:25:03.000000Z' - seen in `kubectl get events`
        'eventTime': f'{now.isoformat()}Z',  # '2019-01-28T18:25:03.000000Z'
    }

    try:
        await api.post(
            url=resource.get_url(namespace=namespace),
            headers={'Content-Type': 'application/json'},
            payload=body,
            logger=logger,
            settings=settings,
        )

    # Events are helpful but auxiliary, they should not fail the handling cycle.
    # Yet we want to notice that something went wrong (in logs).
    except errors.APIError as e:
        logger.warning(f"Failed to post an event. Ignoring and continuing. "
                       f"Code: {e.code}. Message: {e.message}. Details: {e.details}"
                       f"Event: type={type!r}, reason={reason!r}, message={message!r}.")
    except aiohttp.ClientResponseError as e:
        logger.warning(f"Failed to post an event. Ignoring and continuing. "
                       f"Status: {e.status}. Message: {e.message}. "
                       f"Event: type={type!r}, reason={reason!r}, message={message!r}.")
    except aiohttp.ServerDisconnectedError as e:
        logger.warning(f"Failed to post an event. Ignoring and continuing. "
                       f"Message: {e.message}. "
                       f"Event: type={type!r}, reason={reason!r}, message={message!r}.")
    except aiohttp.ClientOSError:
        logger.warning(f"Failed to post an event. Ignoring and continuing. "
                       f"Event: type={type!r}, reason={reason!r}, message={message!r}.")


kopf._cogs.clients.events.post_event = post_event
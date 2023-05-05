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

if TYPE_CHECKING:
    from lazyops.libs.kops.config import KOpsSettings

# Patch so that event logs will show `kops` instead of `kopf` as the source.
_kops_config: Dict[str, Any] = None
_kops_settings: 'KOpsSettings' = None


def _get_config():
    global _kops_config, _kops_settings
    if _kops_settings is None:
        from lazyops.libs.kops.client import KOpsClient
        _kops_settings = KOpsClient.settings
    
    if _kops_config is None:
        _kops_config = {
            'MAX_MESSAGE_LENGTH': _kops_settings.kops_max_message_length,
            'CUT_MESSAGE_INFIX': _kops_settings.kops_cut_message_infix,
            'FINALIZER': _kops_settings.kops_finalizer,
            'PREFIX': _kops_settings.kops_prefix,
            'PERSISTENT_KEY': _kops_settings.kops_persistent_key,
            'GENERATE_EVENT_NAME': _kops_settings.kops_generate_event_name,
            'WATCH_INTERVAL': _kops_settings.kops_watch_interval,
        }
    return _kops_config


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
    conf = _get_config()
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

    now = datetime.datetime.utcnow()
    body = {
        'metadata': {
            'namespace': namespace,
            'generateName': conf['GENERATE_EVENT_NAME'],
        },

        'action': 'Action?',
        'type': type,
        'reason': reason,
        'message': message,

        'reportingComponent': 'kops',
        'reportingInstance': 'dev',
        'source' : {'component': 'kops'},  # used in the "From" column in `kubectl describe`.

        'involvedObject': full_ref,

        'firstTimestamp': now.isoformat() + 'Z',  # '2019-01-28T18:25:03.000000Z' -- seen in `kubectl describe ...`
        'lastTimestamp': now.isoformat() + 'Z',  # '2019-01-28T18:25:03.000000Z' - seen in `kubectl get events`
        'eventTime': now.isoformat() + 'Z',  # '2019-01-28T18:25:03.000000Z'
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
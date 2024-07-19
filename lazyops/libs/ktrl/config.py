from __future__ import annotations

import pathlib
from pydantic import field_validator, PrivateAttr
from pydantic_settings import BaseSettings
from lazyops.utils.logs import logger
from lazyops.utils.system import is_in_kubernetes
from lazyops.libs.abcs.utils.format_utils import build_dict_from_str
from typing import Any, Dict, Optional, List, Tuple, Set, Union, TYPE_CHECKING

if TYPE_CHECKING:
    import jinja2

logger.mute_module('httpx')

_ktrl_settings: Optional['KtrlSettings'] = None

def get_ktrl_settings() -> 'KtrlSettings':
    """
    Returns the ktrl settings
    """
    return _ktrl_settings

def register_ktrl_settings(settings: 'KtrlSettings'):
    """
    Registers the ktrl settings
    """
    global _ktrl_settings
    logger.info('Registering Ktrl Settings')
    _ktrl_settings = settings


class KtrlSettings(BaseSettings):

    # Used for event reporting
    component_name: str = 'ktrl'
    component_instance: str = 'dev'

    ctx_name: Optional[str] = None
    kubeconfig: Optional[str] = None
    
    # This should be modified by the child class
    # i.e. {'lazyops.sh/handled': 'true'}
    resource_label_selector: Optional[Dict[str, Any]] = {'lazyops.sh/handled': 'true'}
    
    disabled_namespaces: Optional[List[str]] = None
    enabled_namespaces: Optional[List[str]] = None
    kopf_enable_event_logging: bool = False
    
    # This should be modified by the child class
    # i.e. lazyops.sh/finalizer
    kopf_finalizer: Optional[str] = 'lazyops.sh/finalizer'
    kopf_persistent_key: str = 'last-handled-configuration'
    kopf_prefix: str = 'lazyops.sh'

    kopf_max_message_length: int = 1024
    kopf_cut_message_infix: str = '...'
    kopf_generate_event_name: str = 'ktrl-event-'

    # Deployment Options
    interval_seconds: int = 30

    _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)
    __pydantic_post_init__ = 'register_post_init'
    

    @property
    def in_k8s(self) -> bool:
        """
        Returns whether we are in k8s
        """
        if 'in_k8s' not in self._extra:
            self._extra['in_k8s'] = is_in_kubernetes()
        return self._extra['in_k8s']
    
    @property
    def templates(self) -> 'jinja2.Environment':
        """
        Returns the jinja2 templates
        """
        return self._extra.get('templates')
    
    @property
    def templates_path(self) -> pathlib.Path:
        """
        Returns the jinja2 templates path
        """
        return self._extra.get('templates_path')

    def get_kopf_config(self) -> Dict[str, Any]:
        """
        Returns the kopf config
        """
        return {
            'MAX_MESSAGE_LENGTH': self.kopf_max_message_length,
            'CUT_MESSAGE_INFIX': self.kopf_cut_message_infix,
            'FINALIZER': self.kopf_finalizer,
            'PREFIX': self.kopf_prefix,
            'PERSISTENT_KEY': self.kopf_persistent_key,
            'GENERATE_EVENT_NAME': self.kopf_generate_event_name,
            'WATCH_INTERVAL': self.interval_seconds,
        }
    

    def register_post_init(self):
        """
        Registers the post init
        """
        register_ktrl_settings(self)


    def set_jinja_templates(self, path: pathlib.Path, **kwargs):
        """
        Sets the jinja templates
        """
        from .helpers import create_jinja_env
        self._extra['templates_path'] = path
        self._extra['templates'] = create_jinja_env(path, **kwargs)
    
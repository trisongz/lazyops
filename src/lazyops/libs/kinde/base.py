from __future__ import annotations

# import jinja2
import pathlib
from lazyops.libs.proxyobj import ProxyObject
from lazyops.utils.pooler import ThreadPooler
from typing import Optional, List, Dict, Any, Union, Type, Tuple, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request
    from .client import KindeClient
    from lazyops.libs.fastapi_utils.types.persistence import TemporaryData
    
    from kinde_sdk.apis.tags.users_api import UsersApi
    from kinde_sdk.apis.tags.applications_api import ApplicationsApi
    from kinde_sdk.apis.tags.organizations_api import OrganizationsApi
    from kinde_sdk.apis.tags.callbacks_api import CallbacksApi
    from kinde_sdk.apis.tags.roles_api import RolesApi
    from kinde_sdk.apis.tags.permissions_api import PermissionsApi

    KindeAPIs = Union[
        UsersApi,
        ApplicationsApi,
        OrganizationsApi,
        CallbacksApi,
        RolesApi,
        PermissionsApi,
    ]


kinde_api_import_paths: Dict[str, str] = {
    'user_api': 'kinde_sdk.apis.tags.users_api.UsersApi',
    'application_api': 'kinde_sdk.apis.tags.applications_api.ApplicationsApi',
    'organization_api': 'kinde_sdk.apis.tags.organizations_api.OrganizationsApi',
    'callback_api': 'kinde_sdk.apis.tags.callbacks_api.CallbacksApi',
    'role_api': 'kinde_sdk.apis.tags.roles_api.RolesApi',
    'permission_api': 'kinde_sdk.apis.tags.permissions_api.PermissionsApi',
}

lib_path = pathlib.Path(__file__).parent
assets_path = lib_path.joinpath('assets')
templates_path = assets_path.joinpath("templates")
staticfile_path = assets_path.joinpath('static')


_kinde_temp_data: Optional['TemporaryData'] = None


def get_kinde_temp_data() -> 'TemporaryData':
    """
    Returns the temporary data object
    """
    global _kinde_temp_data
    if _kinde_temp_data is None:
        from lazyops.libs.abcs.types.persistence import TemporaryData
        _kinde_temp_data = TemporaryData(lib_path.joinpath('data', 'kinde.cache'))
    return _kinde_temp_data



class KindeContextObject:
    """
    The Kinde Context
    """
    pre_validate_hooks: Optional[List[Callable]] = []
    post_validate_hooks: Optional[List[Callable]] = []
    post_validate_auth_hooks: Optional[List[Callable]] = []
    post_callback_auth_hooks: Optional[List[Callable]] = []
    configured_validators: List[str] = []

    def add_post_validate_hook(self, hook: Callable):
        """
        Adds a post validate hook
        """
        if self.post_validate_hooks is None:
            self.post_validate_hooks = []
        self.post_validate_hooks.append(hook)
    
    def add_pre_validate_hook(self, hook: Callable):
        """
        Adds a pre validate hook
        """
        if self.pre_validate_hooks is None:
            self.pre_validate_hooks = []
        self.pre_validate_hooks.append(hook)

    def add_post_validate_auth_hook(self, hook: Callable):
        """
        Adds a post validate auth hook
        """
        if self.post_validate_auth_hooks is None:
            self.post_validate_auth_hooks = []
        self.post_validate_auth_hooks.append(hook)

    def add_post_callback_auth_hook(self, hook: Callable):
        """
        Adds a post callback auth hook
        """
        if self.post_callback_auth_hooks is None:
            self.post_callback_auth_hooks = []
        self.post_callback_auth_hooks.append(hook)

    def get_validation_hooks(self) -> Tuple[List[Callable], List[Callable]]:
        """
        Returns the validation hooks
        """
        return self.pre_validate_hooks.copy(), self.post_validate_hooks.copy()

    async def run_pre_validate_hooks(self, request: 'Request'):
        """
        Runs the pre-validate hooks
        """
        for hook in self.pre_validate_hooks:
            await ThreadPooler.asyncish(hook, request)

    async def run_post_validate_hooks(self, request: 'Request', client: 'KindeClient'):
        """
        Runs the post-validate hooks
        """
        for hook in self.post_validate_hooks:
            await ThreadPooler.asyncish(hook, request, client)

    async def run_post_validate_auth_hooks(self, request: 'Request', client: 'KindeClient'):
        """
        Runs the post-validate auth hooks
        """
        for hook in self.post_validate_auth_hooks:
            await ThreadPooler.asyncish(hook, request, client)

    async def run_post_callback_auth_hooks(self, request: 'Request', client: 'KindeClient'):
        """
        Runs the post-callback auth hooks
        """
        for hook in self.post_callback_auth_hooks:
            await ThreadPooler.asyncish(hook, request, client)


KindeContext: KindeContextObject = ProxyObject(
    KindeContextObject,
)


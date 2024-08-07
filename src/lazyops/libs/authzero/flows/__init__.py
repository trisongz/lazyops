from typing import TYPE_CHECKING, Union, Type

if TYPE_CHECKING:
    from .admin import AZManagementClient, AZManagementAPI
    from .api_keys import APIKeyDataFlow
    from .tokens import ClientCredentialsFlow, APIClientCredentialsFlow
    from .user_data import UserDataFlow
    from .user_session import UserSessionFlow

    AZFlow = Union[
        APIClientCredentialsFlow,
        APIKeyDataFlow,
        ClientCredentialsFlow,
        UserDataFlow,
        UserSessionFlow,
    ]

    AZFlowSchema = Type[
        Union[
            APIClientCredentialsFlow,
            APIKeyDataFlow,
            AZManagementAPI,
            ClientCredentialsFlow,
            UserDataFlow,
            UserSessionFlow,
        ]
    ]

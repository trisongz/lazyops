from typing import TYPE_CHECKING, Union, Type

if TYPE_CHECKING:
    from .admin import AZManagementClient, AZManagementAPI
    from .tokens import ClientCredentialsFlow, APIClientCredentialsFlow
    from .user_data import UserDataFlow
    from .user_session import UserSessionFlow

    AZFlow = Union[
        ClientCredentialsFlow,
        APIClientCredentialsFlow,
        UserDataFlow,
        UserSessionFlow,
    ]

    AZFlowSchema = Type[
        Union[
            AZManagementAPI,
            ClientCredentialsFlow,
            APIClientCredentialsFlow,
            UserDataFlow,
            UserSessionFlow,
        ]
    ]

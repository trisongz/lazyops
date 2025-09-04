from __future__ import annotations

import typing as t
from fastapi import HTTPException
from lzl.types import eproperty
from lzl.logging import logger
from lzl.api import aiohttpx
from pydantic.alias_generators import to_camel
from lzo.utils import timed_cache, Timer
from .models import (
    KeycloakUser,
    KeycloakGroup,
    KeycloakRealm,
    KeycloakClient,

    KeycloakWebhookCreate, 
    KeycloakWebhookObject
)

if t.TYPE_CHECKING:
    from .config import KeycloakSettings


_RealmToClients = {}


class KeycloakManager:
    def __init__(
        self, 
        url: t.Optional[str] = None, 
        client_id: t.Optional[str] = None, 
        username: t.Optional[str] = None, 
        password: t.Optional[str] = None,
        settings: t.Optional[KeycloakSettings] = None,
    ):
        """
        Initialize the KeycloakTokenManager.

        :param url: Keycloak server URL.
        :param client_id: Client ID for Keycloak.
        :param username: Username for Keycloak.
        :param password: Password for Keycloak.
        :param settings: Keycloak settings.
        """
        self._extra: t.Dict[str, t.Any] = {}
        if settings is None:
            from lzl.api.keycloak.registry import get_keycloak_settings
            settings = get_keycloak_settings()
        self.settings = settings
        self.url = url or self.settings.url
        self.master_realm = 'master'  # Always use master realm for token
        self.client_id = client_id or self.settings.client_id
        self.username = username or self.settings.username
        self.password = password or self.settings.password
        self._refresh_int = self.settings.refresh_realms_interval
        self._ts = Timer()
        self._index: t.Dict[str, t.List[KeycloakClient]] = {}

    @eproperty
    def token_url(self) -> str:
        """
        Returns the Keycloak token URL.
        """
        return f"{self.url}/realms/{self.master_realm}/protocol/openid-connect/token"

    @eproperty
    def api(self) -> aiohttpx.Client:
        """
        Returns the Keycloak API client.
        """
        from .auth import KeycloakAuth
        return aiohttpx.Client(
            base_url=self.url,
            auth=KeycloakAuth(self),
            preset_config='polling',
            follow_redirects=True,
            headers={
                'Content-Type': 'application/json',
            }
        )
    
    def _should_refresh_realms(self) -> bool:
        """
        Determines if the realms should be refreshed.
        This is a simple cache to avoid hitting Keycloak too often.
        """
        if self._ts.elapsed > self._refresh_int:
            logger.info(f"Refreshing Realms: {self._ts.elapsed} > {self._refresh_int}")
            self._ts = Timer()
            return True
        return False
        

    async def _apopulate_realms(self, realms: t.Optional[t.List[KeycloakRealm]] = None):
        """
        Populate the keycloak realms and realm clients
        """
        # logger.info("Populating Keycloak realms and clients")
        realms = realms or await self.get_realms()
        for realm in realms:
            self._index[realm.name] = await self.get_realm_clients(realm=realm.name, exclude_defaults=True)


    async def _adetermine_realm(self, realm: t.Optional[str] = None, client_id: t.Optional[str] = None) -> str:
        """
        Determines the realm
        """
        if realm: return realm
        if client_id:
            for r, clients in _RealmToClients.items():
                if client_id in clients:
                    return r

            if not self._index or self._should_refresh_realms(): await self._apopulate_realms()
            for r, clients in self._index.items():
                for c in clients:
                    if c.client_id == client_id or c.id == client_id or c.name == client_id:
                        return r
        raise ValueError(f"Unable to determine realm: {self._index} {client_id} {realm}")
    

    def _populate_realms(self, realms: t.Optional[t.List[KeycloakRealm]] = None):
        """
        Populate the keycloak realms
        """
        realms = realms or  self._get_realms()
        for realm in realms:
            self._index[realm.name] = self._get_realm_clients(realm=realm.name, exclude_defaults=True)
        
    
    def _determine_realm(self, realm: t.Optional[str] = None, client_id: t.Optional[str] = None) -> str:
        """
        Determines the realm
        """
        if realm: return realm
        if client_id:
            for r, clients in _RealmToClients.items():
                if client_id in clients:
                    return r
            if not self._index or self._should_refresh_realms(): self._populate_realms()
            for r, clients in self._index.items():
                for c in clients:
                    if c.client_id == client_id or c.id == client_id or c.name == client_id:
                        return r
        raise ValueError("Unable to determine realm")

    """
    User Methods
    """
    @t.overload
    async def list_users(
        self, 
        realm: t.Optional[str] = None, 
        client_id: t.Optional[str] = None, 
        email: t.Optional[str] = None,
        email_verified: t.Optional[bool] = None,
        enabled: t.Optional[bool] = None,
        exact: t.Optional[bool] = None,
        first: t.Optional[int] = None,
        username: t.Optional[str] = None,
        search: t.Optional[str] = None,
        q: t.Optional[str] = None,
        **kwargs
    ) -> t.List[KeycloakUser]:
        """
        List users in a Keycloak realm.

        :param realm: The realm to list users from.
        :param client_id: The client ID to list users for.
        :param email: The email address to filter users by.
        :param email_verified: Whether to filter users by email verification status.
        :param enabled: Whether to filter users by enabled status.
        :param exact: Whether to perform an exact match search.
        :param first: The index of the first user to return (for pagination).
        :param username: The username to filter users by.
        :param search: A search term to filter users by.
        :param q: A query string to filter users by.
        :param kwargs: Additional query parameters for filtering users.
        :return: A list of KeycloakUser objects.
        """
        ...

    async def list_users(self, realm: t.Optional[str] = None, client_id: t.Optional[str] = None, **kwargs) -> t.List[KeycloakUser]:
        """
        List users in a Keycloak realm.

        :param realm: The realm to list users from.
        :param client_id: The client ID to list users for.
        :param kwargs: Additional query parameters for filtering users.
        :return: A list of KeycloakUser objects.
        """
        realm = await self._adetermine_realm(realm, client_id)
        url_path = f"/admin/realms/{realm}/users"
        kwargs = {
            to_camel(k): v for k, v in kwargs.items() if v is not None
        }
        response = await self.api.aget(url_path, params=kwargs)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch users from Keycloak: {response.text}")
        return [KeycloakUser.model_validate(u, context={'realm': realm}) for u in response.json()]


    async def get_user(self, user_id: t.Optional[str] = None, username: t.Optional[str] = None, email: t.Optional[str] = None, realm: t.Optional[str] = None, client_id: t.Optional[str] = None) -> KeycloakUser:
        """
        Fetch a Keycloak user by their ID, username, or email.

        :param user_id: The ID of the user to fetch.
        :param username: The username of the user to fetch.
        :param email: The email of the user to fetch.
        :param realm: The realm to fetch the user from.
        :param client_id: The client ID to determine the realm.
        :return: A KeycloakUser object.
        """
        realm = await self._adetermine_realm(realm, client_id)
        if not user_id:
            users = await self.list_users(realm=realm, username=username, email=email)
            if not users: raise HTTPException(status_code=404, detail="User not found")
            if len(users) > 1: raise HTTPException(status_code=400, detail="Multiple users found")
            user = users[0]
            user_id = user.id
        response = await self.api.aget(f"/admin/realms/{realm}/users/{user_id}")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch user from Keycloak: {response.text}")
        return KeycloakUser.model_validate_json(response.text, context = {'realm': realm})


    async def update_user(self, user: 'KeycloakUser', realm: t.Optional[str] = None, client_id: t.Optional[str] = None) -> None:
        """
        Update a Keycloak user.

        :param user: The KeycloakUser object to update.
        :param realm: The realm to update the user in.
        :param client_id: The client ID to determine the realm.
        :return: None
        """
        realm = await self._adetermine_realm(realm or user.realm, client_id)
        url_path = f"/admin/realms/{realm}/users/{user.id}"
        user_data = user.model_dump(mode='json', by_alias=True)
        response = await self.api.aput(url_path, json=user_data)
        if response.status_code != 204:
            raise HTTPException(status_code=500, detail=f"Failed to update user in Keycloak: {response.text}")
        logger.info(f"User {user.id} updated successfully in Keycloak.")


    async def get_user_email(self, user_id: t.Optional[str] = None, username: t.Optional[str] = None, realm: t.Optional[str] = None, client_id: t.Optional[str] = None) -> str:
        """
        Fetch the email address of a user from Keycloak using their user ID or username.

        :param user_id: The ID of the user.
        :param username: The username of the user.
        :param realm: The realm to fetch the user from.
        :param client_id: The client ID to determine the realm.
        :return: The email address of the user.
        """
        user = await self.get_user(user_id=user_id, username=username, realm=realm, client_id=client_id)
        return user.email


    
    async def get_user_groups(self, user_id: str, realm: t.Optional[str] = None, client_id: t.Optional[str] = None) -> t.List[KeycloakGroup]:
        """
        Fetch the groups for a Keycloak user by their ID.
        
        :param user_id: The ID of the user.
        :param realm: The realm to fetch the user groups from.
        :param client_id: The client ID to determine the realm.
        :return: A list of KeycloakGroup objects.
        """
        realm = await self._adetermine_realm(realm, client_id)
        url_path = f"{self.url}/admin/realms/{realm}/users/{user_id}/groups"
        response = await self.api.aget(url_path)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch user groups from Keycloak: {response.text}")
        return [KeycloakGroup.model_validate(g, context={'realm': realm}) for g in response.json()]

    @t.overload
    async def get_user_group_names(
        self,
        user_id: str,
        realm: t.Optional[str] = None,
        client_id: t.Optional[str] = None
    ) -> t.List[str]:
        """
        Fetch the list of group names for a user from Keycloak Admin API.
        
        :param user_id: The ID of the user.
        :param realm: The realm to fetch the user groups from.
        :param client_id: The client ID to determine the realm.
        :return: A list of group names (strings).
        """
        ...

    async def get_user_group_names(self, user_id: str, realm: t.Optional[str] = None, client_id: t.Optional[str] = None) -> t.List[str]:
        """
        Fetch the list of group names for a user from Keycloak Admin API.
        Returns a list of group names (strings).
        """
        groups = await self.get_user_groups(user_id, realm, client_id)
        return [group.name for group in groups]
    
    """
    Realm Operations
    """

    def _get_realms(self, **kwargs) -> t.List[KeycloakRealm]:
        """
        Retrieves all realms from Keycloak.
        """
        response = self.api.get("/admin/realms")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch realms from Keycloak: {response.text}")
        return [KeycloakRealm.model_validate(r) for r in response.json()]

    async def get_realms(self, brief_representation: t.Optional[bool] = None, **kwargs) -> t.List[KeycloakRealm]:
        """
        Retrieves all realms from Keycloak.
                
        :param brief_representation: Whether to return a brief representation of the realms.
        :param kwargs: Additional query parameters.
        :return: A list of KeycloakRealm objects.
        """
        response = await self.api.aget("/admin/realms")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch realms from Keycloak: {response.text}")
        return [KeycloakRealm.model_validate(r) for r in response.json()]
    

    def _get_realm_clients(
        self,
        realm: str,
        exclude_defaults: t.Optional[bool] = True,
        **kwargs,
    ) -> t.List[KeycloakClient]:
        """
        Returns all the clients that belong to this realm.
        """
        response = self.api.get(f"/admin/realms/{realm}/clients")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch clients from Keycloak: {response.text}")
        clients = [KeycloakClient.model_validate(c) for c in response.json()]
        if exclude_defaults: clients = [c for c in clients if not c.is_default_client_id]
        return clients

    @t.overload
    async def get_realm_clients(
        self,
        realm: str,
        exclude_defaults: t.Optional[bool] = True,
        client_id: t.Optional[str] = None,
        first: t.Optional[int] = None,
        max: t.Optional[int] = None,
        search: t.Optional[bool] = None,
        viewable_only: t.Optional[bool] = None,
        **kwargs
    ) -> t.List[KeycloakClient]:
        """
        Returns all the clients that belong to this realm.
        
        :param realm: The realm to fetch clients from.
        :param exclude_defaults: Whether to exclude default clients.
        :param client_id: Filter by client ID.
        :param first: The first result to return (for pagination).
        :param max: The maximum number of results to return.
        :param search: Whether to search.
        :param viewable_only: Whether to return only viewable clients.
        :param kwargs: Additional query parameters.
        :return: A list of KeycloakClient objects.
        """
        ...

    async def get_realm_clients(
        self,
        realm: str,
        exclude_defaults: t.Optional[bool] = True,
        **kwargs,
    ) -> t.List[KeycloakClient]:
        """
        Returns all the clients that belong to this realm.
        """
        kwargs = {
            to_camel(k): v for k, v in kwargs.items() if v is not None
        }
        response = await self.api.aget(f"/admin/realms/{realm}/clients", params=kwargs)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch clients from Keycloak: {response.text}")
        # data = response.json()
        # logger.info(data)
        clients = [KeycloakClient.model_validate(c) for c in response.json()]
        if exclude_defaults:
            clients = [c for c in clients if not c.is_default_client_id]
        return clients
        
    """
    Webhook Operations
    """


    async def get_webhooks(self, realm: t.Optional[str] = None, client_id: t.Optional[str] = None) -> t.List[KeycloakWebhookObject]:
        """
        Fetch all webhooks from Keycloak.
        
        :param realm: The realm to fetch webhooks from.
        :param client_id: The client ID to determine the realm.
        :return: A list of KeycloakWebhookObject.
        """
        realm = await self._adetermine_realm(realm, client_id)
        url_path = f"/realms/{realm}/webhooks"
        response = await self.api.aget(url_path)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch webhooks from Keycloak: {response.text}")
        return [KeycloakWebhookObject.model_validate(w) for w in response.json()]

    async def get_webhook_id(
        self,
        url: t.Optional[str] = None,
        webhook_id: t.Optional[str] = None,
        realm: t.Optional[str] = None,
        client_id: t.Optional[str] = None
    ) -> str:
        """
        Fetch the ID of a webhook by its URL or ID.
        
        :param url: The URL of the webhook.
        :param webhook_id: The ID of the webhook.
        :param realm: The realm to search in.
        :param client_id: The client ID to determine the realm.
        :return: The webhook ID.
        """
        if webhook_id: return webhook_id
        if url:
            realm = await self._adetermine_realm(realm, client_id)
            webhooks = await self.get_webhooks(realm=realm, client_id=client_id)
            for webhook in webhooks:
                if webhook.url == url:
                    return webhook.id
            raise HTTPException(status_code=404, detail=f"Webhook with URL {url} not found.")
        raise ValueError("Either 'url' or 'webhook_id' must be provided to get a webhook ID.")

    async def get_webhook(
        self,
        url: t.Optional[str] = None,
        webhook_id: t.Optional[str] = None,
        realm: t.Optional[str] = None,
        client_id: t.Optional[str] = None,
        **kwargs,
    ) -> KeycloakWebhookObject:
        """
        Fetch an existing webhook.
        
        :param url: The URL of the webhook to fetch.
        :param webhook_id: The ID of the webhook to fetch.
        :param realm: The realm to fetch the webhook from.
        :param client_id: The client ID to determine the realm.
        :param kwargs: Additional parameters.
        :return: A KeycloakWebhookObject.
        """
        realm = await self._adetermine_realm(realm, client_id)
        webhook_id = await self.get_webhook_id(url=url, webhook_id=webhook_id, realm=realm, client_id=client_id)
        url_path = f"/realms/{realm}/webhooks/{webhook_id}"
        response = await self.api.aget(url_path)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to fetch webhook from Keycloak: {response.text}")
        return KeycloakWebhookObject.model_validate(response.json())

    @t.overload
    async def create_webhook(
        self,
        url: str,
        enabled: t.Optional[bool] = True,
        events: t.Optional[t.List[str]] = None,
        secret: t.Optional[str] = None,
        realm: t.Optional[str] = None,
        client_id: t.Optional[str] = None,
        **kwargs,
    ) -> KeycloakWebhookObject:
        """
        Create a Keycloak webhook.

        :param url: The URL to send the webhook events to.
        :param enabled: Whether the webhook is enabled.
        :param events: List of events to subscribe to.
        :param secret: Optional secret for the webhook.
        :param realm: The realm to create the webhook in.
        :param client_id: The client ID to create the webhook for.
        """
        ...


    async def create_webhook(
        self,
        url: str,
        overwrite: t.Optional[bool] = False,
        realm: t.Optional[str] = None,
        client_id: t.Optional[str] = None,
        **kwargs,
    ) -> KeycloakWebhookObject:
        """
        Create a Keycloak webhook.

        :param url: The URL to send the webhook events to.
        :param enabled: Whether the webhook is enabled.
        :param events: List of events to subscribe to.
        :param secret: Optional secret for the webhook.
        :param realm: The realm to create the webhook in.
        :param client_id: The client ID to create the webhook for.
        """
        # We'll check if the webhook already exists
        realm = await self._adetermine_realm(realm, client_id)
        if not overwrite:
            webhooks = await self.get_webhooks(realm=realm, client_id=client_id)
            for webhook in webhooks:
                if webhook.url == url:
                    logger.info(f"Webhook already exists: {webhook.id} in realm |y|{realm}|e| for url: {url}")
                    return webhook
        kwargs['url'] = url
        data_object = KeycloakWebhookCreate.model_validate(kwargs)
        data = data_object.model_dump(mode='json', by_alias=True, exclude_none=True)
        url_path = f"/realms/{realm}/webhooks"
        response = await self.api.apost(url_path, json=data)
        if response.status_code != 201:
            raise HTTPException(status_code=500, detail=f"Failed to create webhook in Keycloak: {response.text} for {url} in {realm}")
        return await self.get_webhook(url=url, realm=realm, client_id=client_id)
        

    @t.overload
    async def update_webhook(
        self,
        url: t.Optional[str] = None,
        webhook_id: t.Optional[str] = None,
        enabled: t.Optional[bool] = None,
        events: t.Optional[t.List[str]] = None,
        secret: t.Optional[str] = None,
        realm: t.Optional[str] = None,
        client_id: t.Optional[str] = None,
        **kwargs
    ) -> KeycloakWebhookObject:
        """
        Update an existing webhook.
        
        :param url: The URL to send the webhook events to.
        :param webhook_id: The ID of the webhook to update.
        :param enabled: Whether the webhook is enabled.
        :param events: List of events to subscribe to.
        :param secret: Optional secret for the webhook.
        :param realm: The realm to update the webhook in.
        :param client_id: The client ID to determine the realm.
        :param kwargs: Additional parameters.
        :return: The updated KeycloakWebhookObject.
        """
        ...

    async def update_webhook(
        self,   
        url: t.Optional[str] = None,
        webhook_id: t.Optional[str] = None,
        realm: t.Optional[str] = None,
        client_id: t.Optional[str] = None,
        **kwargs,
    ) -> KeycloakWebhookObject:
        """
        Update an existing webhook

        :param url: The URL to send the webhook events to.
        :param webhook_id: The ID of the webhook to update.
        :param enabled: Whether the webhook is enabled.
        :param events: List of events to subscribe to.
        :param secret: Optional secret for the webhook.
        :param realm: The realm to update the webhook in.
        :param client_id: The client ID to determine the realm.
        :param kwargs: Additional parameters.
        :return: The updated KeycloakWebhookObject.
        """
        if not url and not webhook_id:
            raise ValueError("Either 'url' or 'webhook_id' must be provided to update a webhook.")
        realm = await self._adetermine_realm(realm, client_id)
        webhook_id = await self.get_webhook_id(url=url, webhook_id=webhook_id, realm=realm, client_id=client_id)
        url_path = f"/realms/{realm}/webhooks/{webhook_id}"
        kwargs['url'] = url
        data_object = KeycloakWebhookCreate.model_validate(kwargs)
        data = data_object.model_dump(mode='json', by_alias=True, exclude_none=True)
        response = await self.api.aput(url_path, json=data)
        if response.status_code != 204:
            raise HTTPException(status_code=500, detail=f"Failed to update webhook in Keycloak: {response.text}")
        return await self.get_webhook(url=url, realm=realm, client_id=client_id)
    

    async def delete_webhook(
        self,
        url: t.Optional[str] = None,
        webhook_id: t.Optional[str] = None,
        realm: t.Optional[str] = None,
        client_id: t.Optional[str] = None,
    ) -> t.Dict[str, str]:
        """
        Delete a Keycloak webhook.

        :param url: The URL of the webhook to delete.
        :param webhook_id: The ID of the webhook to delete.
        :param realm: The realm to delete the webhook from.
        :param client_id: The client ID to delete the webhook for.
        :return: A dictionary with a success message.
        """
        realm = await self._adetermine_realm(realm, client_id)
        webhook_id = await self.get_webhook_id(url=url, webhook_id=webhook_id, realm=realm, client_id=client_id)
        url_path = f"/realms/{realm}/webhooks/{webhook_id}"
        response = await self.api.adelete(url_path)
        if response.status_code != 204:
            raise HTTPException(status_code=500, detail=f"Failed to delete webhook in Keycloak: {response.text}")
        return {"detail": "Webhook deleted successfully"}


    async def _clear_all_webhooks(self, realm: t.Optional[str] = None, client_id: t.Optional[str] = None) -> None:
        """
        Delete all existing webhooks
        """
        realm = await self._adetermine_realm(realm, client_id)
        webhooks = await self.get_webhooks(realm=realm, client_id=client_id)
        for webhook in webhooks:
            await self.delete_webhook(webhook_id=webhook.id)

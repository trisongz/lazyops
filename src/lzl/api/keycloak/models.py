from __future__ import annotations

import fnmatch
import datetime
import typing as t
import json
from fastapi import HTTPException
from lzo.types import BaseModel, eproperty, Field
from lzl.logging import logger
from pydantic import PrivateAttr, model_validator, field_validator, AliasChoices, field_serializer, ConfigDict, AliasGenerator
from pydantic.alias_generators import to_camel, to_snake
from pydantic import ValidationInfo

def validation_gen(field: str) -> AliasChoices:
    """
    Generate validation aliases for a field.
    """
    return AliasChoices(to_camel(field), field)

default_alias_gen = AliasGenerator(
    validation_alias=validation_gen,
    serialization_alias=to_camel,
)

_DefaultKeycloakClientIds = [
    'account',
    'account-console',
    'admin-cli',
    'admin-portal',
    'broker',
    'idp-wizard',
    'realm-management',
    'security-admin-console'
]

_ValidEventTypes = {
    "LOGIN",
    "LOGOUT",
    "USER_INFO_REQUEST",
}

class BaseKCModel(BaseModel):
    """
    Base Keycloak Model
    """
    # The other stuff we don't really care about
    model_config = ConfigDict(
        extra = "allow",
        arbitrary_types_allowed=True,
        alias_generator=default_alias_gen,
        serialize_by_alias=True,
    )


class KeycloakRealm(BaseKCModel):
    """
    Represents a Keycloak realm.
    """
    id: str
    realm: str
    display_name: str = Field(...)

    @eproperty
    def name(self) -> str:
        """
        Returns the realm name
        """
        return self.realm


class ProtocolMapperItem(BaseKCModel):
    id: str
    name: t.Optional[str] = Field(None)
    protocol: t.Optional[str] = Field(None)
    protocol_mapper: t.Optional[str] = Field(None)
    consent_required: t.Optional[bool] = Field(None)
    config: t.Dict[str, t.Any] = Field(default_factory=dict)


class KeycloakClient(BaseKCModel):
    """
    Represents a Keycloak client.
    """
    id: str
    client_id: str = Field(...)
    name: str = Field(...)
    root_url: t.Optional[str] = Field(None)
    base_url: t.Optional[str] = Field(None)

    admin_url: t.Optional[str] = Field(None)
    enabled: t.Optional[bool] = Field(default=True)
    
    client_authenticator_type: t.Optional[str] = Field(None)
    secret: t.Optional[str] = Field(None)

    web_origins: t.List[str] = Field(default_factory=list)
    redirect_uris: t.List[str] = Field(default_factory=list)

    protocol: t.Optional[str] = Field(None)
    attributes: t.Optional[t.Dict[str, t.Any]] = Field(default_factory=dict)
    protocol_mappers: t.List[ProtocolMapperItem] = Field(default_factory=list)
    default_client_scopes: t.List[str] = Field(default_factory=list)
    optional_client_scopes: t.List[str] = Field(default_factory=list)
    access: t.Optional[t.Dict[str, bool]] = Field(default_factory=dict)


    @eproperty
    def is_default_client_id(self) -> bool:
        """
        Checks if the client ID is a default Keycloak client ID.
        """
        return self.client_id in _DefaultKeycloakClientIds


class KeycloakUser(BaseKCModel):
    """
    Represents a Keycloak user.
    """
    id: str
    username: str
    first_name: t.Optional[str] = Field(None)
    last_name: t.Optional[str] = Field(None)
    email: t.Optional[str] = None
    email_verified: bool = Field(default=False)
    enabled: bool = Field(default=True)
    created_timestamp: t.Optional[int] = Field(None)
    totp: bool = Field(default=False)
    disableable_credential_types: t.List[str] = Field(default_factory=list)
    required_actions: t.List[str] = Field(default_factory=list)
    not_before: int = Field(default=0)
    access: t.Optional[t.Dict[str, t.Any]] = None
    attributes: t.Optional[t.Dict[str, t.List[str] | t.Dict[str, str]]] = Field(default_factory=dict, validation_alias=AliasChoices("attributes", "userAttributes", "user_attributes"))

    @field_validator("attributes", mode='before')
    def validate_attributes(cls, v: t.Optional[t.Dict[str, t.List[str] | t.Dict[str, str]]]) -> t.Optional[t.Dict[str, t.List[str] | t.Dict[str, str]]]:
        """
        Validate the attributes field to ensure it is a dictionary.
        """
        if v is None: return {}
        for key in {'userdata', 'appdata', 'sparkdata'}:
            if v.get(key):
                try:
                    v[key] = json.loads(v[key][0] if isinstance(v[key], list) else v[key])
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON format for {key} in attributes: {e}")
                    raise HTTPException(status_code=400, detail=f"Invalid JSON format for {key} in attributes.") from e
        return v


    @field_serializer("attributes", when_used='json')
    def serialize_attributes(self, v: t.Optional[t.Dict[str, t.List[str] | t.Dict[str, str]]]) -> t.Optional[t.Dict[str, t.List[str] | t.Dict[str, str]]]:
        """
        Serialize the attributes field to ensure it is a dictionary.
        """
        if v is None: return {}
        for key in {'userdata', 'appdata', 'sparkdata', 'orgdata', 'litellmdata', 'kcdata'}:
            if isinstance(v.get(key), dict):
                v[key] = [json.dumps(v[key])]
            elif isinstance(v.get(key), list):
                v[key] = [json.dumps(item) for item in v[key] if isinstance(item, dict)]
        return v

    @model_validator(mode='after')
    def validate_user(self, info: ValidationInfo) -> KeycloakUser:
        """
        Validate the Keycloak user model after initial validation.
        """
        if info.context and 'realm' in info.context:
            self._extra['realm'] = info.context['realm']
        return self

    @eproperty
    def created_at(self) -> t.Optional[datetime.datetime]:
        """
        Returns the creation timestamp as a datetime object.

        >>> 1755145228090 -> datetime.datetime(2024, 5, 12, 10, 20, 28, 90)
        """
        if self.created_timestamp is None: return None
        return datetime.datetime.fromtimestamp(self.created_timestamp / 1000.0)

    @eproperty
    def appdata(self) -> t.Dict[str, t.Any]:
        """
        Returns the appdata attribute as a dictionary.
        """
        if 'appdata' not in self.attributes:
            self.attributes['appdata'] = {}
        return self.attributes['appdata']
    
    @eproperty
    def userdata(self) -> t.Dict[str, t.Any]:
        """
        Returns the userdata attribute as a dictionary.
        """
        if 'userdata' not in self.attributes:
            self.attributes['userdata'] = {}
        return self.attributes['userdata']

    @eproperty
    def sparkdata(self) -> t.Dict[str, t.Any]:
        """
        Returns the sparkdata attribute as a dictionary.
        """
        if 'sparkdata' not in self.attributes:
            self.attributes['sparkdata'] = {}
        return self.attributes['sparkdata']
    
    @eproperty
    def orgdata(self) -> t.Dict[str, t.Any]:
        """
        Returns the orgdata attribute as a dictionary.
        """
        if 'orgdata' not in self.attributes:
            self.attributes['orgdata'] = {}
        return self.attributes['orgdata']
    
    @eproperty
    def litellmdata(self) -> t.Dict[str, t.Any]:
        """
        Returns the litellmdata attribute as a dictionary.
        """
        if 'litellmdata' not in self.attributes:
            self.attributes['litellmdata'] = {}
        return self.attributes['litellmdata']
    
    @eproperty
    def kcdata(self) -> t.Dict[str, t.Any]:
        """
        Returns the kcdata attribute as a dictionary.
        """
        if 'kcdata' not in self.attributes:
            self.attributes['kcdata'] = {}
        return self.attributes['kcdata']

    @eproperty
    def realm(self) -> str:
        """
        Returns the realm of the user.
        """
        return self._extra.get('realm')


class KeycloakGroup(BaseKCModel):
    """
    Represents a Keycloak group.
    """
    id: str
    name: str
    description: t.Optional[str] = None
    path: str
    sub_groups: t.List[KeycloakGroup] = Field(default_factory=list)
    # access: t.Optional[t.Dict[str, t.Any]] = None

    @model_validator(mode='after')
    def validate_group(self, info: ValidationInfo) -> KeycloakGroup:
        """
        Validate the Keycloak group model after initial validation.
        """
        if info.context and 'realm' in info.context:
            self._extra['realm'] = info.context['realm']
        return self


class KeycloakWebhookCreate(BaseKCModel):
    """ 
    Represents a Keycloak webhook creation request.
    """
    url: str = Field(..., description="The URL to which the webhook will send events")
    enabled: bool = Field(default=True, description="Whether the webhook is enabled")
    secret: t.Optional[str] = Field(None, description="The secret for the webhook")
    event_types: t.List[str] = Field(default=["*"], description="List of event types for the webhook")


class KeycloakWebhookObject(BaseKCModel):
    """
    Represents a Keycloak webhook object.
    """
    id: t.Optional[str] = Field(None, description="The ID of the webhook object")
    enabled: bool = Field(default=True, description="Whether the webhook object is enabled")
    url: str = Field(..., description="The URL of the webhook object")
    secret: t.Optional[str] = Field(None, description="The secret for the webhook object")
    event_types: t.List[str] = Field(default_factory=list, description="List of event types for the webhook object")
    created_by: t.Optional[str] = Field(None, description="The user id who created the webhook object")
    created_at: t.Optional[datetime.datetime] = Field(None, description="The creation date of the webhook object")


class AuthDetails(BaseKCModel):
    realm_id: str = Field(..., description="The ID of the realm")
    client_id: str = Field(..., description="The ID of the client")
    user_id: str = Field(..., description="The ID of the user")
    ip_address: str = Field(..., description="The IP address of the user")
    username: str = Field(..., description="The username of the user")
    session_id: str = Field(..., description="The ID of the session")

# Valid Schema for access.CODE_TO_TOKEN, access.LOGIN

class AccessWebhookEvent(BaseKCModel):
    id: str = Field(..., description="The ID of the webhook event")
    time: int = Field(..., description="The time of the webhook event")
    realm_id: str = Field(..., description="The ID of the realm")
    realm_name: str = Field(..., description="The name of the realm")
    uid: str = Field(..., description="The user ID")
    auth_details: AuthDetails = Field(..., description="The authentication details")
    details: t.Dict[str, t.Any] = Field(..., description="The event details")
    type: str = Field(..., description="The event type")
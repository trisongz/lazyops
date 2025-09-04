from __future__ import annotations

import typing as t
from lzl.types import eproperty
from pydantic import PrivateAttr, model_validator, field_validator, Field, Json, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from lzl.io import File


class KeycloakSettings(BaseSettings):

    url: t.Optional[str] = Field(None, validation_alias=AliasChoices('KEYCLOAK_URL', 'KEYCLOAK_ADMIN_URL'))
    realm: t.Optional[str] = Field(None, validation_alias=AliasChoices('KEYCLOAK_REALM', 'KEYCLOAK_ADMIN_REALM'))
    client_id: t.Optional[str] = Field('admin-cli', validation_alias=AliasChoices('KEYCLOAK_CLIENT_ID', 'KEYCLOAK_ADMIN_CLIENT_ID'))
    username: t.Optional[str] = Field(None, validation_alias=AliasChoices('KEYCLOAK_USERNAME', 'KEYCLOAK_ADMIN_USERNAME'))
    password: t.Optional[str] = Field(None, validation_alias=AliasChoices('KEYCLOAK_PASSWORD', 'KEYCLOAK_ADMIN_PASSWORD'))
    refresh_realms_interval: int = Field(120.0, validation_alias=AliasChoices('KEYCLOAK_REFRESH_REALMS_INTERVAL', 'KEYCLOAK_ADMIN_REFRESH_REALMS_INTERVAL'))
    _extra: t.Dict[str, t.Any] = PrivateAttr(default_factory= dict)

    model_config = SettingsConfigDict(
        env_prefix='',
        case_sensitive=False,
        env_file='.env',
        extra='allow',
    )
    
    @eproperty
    def keycloak_bucket(self) -> File:
        """
        Get the path to the Keycloak bucket.
        """
        return self._extra.get('keycloak_bucket')
    
    @eproperty
    def instance_id(self) -> str:
        """
        Get the instance ID.
        """
        return self._extra.get('instance_id', 'default-instance')


from __future__ import annotations

"""
JWT Token Objects
"""

import time
import datetime
from jwt import PyJWKClient
from pydantic import BaseModel, Field, PrivateAttr, model_validator
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from lazyops.libs.kinde.v2.config import KindeSettings

"""
{'access_token': 'eyJhbGciOiJSUzI1NiIsImtpZCI6ImI0OmJkOmQ5OmQwOmViOjI5OjBiOjM3OmQ5OmNmOjFlOmYzOmNmOmZiOjZiOmQ5IiwidHlwIjoiSldUIn0.eyJhdWQiOltdLCJhenAiOiIzNWMzNjA3NjFiOGQ0OTc2YjY4ZWNlNTdiOTM1YzJkNCIsImV4cCI6MTcyMTg3NTU3MCwiZXh0ZXJuYWxfb3JnX2lkIjoiZ292ZXJseWFpIiwiaWF0IjoxNzIxNzg5MTY5LCJpc3MiOiJodHRwczovL2dvdmVybHktZGV2ZWxvcG1lbnQudXMua2luZGUuY29tIiwianRpIjoiZTU4MzczODQtN2ZiOS00ZWQ4LWE0ZTAtYWE2ZmVkZWU4MDgyIiwib3JnX2NvZGUiOiJvcmdfMWMzNjFlMzViM2ZhIiwib3JnX25hbWUiOiJHb3Zlcmx5IEFJIiwicGVybWlzc2lvbnMiOlsicmVhZDpvcHBvcnR1bml0aWVzOnVzX2ZlZGVyYWwiXSwicm9sZXMiOlt7ImlkIjoiMDE5MGMyZGQtYjFkOC00ZDk5LTRjODAtM2JlMTIwYTY4NGVkIiwia2V5IjoiZGVmYXVsdCIsIm5hbWUiOiJkZWZhdWx0In1dLCJzY3AiOlsib3BlbmlkIiwicHJvZmlsZSIsImVtYWlsIiwib2ZmbGluZSJdLCJzdWIiOiJrcF9jZDY1N2QyOGE3NzA0MjIyYmQ3MDE3ZmI5ODIyNzcwOSJ9.UN1Ol9UTEfL1iWDlRn4O91YIg40UfPkN2br4OHu0F6dQ5Qy2V_OHuBKGP6aTYV4yRB-KHEJ1k-8Atf5VtM_g7xKH2ny2C610ScMkDrK61BJ9hlV8IqxiUExDnzlOp5cFIKWy_xGSJEn42fc0ouxofJjTBQoN6zIFI1FoNm50rjQntd-S2sOtDGGZjEK8AM8TX-CnGhfAYdJ9K1ppEQzg0rxeHulXIsA3Od1VoVU2tUNqqv3vJ7nti5ZA2zecxrDOq7Yy2IgqQgQus3v1oi7NclK_f5ud0hVRMawDTB2mSsWzEIRULvpNnWnDM9rZHRBNhR2bI7HaYqwhYsudNWDRvA', 'expires_in': 86399, 'id_token': 'eyJhbGciOiJSUzI1NiIsImtpZCI6ImI0OmJkOmQ5OmQwOmViOjI5OjBiOjM3OmQ5OmNmOjFlOmYzOmNmOmZiOjZiOmQ5IiwidHlwIjoiSldUIn0.eyJhdF9oYXNoIjoiT2ZhRVhNd2VNOXZoeE41YmFrSDNaQSIsImF1ZCI6WyIzNWMzNjA3NjFiOGQ0OTc2YjY4ZWNlNTdiOTM1YzJkNCJdLCJhdXRoX3RpbWUiOjE3MjE3ODkxNjksImF6cCI6IjM1YzM2MDc2MWI4ZDQ5NzZiNjhlY2U1N2I5MzVjMmQ0IiwiZW1haWwiOiJkZXZvcHNAZ292ZXJseS5haSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJleHAiOjE3MjE4NzU1NzAsImZhbWlseV9uYW1lIjoiT3BzIiwiZ2l2ZW5fbmFtZSI6IkRldiIsImlhdCI6MTcyMTc4OTE3MCwiaXNzIjoiaHR0cHM6Ly9nb3Zlcmx5LWRldmVsb3BtZW50LnVzLmtpbmRlLmNvbSIsImp0aSI6IjBlZjkxMDQwLTAwYzQtNGRjYy1hMzYyLTViYjBiZTkyZmMzZiIsIm5hbWUiOiJEZXYgT3BzIiwib3JnX2NvZGVzIjpbIm9yZ18xYzM2MWUzNWIzZmEiXSwib3JnYW5pemF0aW9ucyI6W3siaWQiOiJvcmdfMWMzNjFlMzViM2ZhIiwibmFtZSI6IkdvdmVybHkgQUkifV0sInBpY3R1cmUiOiJodHRwczovL2dyYXZhdGFyLmNvbS9hdmF0YXIvYzYzMWRlMDc1NDVlMmRjYzE3MTgzN2YwZWNhMTdiOTdhYzE0MDA3OGY2NTkyN2NiYjEzMTk1N2FlNDUzZTJlNj9kPWJsYW5rXHUwMDI2c2l6ZT0yMDAiLCJyYXQiOjE3MjE3ODkxNjksInN1YiI6ImtwX2NkNjU3ZDI4YTc3MDQyMjJiZDcwMTdmYjk4MjI3NzA5IiwidXBkYXRlZF9hdCI6MS43MjEzNDgwNWUrMDl9.id0AW1X4Uf5OhAiOZrGd1i9LajcrcgN3Sdd-3_zZaHvSYmhkf3fqarQ8A8ZThzhzt-6eTe26Hjudws9eDwkGPusXghjgR4TqStti4ElpZ__00fopQJXrwRVhf84Me7a2VNk4oB5xktMW92RDyKBSXUPxQqgABMftOyP547k8OwpO9EF-my8CYpWIXdjc6yKIXNxvlHo-noa0cu1ysHuD30ueE1zNGjwus7EhLcsmqU8zgL462-NIqEwK33Q1j3MljS8k4N3kP-LTA95IYHBYgfLOJTEP-_fjRNAggZ_SbasNbVFsdtGweyPhcR7WHHv8DkYiq7wU1xhaYFXOZIDh2w', 'refresh_token': 'KrJlngIHCZ-4WD-ZXxWutzpotUygQ0f6UDHA7Am_TnY.urh-m2DsUxBtY_elQh04K5NTMjNp3G91KeZwvADUiPg', 'scope': 'openid profile email offline', 'token_type': 'bearer', 'expires_at': 1721875569}
"""

class BaseJWTObject(BaseModel):
    """
    Base JWT Object
    """

    _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)

    @property
    def settings(self) -> 'KindeSettings':
        """
        Returns the Kinde Settings
        """
        from lazyops.libs.kinde.v2.utils import get_kinde_settings
        return get_kinde_settings()


class AccessToken(BaseJWTObject):
    """
    Access Token
    """
    aud: List[str] = Field(default_factory=list, description = "The audience of the token")
    azp: str = Field(None, description = "The authorized party of the token")
    exp: int = Field(None, description = "The expiration time of the token")
    external_org_id: str = Field(None, description = "The external organization id of the token")
    iat: int = Field(None, description = "The issued at time of the token")
    iss: str = Field(None, description = "The issuer of the token")
    jti: str = Field(None, description = "The token id of the token")
    org_code: str = Field(None, description = "The organization code of the token")
    org_name: str = Field(None, description = "The organization name of the token")
    permissions: List[str] = Field(default_factory=list, description = "The permissions of the token")
    roles: List[Dict[str, str]] = Field(default_factory=list, description = "The roles of the token")
    scp: List[str] = Field(default_factory=list, description = "The scope of the token")
    sub: str = Field(None, description = "The subject of the token")


class IDToken(BaseJWTObject):
    """
    ID Token
    """
    at_hash: str = Field(None, description = "The access token hash of the token")
    aud: Optional[List[str]] = Field(default_factory=list, description = "The audience of the token")
    auth_time: int = Field(None, description = "The authentication time of the token")
    azp: str = Field(None, description = "The authorized party of the token")
    email: str = Field(None, description = "The email of the token")
    email_verified: bool = Field(None, description = "The email verified of the token")
    exp: int = Field(None, description = "The expiration time of the token")
    family_name: Optional[str] = Field(None, description = "The family name of the token")
    given_name: Optional[str] = Field(None, description = "The given name of the token")
    iat: int = Field(None, description = "The issued at time of the token")
    iss: str = Field(None, description = "The issuer of the token")
    jti: str = Field(None, description = "The token id of the token")
    name: Optional[str] = Field(None, description = "The name of the token")
    org_codes: List[str] = Field(default_factory=list, description = "The organization codes of the token")
    organizations: List[Dict[str, str]] = Field(default_factory=list, description = "The organizations of the token")
    picture: Optional[str] = Field(None, description = "The picture of the token")
    rat: str = Field(None, description = "The rat of the token")
    sub: str = Field(None, description = "The subject of the token")
    updated_at: int = Field(None, description = "The updated at time of the token")

    @model_validator(mode = 'after')
    def validate_exp(self):
        """
        Validates the expiration
        """
        if self.exp is None: return
        if self.exp < time.time():
            raise ValueError(f'Token is expired. Expiration: {self.exp}')
        return self



from __future__ import annotations

"""
The Base HTTP Client for KeyCloak
"""
import time
import httpx
import asyncio
import typing as t
import threading
from fastapi import HTTPException
from lzl.logging import logger
from .registry import kv_pdict, kv_available

if t.TYPE_CHECKING:
    from .manager import KeycloakManager


class KeycloakAuth(httpx.Auth):
    def __init__(self, client: 'KeycloakManager'):
        self.c = client
        self.token = None
        self.token_expiry = 0
        self._sync_lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        if kv_available:
            self._set_from_kv()
    
    def _set_from_kv(self):
        """
        Sets the Keycloak token and expiry from the KV store.
        """
        try:
            if kv_pdict.contains('tokendata'):
                token_data: t.Dict[str, t.Any] = kv_pdict.get('tokendata')
                self.token = token_data.get('access_token')
                self.token_expiry = token_data.get('expires_at', 0)
        except Exception as e:
            logger.error(f"Failed to get Keycloak token from KV store: {e}")

    async def arefresh_token(self):
        """        
        Refresh the Keycloak token.
        """
        data = {
            "grant_type": "password",
            "client_id": self.c.client_id,
            "username": self.c.username,
            "password": self.c.password,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient(timeout = 60.0) as client:
            r = await client.post(self.c.token_url, data=data, headers=headers)
        if r.status_code != 200:
            logger.error(f"Failed to get Keycloak token: {r.text}")
            raise HTTPException(status_code=500, detail=f"Failed to get Keycloak token: {r.text}")
        token_data = r.json()
        logger.info(f"Keycloak token data: {token_data}")
        token_data['expires_at'] = time.time() + token_data.get("expires_in", 60)
        self.token = token_data["access_token"]
        self.token_expiry = token_data['expires_at']
        if kv_available: 
            logger.info("Saving Keycloak token to KV store")
            try:
                await kv_pdict.aset('tokendata', token_data, ex = (token_data.get("expires_in", 60) - 15))
            except Exception as e:
                logger.error(f"Failed to set Keycloak token in KV store: {e}")

    async def aget_token(self):
        """
        Fetch the Keycloak token, refreshing it if necessary.
        """
        async with self._async_lock:
            if self.token is None or time.time() > self.token_expiry - 30:
                logger.info(f"Refreshing Keycloak token: {time.time()} > {self.token_expiry - 30}")
                await self.arefresh_token()
        return self.token

    async def async_auth_flow(self, request: httpx.Request) -> t.AsyncIterator[httpx.Request]:
        token = await self.aget_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

    def refresh_token(self):
        """        
        Refresh the Keycloak token.
        """
        data = {
            "grant_type": "password",
            "client_id": self.c.client_id,
            "username": self.c.username,
            "password": self.c.password,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        with httpx.Client(timeout = 60.0) as client:
            r = client.post(self.c.token_url, data=data, headers=headers)
        if r.status_code != 200:
            logger.error(f"Failed to get Keycloak token: {r.text}")
            raise HTTPException(status_code=500, detail=f"Failed to get Keycloak token: {r.text}")
        token_data = r.json()
        self.token = token_data["access_token"]
        self.token_expiry = time.time() + token_data.get("expires_in", 60)
        if kv_available:
            try:
                kv_pdict.set('tokendata', token_data, ex = (token_data.get("expires_in", 60) - 30))
            except Exception as e:
                logger.error(f"Failed to set Keycloak token in KV store: {e}")

    def get_token(self):
        """
        Get the Keycloak token, refreshing it if necessary.
        """
        if self.token is None or time.time() > self.token_expiry - 30:
            self.refresh_token()
        return self.token
    
    def sync_auth_flow(self, request: httpx.Request) -> t.Iterator[httpx.Request]:
        token = self.get_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

from __future__ import annotations

"""
Web Browser Api using Playwright
"""
import asyncio
# from lazyops.libs.proxyobj import ProxyObject, proxied
from typing import Optional, Dict, Any, List, Union, Type, TYPE_CHECKING
from .base import BaseGlobalClient

if TYPE_CHECKING:
    from playwright.sync_api import PlaywrightContextManager, Playwright, Browser as SyncBrowser
    from playwright.async_api import (
        PlaywrightContextManager as AsyncPlaywrightContextManager, 
        Playwright as AsyncPlaywright,
        Browser as AsyncBrowser
    )

# @proxied
class BrowserClient(BaseGlobalClient):
    """
    The Browser Client Meta Class
    """
    initialized: bool = False
    _initializing: bool = False

    _abrowser: 'AsyncBrowser' = None
    _apw_client: 'AsyncPlaywright' = None
    _apw_context_manager: 'AsyncPlaywrightContextManager' = None

    _browser: 'SyncBrowser' = None
    _pw_client: 'Playwright' = None
    _pw_context_manager: 'PlaywrightContextManager' = None
    
    @property
    def abrowser(self) -> 'AsyncBrowser':
        """
        Returns the browser instance
        """
        if self._abrowser is None:
            raise RuntimeError('AsyncBrowser not initialized. Initialize with Browser.ainit()')
        return self._abrowser
    
    @property
    def acontext_manager(self) -> 'AsyncPlaywrightContextManager':
        """
        Returns the Playwright context manager
        """
        if self._apw_context_manager is None:
            from playwright.async_api import async_playwright
            self._apw_context_manager = async_playwright()
        return self._apw_context_manager
    
    @property
    def aclient(self) -> 'AsyncPlaywright':
        """
        Returns the Playwright instance
        """
        if self._apw_client is None:
            raise RuntimeError('AsyncPlaywright not initialized. Initialize with Browser.ainit()')
        return self._apw_client

    @property
    def browser(self) -> 'SyncBrowser':
        """
        Returns the browser instance
        """
        if self._browser is None:
            self._browser = self.client.chromium.launch(
                headless = True,
                downloads_path = self.settings.module_path.joinpath('data').as_posix()
            )
        return self._browser
    
    @property
    def context_manager(self) -> 'PlaywrightContextManager':
        """
        Returns the Playwright context manager
        """
        if self._pw_context_manager is None:
            from playwright.sync_api import sync_playwright
            self._pw_context_manager = sync_playwright()
        return self._pw_context_manager
    
    @property
    def client(self) -> 'Playwright':
        """
        Returns the Playwright instance
        """
        if self._pw_client is None:
            self._pw_client = self.context_manager.start()
        return self._pw_client
    
    def _set_apw_client(self, task: asyncio.Task):
        """
        Sets the AsyncPlaywright instance
        """
        self.logger.info('Setting AsyncPlaywright')
        self._apw_client = task.result()

    def _set_abrowser(self, task: asyncio.Task):
        """
        Sets the AsyncBrowser instance
        """
        self.logger.info('Setting AsyncBrowser')
        self._abrowser = task.result()

    async def ainit(self):
        """
        Initializes the browser
        """
        if self.initialized: return
        self.logger.info('Initializing Browser')
        self._initializing = True
        if self._apw_client is None:
            self._apw_client = await self.acontext_manager.start()
        if self._abrowser is None:
            self._abrowser = await self.aclient.chromium.launch(
                headless = True,
                downloads_path = self.settings.module_path.joinpath('data').as_posix()
            )
        self.initialized = True
        self._initializing = False
    
    def close(self):
        """
        Closes the browser
        """
        if self._abrowser:
            self.pooler.create_background(
                self._abrowser.close,
            )
            self._abrowser = None
        if self._browser:
            self._browser.close()
            self._browser = None
        
        if self._apw_client:
            self.pooler.create_background(
                self._apw_client.stop,
            )
            self._apw_client = None
        if self._pw_client:
            self._pw_client.stop()
            self._pw_client = None
        
        self._apw_context_manager = None
        self._pw_context_manager = None
        self.initialized = False



    async def aclose(self):
        """
        Closes the browser
        """
        if self._abrowser:
            await self._abrowser.close()
            self._abrowser = None
        if self._browser:
            self._browser.close()
            self._browser = None
        
        if self._apw_client:
            await self._apw_client.stop()
            self._apw_client = None
        if self._pw_client:
            self._pw_client.stop()
            self._pw_client = None
        
        self._apw_context_manager = None
        self._pw_context_manager = None
        self.initialized = False


# Browser: BrowserClient = ProxyObject(
 #    obj_cls = BrowserClient,
# )


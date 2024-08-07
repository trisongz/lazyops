from __future__ import annotations

from io import IOBase
from lazyops.types import BaseModel, Field
from lazyops.utils import logger
from typing import Optional, Dict, Any, List, Union, Sequence, Callable, TYPE_CHECKING
from .types import SlackContext, SlackPayload
from .configs import SlackSettings

if TYPE_CHECKING:
    from slack_sdk import WebClient
    from slack_sdk.web.async_client import AsyncWebClient

    from slack_sdk.models.attachments import Attachment
    from slack_sdk.models.blocks import Block

    from fastapi import APIRouter, FastAPI


class SlackClient:

    verbose: Optional[bool] = False

    if TYPE_CHECKING:
        sapi: WebClient
        api: AsyncWebClient

    def __init__(
        self,
        token: Optional[str] = None,
        default_user: Optional[str] = None,
        default_channel: Optional[str] = None,
        username_mapping: Optional[Dict[str, Union[str, List[str]]]] = None,
        verbose: Optional[bool] = None,
        **kwargs
    ):
        """
        Slack Client
        """
        from lazyops.imports._slacksdk import resolve_slack_sdk
        resolve_slack_sdk(True)

        self.settings = SlackSettings()
        self.token = token or self.settings.bot_token
        self.disabled = self.token is None
        if self.token is None:
            logger.warning("No token provided. Disabling Slack client")
            return

        self._api: Optional['AsyncWebClient'] = None
        self._sapi: Optional['WebClient'] = None
        self._kwargs: Optional[Dict[str, Any]] = kwargs
        if verbose is not None: self.verbose = verbose
        self.logger = logger
        self.default_user = default_user or self.settings.default_user
        self.default_user_id: Optional[str] = None

        self.default_channel = default_channel or self.settings.default_channel
        self.default_channel_id: Optional[str] = None
        self.ctx: SlackContext = self.settings.load_context()
        if username_mapping: 
            self.ctx.username_mapping = username_mapping
            self.settings.save_context(self.ctx)

    @property
    def api(self) -> 'AsyncWebClient':
        """
        Returns the Async API
        """
        if self._api is None and not self.disabled:
            from slack_sdk.web.async_client import AsyncWebClient
            self._api = AsyncWebClient(token = self.token, **self._kwargs)
        return self._api
    
    @property
    def sapi(self) -> 'WebClient':
        """
        Returns the Sync API
        """
        if self._sapi is None and not self.disabled:
            from slack_sdk import WebClient
            self._sapi = WebClient(token = self.token, **self._kwargs)
        return self._sapi

    def get_users(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Get users
        """
        resp = self.sapi.users_list(**kwargs)
        return resp["members"] if resp["ok"] else []

    async def aget_users(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Get users
        """
        resp = await self.api.users_list(**kwargs)
        return resp["members"] if resp["ok"] else []

    def get_channels(self, types: Optional[List[str]] = None, include_users: Optional[bool] = True, **kwargs) -> List[Dict[str, Any]]:
        """
        Get channels
        """
        if not types:  types = ['public_channel','private_channel','im','mpim']
        if types and isinstance(types, list): types = ",".join(types)
        resp = self.sapi.conversations_list(types = types, **kwargs)
        channels =  resp["channels"] if resp["ok"] else []
        if include_users:
            resp = self.sapi.users_conversations(types = types, **kwargs)
            channels += resp["channels"] if resp["ok"] else []
        return channels
    
    async def aget_channels(self, types: Optional[List[str]] = None, include_users: Optional[bool] = True, **kwargs) -> List[Dict[str, Any]]:
        """
        Get channels
        """
        if not types:  types = ['public_channel','private_channel','im','mpim']
        if types and isinstance(types, list):
            types = ",".join(types)
        resp = await self.api.conversations_list(types = types, **kwargs)
        channels =  resp["channels"] if resp["ok"] else []
        if include_users:
            resp = await self.api.users_conversations(types = types, **kwargs)
            channels += resp["channels"] if resp["ok"] else []
        return channels

    @property
    def default_id(self) -> Optional[str]:
        """
        Default ID
        """
        if self.disabled: return
        return self.default_user_id or self.default_channel_id


    def configure_defaults(self):
        """
        Configure defaults
        """
        if self.default_user:
            self.default_user_id = self.ctx.lookup_id(self.default_user)
            if self.verbose: self.logger.info(f"Default user id: {self.default_user} -> {self.default_user_id}")
        if self.default_channel:
            self.default_channel_id = self.ctx.lookup_id(self.default_channel)
            if self.verbose: self.logger.info(f"Default channel id: {self.default_channel} -> {self.default_channel_id}")
        if self.default_id and self.verbose: self.logger.info(f"Default id: {self.default_id}")

    def init(self, overwrite: Optional[bool] = False):
        """
        Initialize
        """
        # Build Channels
        if self.disabled: return
        if not overwrite and self.ctx.initialized:
            self.configure_defaults()
            return

        users = self.get_users()
        for user in users:
            if aliases := self.ctx.username_mapping.get(user['name']):
                if isinstance(aliases, str): aliases = [aliases]
                for alias in aliases:
                    self.ctx.uids[user['id']] = alias
                    self.ctx.users[alias] =  user['id']
            else:
                self.ctx.uids[user['id']] = user['name']
            self.ctx.users[user['name']] =  user['id']


        channels = self.get_channels()
        for channel in channels:
            if not channel.get('name'): 
                self.ctx.channels[self.ctx.uids[channel['user']]] = channel['id']
                self.ctx.uids[channel['id']] = self.ctx.uids[channel['user']]
            else:
                self.ctx.channels[channel['name']] = channel['id']
                self.ctx.uids[channel['id']] = channel['name']
        
        self.ctx.initialized = True
        self.configure_defaults()
        self.settings.save_context(self.ctx)

    async def ainit(self, overwrite: Optional[bool] = False):
        """
        Initialize
        """
        # Build Channels
        if self.disabled: return
        if not overwrite and self.ctx.initialized:
            self.configure_defaults()
            return

        users = await self.aget_users()
        for user in users:
            if aliases := self.ctx.username_mapping.get(user['name']):
                if isinstance(aliases, str): aliases = [aliases]
                for alias in aliases:
                    self.ctx.uids[user['id']] = alias
                    self.ctx.users[alias] =  user['id']
            else:
                self.ctx.uids[user['id']] = user['name']
            self.ctx.users[user['name']] =  user['id']


        channels = await self.aget_channels()
        for channel in channels:
            if not channel.get('name'): 
                self.ctx.channels[self.ctx.uids[channel['user']]] = channel['id']
                self.ctx.uids[channel['id']] = self.ctx.uids[channel['user']]
            else:
                self.ctx.channels[channel['name']] = channel['id']
                self.ctx.uids[channel['id']] = channel['name']
        
        self.ctx.initialized = True
        self.configure_defaults()

    def lookup(self, user_or_channel: str) -> Optional[str]:
        """
        Return the ID of a user or channel
        """
        if self.disabled: return
        if user_or_channel in [
            self.default_id,
            self.default_channel_id,
        ]:
            return user_or_channel
        return self.ctx.lookup_id(user_or_channel) or user_or_channel


    def join_channel(self, channel_id: str, **kwargs):
        """
        Join a channel
        """
        if self.disabled: return
        if self.verbose: self.logger.info(f"Joining channel {channel_id}")
        self.sapi.conversations_join(channel = channel_id, **kwargs)

    async def ajoin_channel(self, channel_id: str, **kwargs):
        """
        Join a channel
        """
        if self.disabled: return
        if self.verbose: self.logger.info(f"Joining channel {channel_id}")
        await self.api.conversations_join(channel = channel_id, **kwargs)

    def message(
        self,
        message: Optional[str] = None,
        user_or_channel: Optional[str] = None,
        channel_id: Optional[str] = None,
        **kwargs
    ):
        """
        Send a message
        """
        if self.disabled: return
        if user_or_channel:
            channel_id = self.lookup(user_or_channel)
        elif channel_id is None:
            channel_id = self.default_id
        if not self.ctx.uids.get(channel_id): self.join_channel(channel_id)
        if channel_id is None:
            raise ValueError("No channel id provided")
        return self.sapi.chat_postMessage(channel = channel_id, text = message, **kwargs)
    

    async def amessage(
        self,
        message: str,
        user_or_channel: Optional[str] = None,
        channel_id: Optional[str] = None,
        **kwargs
    ):
        """
        Send a message
        """
        if self.disabled: return
        if user_or_channel:
            channel_id = self.lookup(user_or_channel)
        elif channel_id is None:
            channel_id = self.default_id
        if not self.ctx.uids.get(channel_id): await self.ajoin_channel(channel_id)
        if channel_id is None:
            raise ValueError("No channel id provided")
        return await self.api.chat_postMessage(channel = channel_id, text = message, **kwargs)
    

    def upload_file(
        self,
        file: Optional[Union[str, bytes, IOBase]] = None,
        content: Optional[str] = None,
        filename: Optional[str] = None,
        filetype: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None,
        title: Optional[str] = None,
        channels: Optional[Union[str, Sequence[str]]] = None,
        **kwargs,
    ):
        """
        Upload a file
        """
        if self.disabled: return
        channels = channels or [self.default_id]
        if not isinstance(channels, (list, tuple)): channels = [channels]
        if channels: channels = [self.lookup(channel) for channel in channels]
        return self.sapi.files_upload_v2(
            file = file, 
            content = content, 
            filename = filename, 
            filetype = filetype, 
            initial_comment = initial_comment, 
            thread_ts = thread_ts, 
            title = title, 
            channels = channels, 
            **kwargs
        )
    
    async def aupload_file(
        self,
        file: Optional[Union[str, bytes, IOBase]] = None,
        content: Optional[str] = None,
        filename: Optional[str] = None,
        filetype: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None,
        title: Optional[str] = None,
        channels: Optional[Union[str, Sequence[str]]] = None,
        **kwargs,
    ):
        """
        Upload a file
        """
        if self.disabled: return
        channels = channels or [self.default_id]
        if not isinstance(channels, (list, tuple)): channels = [channels]
        if channels: channels = [self.lookup(channel) for channel in channels]
        return await self.api.files_upload_v2(
            file = file, 
            content = content, 
            filename = filename, 
            filetype = filetype, 
            initial_comment = initial_comment, 
            thread_ts = thread_ts, 
            title = title, 
            channels = channels, 
            **kwargs
        )
    
    def temp_message(
        self,
        text: str,
        user: str,
        channel: Optional[str] = None,
        attachments: Optional[Sequence[Union[Dict, 'Attachment']]] = None,
        blocks: Optional[Sequence[Union[Dict, 'Block']]] = None,
        **kwargs,
    ):
        """
        Send a temporary message
        """
        if self.disabled: return
        user = self.lookup(user)
        channel = self.lookup(channel) if channel else self.default_id
        return self.sapi.chat_postEphemeral(
            text = text, 
            channel = channel, 
            user = user, 
            attachments = attachments, 
            blocks = blocks,
            **kwargs
        )
    
    async def atemp_message(
        self,
        text: str,
        user: str,
        channel: Optional[str] = None,
        attachments: Optional[Sequence[Union[Dict, 'Attachment']]] = None,
        blocks: Optional[Sequence[Union[Dict, 'Block']]] = None,
        **kwargs,
    ):
        """
        Send a temporary message
        """
        if self.disabled: return
        user = self.lookup(user)
        channel = self.lookup(channel) if channel else self.default_id
        return await self.api.chat_postEphemeral(
            text = text, 
            channel = channel, 
            user = user, 
            attachments = attachments, 
            blocks = blocks,
            **kwargs
        )


    def __getitem__(self, name_or_id: str) -> 'SlackProxy':
        """
        Return the ID of a user or channel
        """
        if self.disabled: return
        return SlackProxy(name = name_or_id, uid = self.lookup(name_or_id) or name_or_id, client = self)

    def create_slash_command_endpoint(
        self,
        router: Union['APIRouter', 'FastAPI'],
        path: str,
        function: Callable,
        function_name: Optional[str] = None,
    ):
        
        function_name = function_name or function.__qualname__
        from fastapi.requests import Request

        async def slash_command(
            data: Request,
        ):
            payload = await data.form()
            return await function(SlackPayload(**payload))
        
        router.add_api_route(
            path = path,
            endpoint = slash_command,
            name = function_name,
            methods = ['POST'],
            include_in_schema=False,
        )
        return router


    # def create_interactive_endpoint(
    #     self,
    #     router: 'APIRouter',
    #     path: str,
    # ):
    #     """
    #     Create an interactive endpoint
    #     """
    #     from slack_sdk.web import WebClient
    #     from slack_bolt import App
    #     from slack_bolt.adapter.fastapi import SlackRequestHandler
    #     app = App(client = WebClient(token = self.token))
    #     handler = SlackRequestHandler(app = app)
    #     router.add_api_route(
    #         path = path,
    #         endpoint = handler,
    #         methods = ['POST'],
    #     )


class SlackProxy(BaseModel):

    name: str
    uid: str
    client: SlackClient


    def message(
        self,
        message: str,
        **kwargs
    ):
        """
        Send a message
        """
        return self.client.sapi.chat_postMessage(channel = self.uid, text = message, **kwargs)
    

    async def amessage(
        self,
        message: str,
        **kwargs
    ):
        """
        Send a message
        """
        return await self.client.api.chat_postMessage(channel = self.uid, text = message, **kwargs)
    
    def upload_file(
        self,
        file: Optional[Union[str, bytes, IOBase]] = None,
        content: Optional[str] = None,
        filename: Optional[str] = None,
        filetype: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None,
        title: Optional[str] = None,
        channels: Optional[Union[str, Sequence[str]]] = None,
        **kwargs,
    ):
        """
        Upload a file
        """
        channels = channels or [self.client.default_id]
        if not isinstance(channels, (list, tuple)): channels = [channels]
        if channels: 
            channels = [self.client.lookup(channel) for channel in channels]
        return self.client.sapi.files_upload_v2(
            file = file, 
            content = content, 
            filename = filename, 
            filetype = filetype, 
            initial_comment = initial_comment, 
            thread_ts = thread_ts, 
            title = title, 
            channels = channels, 
            **kwargs
        )
    

    async def aupload_file(
        self,
        file: Optional[Union[str, bytes, IOBase]] = None,
        content: Optional[str] = None,
        filename: Optional[str] = None,
        filetype: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None,
        title: Optional[str] = None,
        channels: Optional[Union[str, Sequence[str]]] = None,
        **kwargs,
    ):
        """
        Upload a file
        """
        channels = channels or [self.client.default_id]
        if not isinstance(channels, (list, tuple)): channels = [channels]
        if channels: 
            channels = [self.client.lookup(channel) for channel in channels]
        return await self.client.api.files_upload_v2(
            file = file, 
            content = content, 
            filename = filename, 
            filetype = filetype, 
            initial_comment = initial_comment, 
            thread_ts = thread_ts, 
            title = title, 
            channels = channels, 
            **kwargs
        )
    
    def temp_message(
        self,
        text: str,
        channel: str,
        attachments: Optional[Sequence[Union[Dict, 'Attachment']]] = None,
        blocks: Optional[Sequence[Union[Dict, 'Block']]] = None,
        **kwargs,
    ):
        """
        Send a temporary message
        """
        channel = self.client.lookup(channel)
        return self.client.sapi.chat_postEphemeral(
            text = text, 
            channel = channel, 
            user = self.uid, 
            attachments = attachments, 
            blocks = blocks,
            **kwargs
        )

    async def atemp_message(
        self,
        text: str,
        channel: str,
        attachments: Optional[Sequence[Union[Dict, 'Attachment']]] = None,
        blocks: Optional[Sequence[Union[Dict, 'Block']]] = None,
        **kwargs,
    ):
        """
        Send a temporary message
        """
        channel = self.client.lookup(channel)
        return await self.client.api.chat_postEphemeral(
            text = text, 
            channel = channel, 
            user = self.uid, 
            attachments = attachments, 
            blocks = blocks,
            **kwargs
        )


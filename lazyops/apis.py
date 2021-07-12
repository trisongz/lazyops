
import requests
import aiohttp
import asyncio

from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import List, Dict, Any, Optional

async def async_req(sess, url, decode_json=True, with_url=False, *args, **kwargs):
    async with sess.request(url, *args, **kwargs) as resp:
        data = await resp.json() if decode_json else await resp
        if not with_url:
            return data
        return {'url': url, 'data': data}


class LazySession:
    def __init__(self, header=None):
        self.header = header
        self.sess = requests.session()
        if header:
            self.sess.headers.update(header)
    
    def fetch(self, decode_json=True, *args, **kwargs):
        res = self.sess.request(*args, **kwargs)
        if decode_json:
            return res.json()
        return res
    
    async def async_batch(self, url, batch_params, decode_json=True, *args, **kwargs):
        tasks = []
        async with aiohttp.ClientSession(headers=self.header) as sess:
            for batch in batch_params:
                tasks.append(asyncio.ensure_future(async_req(sess=sess, url=url, *args, **batch, **kwargs)))
            all_tasks = await asyncio.gather(*tasks)
            return [task for task in all_tasks]
    
    async def async_fetch_urls(self, urls, decode_json=True, *args, **kwargs):
        tasks = []
        async with aiohttp.ClientSession(headers=self.header) as sess:
            for url in urls:
                tasks.append(asyncio.ensure_future(async_req(sess=sess, url=url, with_url=True, *args, **kwargs)))
            all_tasks = await asyncio.gather(*tasks)
            return [task for task in all_tasks]

    async def async_fetch(self, decode_json=True, *args, **kwargs):
        async with aiohttp.ClientSession(headers=self.header) as sess:
            async with sess.request(*args, **kwargs) as resp:
                return await resp.json() if decode_json else await resp

    def __call__(self, *args, **kwargs):
        return self.fetch(*args, **kwargs)
    
    def __exit__(self, _):
        self.sess.close()



@dataclass_json
@dataclass
class LazyRoute:
    path: str
    method: Optional[str] = 'POST'
    data_key: Optional[str] = 'inputs'
    params_key: Optional[str] = 'params'
    params: Optional[Dict[str, Any]] = None
    prefix_payload: Optional[bool] = True
    is_async: Optional[bool] = False
    decode_json: Optional[bool] = True

    def get_config(self, base_url, data=None, **config):
        p = self.params.copy() if self.params else {}
        if config:
            for k,v in config.items():
                if ((self.params and k in self.params) or not self.params) and v:
                    p[k] = v
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        if not self.path.startswith('/'):
            self.path = '/' + self.path
        pc = {self.params_key: p} if self.params_key else p
        if data: pc[self.data_key] = data
        if self.prefix_payload: pc = {'payload': pc}
        return {'method': self.method, 'url': base_url + self.path, self.pkey: pc, 'decode_json': self.decode_json}

    @property
    def pkey(self):
        if self.method in ['POST']:
            return 'json'
        if self.method in ['GET']:
            return 'params'
        return 'data'



@dataclass_json
@dataclass
class LazyHeader:
    user: Optional[str] = None
    key: Optional[str] = None
    token: Optional[str] = None
    content_type: Optional[str] = 'application/json'

    @property
    def config(self):
        h = {'Content-type': self.content_type}
        if self.token:
            h['Authorization'] = f'Bearer {self.token}'
        elif self.user and self.key:
            h.update({'username': self.user, 'password': self.key})
        return h


@dataclass_json
@dataclass
class LazyAPIModel:
    url: str
    header: LazyHeader
    routes: Dict[str, LazyRoute]
    session: Optional[LazySession] = None

    @property
    def sess(self):
        if not self.session:
            self.session = LazySession(header=self.header.config)
        return self.session

    async def async_call(self, route, *args, **kwargs):
        return await self.sess.async_fetch(**self.routes[route].get_config(base_url=self.url, *args, **kwargs))

    def get(self, route, *args, **kwargs):
        if route not in self.routes:
            raise ValueError
        if self.routes[route].is_async and kwargs.get('call_async', False):
            return self.async_call(route, *args, **kwargs)
        return self.sess(**self.routes[route].get_config(base_url=self.url, *args, **kwargs))

    def __call__(self, route, *args, **kwargs):
        return self.get(route, *args, **kwargs)

@dataclass_json
@dataclass
class LazyAPIConfig:
    url: str
    user: Optional[str] = None
    key: Optional[str] = None
    token: Optional[str] = None
    default_params: Optional[Dict[str, str]] = None
    params_key: Optional[str] = None
    data_key: Optional[str] = None
    default_fetch: Optional[str] = None
    default_async: Optional[str] = None
    route_config: Optional[Dict[str, LazyRoute]] = None


class LazyAPI:
    def __init__(self, config: LazyAPIConfig, *args, **kwargs):
        self.config = config
        self.header = LazyHeader(user=self.config.user, key=self.config.key, token=self.config.token)
        self.api = LazyAPIModel(self.config.url, self.header, self.config.route_config)
        for route_name in list(self.config.route_config.keys()):
            func = (lambda route_name=route_name, *args, **kwargs: self.api.get(route=route_name, *args, **kwargs))
            setattr(self, route_name, func)
    
    def api_call(self, is_async=False, *args, **kwargs):
        return self.api(route=(self.config.default_async if is_async else self.config.default_fetch), *args, **kwargs)
    
    async def async_call(self, *args, **kwargs):
        return await self.api.async_call(route=self.config.default_async, *args, **kwargs)
    
    def __call__(self, route, *args, **kwargs):
        return self.api(route, *args, **kwargs)
    
    @classmethod
    def build(cls, config, *args, **kwargs):
        if isinstance(config, LazyAPIConfig):
            pass
        elif isinstance(config, dict):
            config = LazyAPIConfig.from_dict(config)
        elif isinstance(config, str):
            config = LazyAPIConfig.from_json(config)
        return LazyAPI(config, *args, **kwargs)




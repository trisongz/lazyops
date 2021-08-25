import requests
import aiohttp
from lazyops import async_cache, timed_cache
from lazyops.lazyio import LazyJson
from ._base import lazyclass, dataclass, List, Union, Any
from .tfserving_pb2 import TFSModelConfig, TFSConfig



@lazyclass
@dataclass
class TFSRequest:
    data: Any

    def to_data(self):
        if isinstance(self.data, str):
            return {'inputs': [self.data]}
        if isinstance(self.data, list):
            return {'inputs': self.data}
        if isinstance(self.data, dict):
            if self.data.get('inputs'):
                return self.data
            if self.data.get('text'):
                if isinstance(self.data['text'], str):
                    return {'inputs': [self.data['text']]}
                return {'inputs': self.data['text']}
        return {'inputs': self.data}


@lazyclass
@dataclass
class TFSModelEndpoint:
    url: str
    config: TFSModelConfig
    ver: str = 'v1'
    sess: requests.Session = requests.Session()
    aiosess: aiohttp.ClientSession = None

    @property
    def default_endpoint(self):
        return f'{self.url}/{self.ver}/models/{self.config.name}'
    
    @property
    def default_url(self):
        if self.config.default_label:
            return self.default_endpoint + f'/labels/{self.config.default_label}'
        if self.config.default_version:
            return self.default_endpoint + f'/versions/{self.config.default_version}'
        return self.default_endpoint
    
    @property
    def default_predict(self):
        return self.default_url + ':predict'
    
    def get_label(self, label: str = 'latest'):
        return self.default_endpoint + '/labels/' + label
    
    def get_version(self, ver: Union[str, int]):
        return self.default_endpoint + '/versions/' + str(ver)
    
    def get_endpoint(self, label: str = None, ver: Union[str, int] = None):
        if label:
            return self.get_label(label)
        if ver:
            return self.get_version(ver)
        return self.default_url
    
    def get_predict_endpoint(self, label: str = None, ver: Union[str, int] = None):
        if label:
            return self.get_label(label) + ':predict'
        if ver:
            return self.get_version(ver) + ':predict'
        return self.default_predict
        
    @timed_cache(seconds=600)
    def get_metadata(self, label: str = None, ver: Union[str, int] = None):
        ep = self.get_endpoint(label=label, ver=ver)
        return self.sess.get(ep + '/metadata').json()
    
    @async_cache
    async def get_aio_metadata(self, label: str = None, ver: Union[str, int] = None):
        ep = self.get_endpoint(label=label, ver=ver)
        resp = await self.aiosess.get(ep + '/metadata')
        return resp.json()

    @async_cache
    async def aio_predict(self, data, label: str = None, ver: Union[str, int] = None, **kwargs):
        epoint = self.get_predict_endpoint(label=label, ver=ver)
        item = TFSRequest(data=data)
        res = await self.aiosess.post(epoint, json=item.to_data())
        return res.json(loads=LazyJson.loads)
    
    @timed_cache(seconds=60)
    def predict(self, data, label: str = None, ver: Union[str, int] = None, **kwargs):
        epoint = self.get_predict_endpoint(label=label, ver=ver)
        item = TFSRequest(data=data)
        res = self.sess.post(epoint, json=item.to_data())
        return res.json(loads=LazyJson.loads)
    
    @property
    def is_alive(self):
        return bool(self.get_metadata().get('model_spec'))
    

class TFServeModel:
    def __init__(self, url: str, configs: List[TFSModelConfig], ver: str = 'v1', **kwargs):
        self.url = url
        self.configs = configs
        self.ver = ver
        self.sess = requests.Session()
        self.aiosess = aiohttp.ClientSession()
        self.endpoints = {config.name: TFSModelEndpoint(url, config=config, ver=ver, sess=self.sess, aiosess=self.aiosess) for config in configs}
        self.default_model = kwargs.get('default_model') or configs[0].name
        self.available_models = [config.name for config in configs]

    def predict(self, data, model: str = None, label: str = None, ver: Union[str, int] = None, **kwargs):
        if model: assert model in self.available_models
        model = model or self.default_model
        return self.endpoints[model].predict(data, label=label, ver=ver, **kwargs)

    async def aio_predict(self, data, model: str = None, label: str = None, ver: Union[str, int] = None, **kwargs):
        if model: assert model in self.available_models
        model = model or self.default_model
        return await self.endpoints[model].aio_predict(data, label=label, ver=ver, **kwargs)
    
    @property
    def api_status(self):
        return {model: self.endpoints[model].is_alive for model in self.available_models}
    
    @timed_cache(seconds=600)
    def get_api_metadata(self):
        return {model: self.endpoints[model].get_metadata() for model in self.available_models}

    @async_cache
    async def get_aio_api_metadata(self):
        return {model: await self.endpoints[model].get_aio_metadata() for model in self.available_models}
    

    @classmethod
    def from_config_file(cls, url, filepath: str, ver: str = 'v1', **kwargs):
        configs = TFSConfig.from_config_file(filepath, as_obj=True)
        return TFServeModel(url=url, configs=configs, ver=ver, **kwargs)
    

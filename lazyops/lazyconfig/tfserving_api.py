import requests
import aiohttp
import simdjson as json
from lazyops.utils import timed_cache
from lazyops.serializers import async_cache

from ._base import lazyclass, dataclass, List, Union, Any, Dict
from .tfserving_pb2 import TFSModelConfig, TFSConfig

jparser = json.Parser()


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


class TFSModelEndpoint(object):
    def __init__(
        self, 
        url: str,
        config: TFSModelConfig,
        ver: str = 'v1',
        sess: requests.Session = requests.Session(),
        headers: Dict[str, Any] = {},
        ):
        self.url = url
        self.config = config
        self.ver = ver
        self.sess = sess
        self.headers = headers
        self.validate_endpoints()
    

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
        return self.sess.get(ep + '/metadata', verify=False).json()
    
    async def get_aio_metadata(self, label: str = None, ver: Union[str, int] = None, **kwargs):
        epoint = self.get_endpoint(label=label, ver=ver)
        async with aiohttp.ClientSession(headers=self.headers) as sess:
            async with sess.get(epoint + '/metadata', verify_ssl=False, **kwargs) as resp:
                return await resp.json()

    async def aio_predict(self, data, label: str = None, ver: Union[str, int] = None, **kwargs):
        epoint = self.get_predict_endpoint(label=label, ver=ver)
        item = TFSRequest(data=data)
        async with aiohttp.ClientSession(headers=self.headers) as sess:
            async with sess.post(epoint, json=item.to_data(), verify_ssl=False, **kwargs) as resp:
                return await resp.json()
    
    @timed_cache(seconds=60)
    def predict(self, data, label: str = None, ver: Union[str, int] = None, **kwargs):
        epoint = self.get_predict_endpoint(label=label, ver=ver)
        item = TFSRequest(data=data)
        res = self.sess.post(epoint, json=item.to_data(), verify=False)
        return res.json()
    
    @property
    def is_alive(self):
        return bool(self.get_metadata().get('model_spec'))
    
    def validate_endpoints(self):
        for n, version in enumerate(self.config.model_versions):
            r = self.get_metadata(label=version.label)
            if r.get('error'): self.config.model_versions[n].label = None
            r = self.get_metadata(ver=str(version.step))
            if r.get('error'): self.config.model_versions[n].step = None
    

class TFServeModel:
    def __init__(self, url: str, configs: List[TFSModelConfig], ver: str = 'v1', **kwargs):
        self.url = url
        self.configs = configs
        self.ver = ver
        self.headers = {'Content-Type': 'application/json'}
        if kwargs: self.headers.update(kwargs.get('headers'))
        self.sess = requests.Session()
        self.sess.headers.update(self.headers)
        self.endpoints = {config.name: TFSModelEndpoint(url, config=config, ver=ver, sess=self.sess, headers=self.headers) for config in configs}
        self.default_model = kwargs.get('default_model') or configs[0].name
        self.available_models = [config.name for config in configs]
        self.validate_models()


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
    
    def validate_models(self):
        for model in list(self.available_models):
            if not self.endpoints[model].is_alive:
                self.available_models.remove(model)
                _ = self.endpoints.pop(model)
        if self.default_model not in self.available_models:
            self.default_model = self.available_models[0]


from lazyops import get_logger, timer
from lazyops.apis import LazyAPI

## Eleuther.ai API
## Source: https://github.com/kingoflolz/mesh-transformer-jax/#gpt-j-6b

eai_config = {
    'url': 'https://api.eleuther.ai',
    'token': None,
    'default_params': {'top_p': 0.9, 'temp': 1},
    'params_key': None,
    'data_key': 'context',
    'default_fetch': 'complete',
    'default_async': 'complete_async',
    'route_config': {
        'complete': {
            'method': 'POST',
            'path': '/complete',
            'params': {'top_p': 0.9, 'temp': 1},
            'params_key': None,
            'data_key': 'context',
            'is_async': False,
            'prefix_payload': False,
            'decode_json': True,
        },
        'complete_async': {
            'method': 'POST',
            'path': '/complete',
            'params': {'top_p': 0.9, 'temp': 1},
            'params_key': None,
            'data_key': 'context',
            'is_async': True,
            'prefix_payload': False,
            'decode_json': True,
        },
    }
}

# TextSynth API
# Source: https://bellard.org/textsynth/


textsynth_config = {
    'url': 'https://bellard.org/textsynth/api/v1/engines/gptj_6B',
    'token': None,
    'default_params': {'top_p': 0.9, 'temperature': 1, 'seed': 0, 'stream': False, 'top_k': 40},
    'params_key': None,
    'data_key': 'prompt',
    'default_fetch': 'complete',
    'default_async': 'complete_async',
    'route_config': {
        'complete': {
            'method': 'POST',
            'path': '/completions',
            'params': {'top_p': 0.9, 'temperature': 1, 'seed': 0, 'stream': False, 'top_k': 40},
            'params_key': None,
            'data_key': 'prompt',
            'is_async': False,
            'prefix_payload': False,
            'decode_json': True,
        },
        'complete_async': {
            'method': 'POST',
            'path': '/completions',
            'params': {'top_p': 0.9, 'temperature': 1, 'seed': 0, 'stream': False, 'top_k': 40},
            'params_key': None,
            'data_key': 'prompt',
            'is_async': True,
            'prefix_payload': False,
            'decode_json': True,
        },
    }
}

logger = get_logger('LazyEXP', 'GPTJ')

class GPTJAPI:
    def __init__(self, fallback='eai'):
        self.eai = LazyAPI.build(eai_config)
        self._eai_config =  {'top_p': 0.9, 'temp': 1}
        self.ts = LazyAPI.build(textsynth_config)
        self._ts_config = {'top_p': 0.9, 'temperature': 1, 'seed': 0, 'stream': False, 'top_k': 40}
        self._fallback = fallback
    
    @property
    def primary(self):
        if self._fallback == 'eai':
            return self.ts
        return self.eai
    
    @property
    def fallback(self):
        if self._fallback == 'eai':
            return self.eai
        return self.ts
    
    def get_base_params(self, is_fallback=False):
        if is_fallback:
            if self._fallback == 'eai':
                return self._eai_config.copy()
            return self._ts_config.copy()
        if self._fallback == 'eai':
            return self._ts_config.copy()
        return self._eai_config.copy()

    def build_params(self, text, is_fallback=False, **config):
        p = self.get_base_params(is_fallback)
        if config:
            for k,v in config.items():
                if k in p:
                    config[k] = v
        return p

    def predict(self, text, **config):
        p = self.build_params(text, **config)
        try:
            res = self.primary.complete(data=text, **p)
            #print(res)
            return res.get('completion', res.get('text','')), res
        
        except Exception as e:
            logger.error(f'Error Calling API: {str(e)}')
            p = self.build_params(text, is_fallback=True, **config)
            try:
                res = self.fallback.complete(data=text, **p)
                return res.get('text', res.get('completion','')), res
            except Exception as e:
                logger.error(f'Error Calling API: {str(e)}')
                return None, None
    
    async def as_predict(self, text, **config):
        p = self.build_params(text, **config)
        try:
            res = await self.primary.complete_async(**p)
            return res.get('completion', res.get('text','')), res
        
        except Exception as e:
            logger.error(f'Error Calling API: {str(e)}')
            p = self.build_params(text, is_fallback=True, **config)
            try:
                res = await self.fallback.complete_async(**p)
                return res.get('text', res.get('completion','')), res
            except Exception as e:
                logger.error(f'Error Calling API: {str(e)}')
                return None, None
    
    
                

if __name__ == '__main__':
    test_texts = [
        'In a shocking finding, scientist discovered a herd of unicorns living in a remote, previously unexplored valley, in the Andes Mountains. Even more surprising to the researchers was the fact that the unicorns spoke perfect English.',
        'Game of Thrones is',
        'For todays homework assignment, please describe the reasons for the US Civil War.'
    ]
    api = GPTJAPI()
    for txt in test_texts:
        res, _ = api.predict(text=txt)
        logger.info(res)
    


    




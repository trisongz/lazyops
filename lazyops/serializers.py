import aiocache
from lazyops.lazyio.models import LazyJson, LazyPickler


from aiocache import caches
from aiocache.serializers import StringSerializer, PickleSerializer, JsonSerializer

caches.set_config({
    'default': {
        'cache': "aiocache.SimpleMemoryCache",
        'serializer': {
            'class': "lazyops.lazyio.LazyJson"
        }
    },
})

from aiocache import cached as async_cache

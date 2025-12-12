"""
Testing the Proxied Object Module
"""

import abc
import aiohttpx
from lzl.proxied import proxied
from lzl.logging import logger

logger.set_module_name('__main__', 'lzl.test')


@proxied
class DummyClass(abc.ABC):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        print('DummyClass initialized')

    def hi(self, *args, **kwargs):
        print('DummyClass called')
        return 'hi'
    
    def test_request(self):
        resp = aiohttpx.get('https://oai.hconeai.com')
        return resp.text

    def test_capture(self):
        with logger.silenced('httpx'):
            self.test_request()

    def test_hook(self, msg: str):
        """
        Prints the message
        """
        print(f'Test Hook: {msg}')


def run_test():

    logger.info('Running Test')
    with logger.hooks(DummyClass.test_hook):
        DummyClass.test_request()
        logger.info('Completed Request')
    
    logger.info('Completed Hook')
    logger.info('No Log Record should be printed after this')
    DummyClass.test_capture()
    logger.info('No log record should be printed before this') 

    # Test Silenced
    with logger.hooks(DummyClass.test_hook):
        text = DummyClass.test_request()
        logger.info(text)

run_test()

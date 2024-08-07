import abc
from typing import Union
from lazyops.utils.pooler import ThreadPoolV2 as ThreadPooler

class BaseCompress(abc.ABC):

    @abc.abstractclassmethod
    def compress(cls, data: Union[str, bytes], **kwargs) -> bytes:
        """
        Base Compress
        """
        pass

    @abc.abstractclassmethod
    def decompress(cls, data: Union[str, bytes], **kwargs) -> bytes:
        """
        Base Decompress
        """
        pass


    @abc.abstractclassmethod
    async def acompress(cls, data: Union[str, bytes], **kwargs) -> bytes:
        """
        Base Compress
        """
        return await ThreadPooler.run_async(cls.compress, data, **kwargs)
    
    @abc.abstractclassmethod
    async def adecompress(cls, data: Union[str, bytes], **kwargs) -> bytes:
        """
        Base Decompress
        """
        return await ThreadPooler.run_async(cls.decompress, data, **kwargs)
    


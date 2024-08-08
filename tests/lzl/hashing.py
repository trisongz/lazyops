from pydantic import BaseModel, Field
from lzo.utils.hashing import create_object_hash, create_hash_from_args_and_kwargs
from lzo.utils import logger

class TestModel(BaseModel):
    name: str = Field(..., description="The name of the model")
    age: int = Field(..., description="The age of the model")

def test_func(*args, **kwargs):
    """
    Test Function
    """
    return create_hash_from_args_and_kwargs(*args, **kwargs)


def test_hashing():
    """
    Test Hashing
    """
    model = TestModel(name="test", age=10)
    model_hash = create_object_hash(model)
    logger.info(f'Model Hash: {model_hash}')
    logger.info(f'Function Hash: {test_func(model, name="test", age=10)}')
    logger.info(f'Function Hash: {test_func(model, age = 10, name = "test")}')
    logger.info(f'Model Hash 2: {create_object_hash(model)}')

if __name__ == '__main__':
    test_hashing()
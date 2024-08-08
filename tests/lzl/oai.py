from __future__ import annotations

import asyncio
from enum import Enum
from private_oai_v2 import OpenAI
# from lzl.api.openai.clients import OpenAI, OpenAIManager
from lzl.api.openai.utils import logger
from pydantic import BaseModel, Field

class Unit(str, Enum):
    """
    The unit to use for the temperature. Celsius or Fahrenheit.
    """
    celsius = "celsius"
    fahrenheit = "fahrenheit"

class Weather(BaseModel):
    location: str = Field(..., description="The city and state, e.g. San Francisco, CA.")
    unit: Unit = Field(Unit.fahrenheit)

functions = [ 
  {
    "name": "get_current_weather",
    "description": "Get the current weather in a given location",
    "schema": Weather,
    "strict": True,
  }
]

async def test_functions_v2():

    chat = OpenAI.get_chat_client(noproxy_required = False)
    chat = OpenAI.get_chat_client(noproxy_required = False)

    logger.info(f'Chat Client: {chat.name}')
    result = await chat.async_create(
        messages = [
            {"role": "user", "content": "What's the weather like in Boston today?"}
        ],
        # functions = functions,
        json_schema = functions[0],
    )
    logger.info(result.model_dump(exclude_none = True))
    logger.info(f'Result Headers: {result.headers}: {result.has_stream}')
    # logger.info(f'Result Chat Function: {result.function_results}')
    logger.info(f'Result Chat Function: {result.json_schema}')
    logger.info(f'Result Consumption: {result.consumption_cost}')


async def test_functions():

    # az = OpenAI.init_api_client('az', set_as_default=False, debug_enabled = True)
    # az.configure(proxy_config = settings.get_app_default_file('openai_proxy', suffix = 'yaml', env_var = 'GOVERLY_OAI_PROXY_CONFIG_FILE'))
    result = await OpenAI.chat.async_create(
        # model = model,
        # model = 'gpt-4o',
        messages = [
            {"role": "user", "content": "What's the weather like in Boston today?"}
        ],
        functions = functions,
        # stream = True
    )
    logger.info(f'Result Model: {result}')
    logger.info(result.dict(exclude_none = True))
    # pyd_extra = result.__pydantic_private__.items()
    # logger.info(f'Result Pydantic Extra: {pyd_extra}')

    # logger.info(f'Result Pydantic Extra: {result.__private_attributes__.items()}')

    # logger.info(dir(result))
    logger.info(f'Result Type: {type(result)}')
    logger.info(f'Result Headers: {result.headers}: {result.has_stream}')

    # logger.info(f'Result Chat Message: {result.messages}')
    logger.info(f'Result Chat Function: {result.function_result_objects}')
    logger.info(f'Result Chat Function: {result.function_results}')
    
    logger.info(f'Result Usage: {result.usage}')
    logger.info(f'Result Consumption: {result.consumption_cost}')

    logger.info(f'Result Usage: {result["usage"]}')


async def run_test():

    # model = "gpt-3.5-turbo-16k"
    # s = OpenAIManager()
    result = await OpenAI.chat.async_create(
        # model = model,
        messages = [
            {"role": "user", "content": "Translate the following English text to French: “Multiple models, each with different capabilities and price points. Prices are per 1,000 tokens. You can think of tokens as pieces of words, where 1,000 tokens is about 750 words. This paragraph is 35 tokens”"}
        ],
    )
    logger.info(f'Result Model: {result}')
    logger.info(f'Result Type: {type(result)}')

    logger.info(f'Result Text: {result.text}')
    logger.info(f'Result Chat Message: {result.messages}')
    
    logger.info(f'Result Usage: {result.usage}')
    logger.info(f'Result Consumption: {result.consumption_cost}')
    
    

    # result = OpenAI.chat.create(
    #     messages = [
    #         {"role": "user", "content": "Translate the following English text to French: “Multiple models, each with different capabilities and price points. Prices are per 1,000 tokens. You can think of tokens as pieces of words, where 1,000 tokens is about 750 words. This paragraph is 35 tokens”"}
    #     ],
    # )

    # logger.info(f'Result Model: {result}')
    # logger.info(f'Result Type: {type(result)}')

    # logger.info(f'Result Text: {result.text}')
    # logger.info(f'Result Chat Message: {result.messages}')
    
    # logger.info(f'Result Usage: {result.usage}')
    


async def entrypoint():
    await test_functions_v2()


if __name__ == '__main__':
    asyncio.run(entrypoint())
# asyncio.run(run_test())    


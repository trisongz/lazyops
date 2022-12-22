import typing
from re import sub

def to_camel_case(text: str):
    """Convert a snake str to camel case."""
    components = text.split("_")
    # We capitalize the first letter of each component except the first one
    # with the 'title' method and join them together.
    return components[0] + "".join(x.title() for x in components[1:])

def to_snake_case(text: str):
    """
    multiMaster -> multi_master
    """
    return '_'.join(
        sub('([A-Z][a-z]+)', r' \1',
        sub('([A-Z]+)', r' \1',
        text.replace('-', ' '))).split()).lower()

def to_snake_case_args(text: str):
    """
    multiMaster -> multi-master
    """
    return '-'.join(
        sub('([A-Z][a-z]+)', r' \1',
        sub('([A-Z]+)', r' \1',
        text.replace('-', ' '))).split()).lower()

def to_graphql_format(
    data: typing.Dict
) -> typing.Dict:
    """
    converts all keys in the data to
    camelcase
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[to_camel_case(key)] = to_graphql_format(value)
        elif isinstance(value, list):
            values = []
            for item in value:
                if isinstance(item, (dict, list)):
                    values.append(to_graphql_format(item))
                else:
                    values.append(item)
            result[to_camel_case(key)] = values
        else:
            result[to_camel_case(key)] = value    
    return result

def from_graphql_format(
    data: typing.Dict
) -> typing.Dict:
    """
    converts all camelcase keys in the data to
    snake_case
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[to_snake_case(key)] = from_graphql_format(value)
        elif isinstance(value, list):
            values = []
            for item in value:
                if isinstance(item, (dict, list)):
                    values.append(from_graphql_format(item))
                else:
                    values.append(item)
            result[to_snake_case(key)] = values
        else:
            result[to_snake_case(key)] = value    
    return result
        
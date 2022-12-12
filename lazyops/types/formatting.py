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

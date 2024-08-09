from __future__ import annotations

"""
A More Memory Efficient Version of cysimdjson as it reuses the parser.
"""

import json
import cysimdjson
from typing import Optional, Union
    

# Once it hits this number, we will recycle the parser
MAX_PARSER_COUNT_TO_RECYCLE: int = 50
_parser: Optional['cysimdjson.JSONParser'] = None
_counter: int = 0

def get_parser() -> 'cysimdjson.JSONParser':
    global _parser, _counter
    if _counter > MAX_PARSER_COUNT_TO_RECYCLE:
        del _parser
        _parser = None
        _counter = 0
    if _parser is None: 
        _parser = cysimdjson.JSONParser()
    _counter += 1
    return _parser

def set_max_parser_count_to_recycle(count: int):
    global MAX_PARSER_COUNT_TO_RECYCLE
    MAX_PARSER_COUNT_TO_RECYCLE = count

def load(fp, *, cls=None, object_hook=None, parse_float=None, parse_int=None,
         parse_constant=None, object_pairs_hook=None, **kwargs):
    """
    Same as the built-in json.load(), with the following exceptions:

        - All parse_* arguments are currently ignored. simdjson does not
          currently provide hooks for these, but it is planned.
        - object_pairs_hook is ignored.
        - cls is ignored.
    """
    parser = get_parser()
    return parser.parse(fp.read(), True)


def loads(s: Union[str, bytes], *, cls=None, object_hook=None, parse_float=None, parse_int=None,
          parse_constant=None, object_pairs_hook=None, **kwargs):
    """
    Same as the built-in json.loads(), with the following exceptions:

        - All parse_* arguments are currently ignored. simdjson does not
          currently provide hooks for these, but it is planned.
        - object_pairs_hook is ignored.
        - cls is ignored.
    """
    parser = get_parser()
    return (parser.parse(s) if isinstance(s, bytes) else parser.parse_string(s)).export()

dumps = json.dumps
dump = json.dump
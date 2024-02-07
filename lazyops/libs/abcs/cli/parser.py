from __future__ import annotations

"""
Parser ABC
"""

import argparse
from typing import Any, Dict, List, Optional, Tuple, Union, Type, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel
    from pydantic.fields import FieldInfo


_parsed_parser_objects: Dict[str, argparse.ArgumentParser] = {}

_parser_types: Dict[str, Type] = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
    'list': list,
    'dict': dict,
    'List': List,
    # 'tuple': tuple,
    # 'None': None,
}

def parse_one(
    name: str,
    field: FieldInfo,
) -> Tuple[Set, Dict]:
    """
    Parse a single field into the args and kwargs for the add_argument method
    """
    args = set()
    kwargs = {}

    field_type = field.annotation
    for pt in _parser_types.values():
        if field_type == Optional[pt]:
            field_type = pt

            break

    if field.is_required():
        args.add(name)
    else:
        args.add(f'--{name}')
        if field.json_schema_extra and field.json_schema_extra.get('alt'):
            args.add(f'-{field.json_schema_extra["alt"]}')
        
        elif len(name) > 3:
            if '_' in name:
                parts = name.split('_')
                short_name = ''.join([p[0] for p in parts])
                args.add(f'-{short_name}')
            else: args.add(f'-{name[:2]}')


    if field_type == bool:
        kwargs['action'] = 'store_true' if field.default is False or field.default is None else 'store_false'
    elif field_type in {list[str], list[int], list[float], List[str], List[int], List[float]}:
        kwargs['action'] = 'append'
    else:
        kwargs['type'] = field_type
    if field.default is not None:
        kwargs['default'] = field.default
    elif field.default_factory is not None:
        kwargs['default'] = None

    if field.description is not None:
        kwargs['help'] = field.description

    return args, kwargs


def create_argparser_from_model(
    model: Type['BaseModel'],
    exit_on_error: Optional[bool] = False,
    **argparser_kwargs,
) -> argparse.ArgumentParser:
    """
    Create an Argument Parser from a Pydantic Model
    """
    global _parsed_parser_objects
    model_key = f'{model.__module__}.{model.__name__}'
    if model_key not in _parsed_parser_objects:
        doc = model.__doc__ or ''
        usage = argparser_kwargs.pop('usage', None)
        if 'Usage' in doc and not usage:
            parts = doc.split('Usage:', 1)
            doc, usage = parts[0].strip(), parts[-1].strip()
            

        parser = argparse.ArgumentParser(description = doc, usage = usage, exit_on_error = exit_on_error, **argparser_kwargs)
        for name, field in model.model_fields.items():
            if field.json_schema_extra and field.json_schema_extra.get('hidden', False):
                continue
            args, kwargs = parse_one(name, field)
            parser.add_argument(*args, **kwargs)
        _parsed_parser_objects[model_key] = parser
    return _parsed_parser_objects[model_key]
    
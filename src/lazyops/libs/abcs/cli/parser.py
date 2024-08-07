from __future__ import annotations

"""
Parser ABC
"""

import argparse
from typing import Any, Dict, List, Optional, Tuple, Union, Type, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel
    from pydantic.fields import FieldInfo

class ParserException(Exception):
    """
    Parser Exception
    """

    def __init__(self, message: str, help_text: str = None):
        self._error_message = message
        if help_text: message = f'{message}\n\n{help_text}'
        super().__init__(message)
        self._help_text = help_text

class ArgParser(argparse.ArgumentParser):


    def print_help(self, file=None):
        """
        The default print_help method sends output to stdout, which isn't
        useful when run on the server. We have this raise the same exception
        as ``error`` so it gets handled in the same way (hopefully with
        help text going back to the user.)
        """
        raise ParserException('', help_text = self.format_help())

    def error(self, message):
        """error(message: string)

        Prints a usage message incorporating the message to stderr and
        exits.

        If you override this in a subclass, it should not return -- it
        should either exit or raise an exception.
        """
        # args = {'prog': self.prog, 'message': message}
        # raise ValueError('%(prog)s: error: %(message)s\n' % args)
        raise ParserException(message, help_text = self.format_help())

_parsed_parser_objects: Dict[str, ArgParser] = {}

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
) -> Tuple[Set, Dict]:  # sourcery skip: low-code-quality
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
        if not field.json_schema_extra or not field.json_schema_extra.get('exclude_name', False):
            args.add(f'--{name}')
        
        if field.json_schema_extra and field.json_schema_extra.get('alt'):
            alt = field.json_schema_extra['alt']
            if isinstance(alt, str): alt = [alt]
            for a in alt:
                if not isinstance(a, str): a = str(a)
                if not a.startswith('-'): a = f'-{a}'
                args.add(a)
            # args.add(f'-{field.json_schema_extra["alt"]}')
        
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
    parser_class: Optional[Type[ArgParser]] = None,
    **argparser_kwargs,
) -> ArgParser:
    """
    Create an Argument Parser from a Pydantic Model
    """
    global _parsed_parser_objects

    model_key = f'{model.__module__}.{model.__name__}'
    if model_key not in _parsed_parser_objects:
        if parser_class is None: parser_class = ArgParser
        doc = model.__doc__ or ''
        usage = argparser_kwargs.pop('usage', None)
        if 'Usage' in doc and not usage:
            parts = doc.split('Usage:', 1)
            doc, usage = parts[0].strip(), parts[-1].strip()
            
        parser = parser_class(description = doc, usage = usage, exit_on_error = exit_on_error, **argparser_kwargs)
        for name, field in model.model_fields.items():
            if field.json_schema_extra and field.json_schema_extra.get('hidden', False):
                continue
            args, kwargs = parse_one(name, field)
            parser.add_argument(*args, **kwargs)
        _parsed_parser_objects[model_key] = parser
    return _parsed_parser_objects[model_key]


def create_argparser_from_model_v2(
    model: Type['BaseModel'],
    exit_on_error: Optional[bool] = False,
    sub_parser: Optional[argparse.ArgumentParser] = None,
    **argparser_kwargs,
) -> ArgParser:
    """
    Create an Argument Parser from a Pydantic Model
    """
    global _parsed_parser_objects

    from pydantic import BaseModel

    model_key = f'{model.__module__}.{model.__name__}'
    if model_key not in _parsed_parser_objects:
        doc = model.__doc__ or ''
        usage = argparser_kwargs.pop('usage', None)
        if 'Usage' in doc and not usage:
            parts = doc.split('Usage:', 1)
            doc, usage = parts[0].strip(), parts[-1].strip()
            

        parser = sub_parser if sub_parser is not None else ArgParser(description = doc, usage = usage, exit_on_error = exit_on_error, **argparser_kwargs)
        # Check if there are any subparsers
        if any(
            isinstance(field.annotation, type(BaseModel))
            for field in model.model_fields.values()
        ):
            subparsers = parser.add_subparsers(dest = 'subparser')


        for name, field in model.model_fields.items():
            if field.json_schema_extra and field.json_schema_extra.get('hidden', False):
                continue
            if isinstance(field.annotation, type(BaseModel)):
                subparser = subparsers.add_parser(name, help = field.description, argument_default = field.default, exit_on_error = exit_on_error)
                create_argparser_from_model_v2(field.annotation, exit_on_error = exit_on_error, sub_parser = subparser, **argparser_kwargs)
                # subparser = create_argparser_from_model(field.annotation, exit_on_error = exit_on_error, **argparser_kwargs)
                # parser.add_subparsers(name, subparser)
                continue

            args, kwargs = parse_one(name, field)
            parser.add_argument(*args, **kwargs)
        if sub_parser is not None:
            return parser
        _parsed_parser_objects[model_key] = parser
    return _parsed_parser_objects[model_key]
    
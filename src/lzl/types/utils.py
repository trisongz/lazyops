from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from pydantic import BaseModel, AliasChoices


ModelT = t.TypeVar("ModelT", bound="BaseModel")

_extracted_pydantic_model_kws: t.Dict[str, t.List[str]] = {}

def extract_pydantic_model_kws(
    model: ModelT,
    kwargs: t.Dict[str, t.Any],
) -> t.Tuple[t.Dict[str, t.Any], t.Dict[str, t.Any]]:
    """
    Extracts the kwargs from the resource and returns the kwargs and the model kwargs
    """
    global _extracted_pydantic_model_kws
    base_model_name = f"{model.__module__}.{model.__name__}"
    if base_model_name not in _extracted_pydantic_model_kws:
        from .base import get_pydantic_field_names
        resource_kws = get_pydantic_field_names(model)
        _extracted_pydantic_model_kws[base_model_name] = resource_kws
    model_kwargs = {
        key: kwargs.pop(key) for key in kwargs if key in _extracted_pydantic_model_kws[base_model_name]
    }
    return kwargs, model_kwargs


def create_alias_choices(
    key: str,
    *values: str,
    key_pos: t.Literal['prefix', 'suffix'] = 'suffix',
    case: t.Optional[t.Literal['upper', 'lower']] = 'upper',
) -> 'AliasChoices':
    """
    Helper Function to create alias choices
    
    Args:
        key (str): The key to use for the alias choices
        *values (str): The values to use for the alias choices
        key_pos (Literal['prefix', 'suffix']): The position for the key to use for the alias choices

    Example:
    
        >>> create_alias_choices('database', 'url', 'port', key_pos = 'prefix')
        
        AliasChoices('DATABASE_URL', 'DATABASE_PORT')

        >>> create_alias_choices('url', 'redis', 'pg', key_pos = 'suffix')

        AliasChoices('REDIS_URL', 'PG_URL')

    """
    alias_values: t.List[str] = []
    if key_pos == 'suffix':
        alias_values.extend(f'{value}_{key}' for value in values)
    elif key_pos == 'prefix':
        alias_values.extend(f'{key}_{value}' for value in values)
    else: raise ValueError(f'Invalid Key Position: {key_pos}')
    if case == 'upper': alias_values = [v.upper() for v in alias_values]
    elif case == 'lower': alias_values = [v.lower() for v in alias_values]
    from pydantic import AliasChoices
    return AliasChoices(*alias_values)
from __future__ import annotations


from typing import Any, Dict, TypeVar, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound="BaseModel")

_extracted_pydantic_model_kws: Dict[str, List[str]] = {}

def extract_pydantic_model_kws(
    model: ModelT,
    kwargs: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
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

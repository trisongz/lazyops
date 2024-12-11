from __future__ import annotations

"""
Temporal Workflow Mixins
"""


import uuid
import typing as t

if t.TYPE_CHECKING:
    from .base import BaseTemporalMixin


def default_id_gen_function(obj: 'BaseTemporalMixin', *args, prefix: t.Optional[str] = None, **kwargs) -> str:
    """
    Default ID Generator Function
    """
    # logger.info(f'ID Generator Options: {obj}', prefix = 'Temporal')
    base = prefix or obj.id_gen.prefix or ''
    if obj.id_gen.func: id_gen = obj.id_gen.func(*args, **kwargs)
    else: id_gen = str(uuid.uuid4().int)
    # id_gen = str(uuid.uuid4().int)
    if obj.id_gen.id_length: id_gen = id_gen[:obj.id_gen.id_length]
    base += f'{obj.id_gen.joiner}{id_gen}'
    if obj.id_gen.suffix: base += f'{obj.id_gen.joiner}{obj.id_gen.suffix}'
    base = base.lstrip(obj.id_gen.joiner).rstrip(obj.id_gen.joiner)
    base = base.replace(" ", obj.id_gen.joiner).replace(f'{obj.id_gen.joiner}{obj.id_gen.joiner}', obj.id_gen.joiner)
    if obj.id_gen.lower: base = base.lower()
    if obj.id_gen.max_length and len(base) > obj.id_gen.max_length: base = base[:obj.id_gen.max_length]
    return base
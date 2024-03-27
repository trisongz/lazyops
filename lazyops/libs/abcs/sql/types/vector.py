from __future__ import annotations

"""
Vector Types
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union, Literal, TYPE_CHECKING

class VectorDistance(str, Enum):
    """

    Euclidean (L2): `<->`
    Cosine: `<=>`
    Max Inner Product: `<~>` Fallback to Manhattan (L1): `<~>`
    Manhattan (L1): `<~>`
    """
    EUCLIDEAN = '<->'
    COSINE = '<=>'
    MAX_INNER_PRODUCT = '<#>'
    # INNER_DISTANCE = '<#>'
    # MAX_INNER_PRODUCT = '<~>'
    # INNER_DISTANCE = '<~>'
    # MANHATTAN = '<~>'

    @property
    def vector_op(self) -> str:
        """
        Returns the Vector Op Name

        vector_l2_ops = L2 distance
        vector_ip_ops = Inner Product
        vector_cosine_ops = Cosine Distance
        """
        if self == VectorDistance.EUCLIDEAN:
            return 'vector_l2_ops'
        elif self == VectorDistance.COSINE:
            return 'vector_cosine_ops'
        return 'vector_ip_ops'
    
    @classmethod
    def parse(cls, value: str) -> 'VectorDistance':
        """
        Parses the Vector Distance
        """
        value = value.lower()
        if value in {'euclidean', 'vector_l2_ops', '<->'}:
            return cls.EUCLIDEAN
        if value in {'cosine', 'vector_cosine_ops', '<=>'}:
            return cls.COSINE
        if value in {'max_inner_product', 'vector_ip_ops', '<#>', 'inner_product'}:
            return cls.MAX_INNER_PRODUCT
        # if value in {'inner_distance', '<~>'}:
        #     return cls.INNER_DISTANCE
        # if value == 'manhattan':
        #     return cls.MANHATTAN
        raise ValueError(f"Invalid/Unsupported Vector Distance: {value}")

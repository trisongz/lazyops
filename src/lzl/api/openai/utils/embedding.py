from __future__ import annotations

"""
Embedding Utility Helpers

These are borrowed from the `openai` experiments library

- We specifically use lazy loading to avoid runtime errors if the user does not have the required dependencies
"""

from lzl import load
from lzl.proxied import ProxyObject
from lzo.types import Literal

from typing import Dict, Callable, List, Union, Optional

if load.TYPE_CHECKING:
    from scipy import spatial
    import numpy as np
    from numpy import ndarray
else:
    spatial = load.LazyLoad("scipy.spatial", install_missing=True, install_options = {'package': 'scipy'})
    np = load.LazyLoad("numpy", install_missing=True)
    
def _initialize_distance_dict(*args, **kwargs) -> Dict[str, Callable[..., float]]:
    """
    Initializes the distance dictionary
    """
    return {
        "cosine": spatial.distance.cosine,
        "euclidean": spatial.distance.euclidean,
        "inner_product": lambda x, y: -np.dot(x, y),
        "L1": spatial.distance.cityblock,
        "L2": spatial.distance.euclidean,
        "Linf": spatial.distance.chebyshev,
    }


distance_metrics: Dict[str, Callable[..., float]] = ProxyObject(obj_getter = _initialize_distance_dict)

MetricT = Literal["cosine", "L1", "L2", "Linf"]


def distances_from_embeddings(
    query_embedding: List[float],
    embeddings: List[List[float]],
    distance_metric: Optional[MetricT] = "cosine",
) -> List[List]:
    """
    Return the distances between a query embedding and a list of embeddings.
    """
    return [
        distance_metrics[distance_metric](query_embedding, embedding)
        for embedding in embeddings
    ]


def indices_of_nearest_neighbors_from_distances(
    distances: 'ndarray',
    reverse: Optional[bool] = False,
) -> 'ndarray':
    """
    Return a list of indices of nearest neighbors from a list of distances.
    """
    return np.argsort(distances)[::-1] if reverse else np.argsort(distances)
    # if reverse: distances = distances[::-1] 
    # return np.argsort(distances)
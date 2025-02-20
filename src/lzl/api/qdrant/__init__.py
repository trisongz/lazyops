"""
Qdrant Client with Unified Async / Sync 
"""

from .config import QdrantClientSettings, settings

# We need to use the full client because it waits for models to be added before initializing
from .full_client import QdrantClient
"""
Common Types
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union, Literal, TYPE_CHECKING

ValidationMethod = Literal['api_key', 'auth_token']
UserType = Literal['user', 'api_client', 'service', 'system', 'admin', 'allowed']

from typing import Optional, Dict
from lazyops.types.models import BaseSettings

class ClientSettings(BaseSettings):

    """
    Client Settings
    """
    max_retries: Optional[int] = 5
    timeout: Optional[int] = 180
    debug_enabled: Optional[bool] = True

    api_key: Optional[str] = None
    api_header: Optional[str] = None

    # API Key Details
    api_dev_mode: Optional[bool] = False # sets to local_url if enabled

    local_url: Optional[str] = 'http://localhost:80'
    cluster_url: Optional[str] = 'http://api.svc.cluster.local:80'
    external_url: Optional[str] = None

    class Config:
        env_prefix = 'LAZYOPS_CLIENT_'
        case_sensitive = False
    
    def get_headers(self):
        _base_headers = {
            'content-type': 'application/json',
        }
        if self.api_key and self.api_header: _base_headers[self.api_header] = self.api_key
        return _base_headers
    
    @property
    def endpoints(self) -> Dict[str, str]:
        return {
            'local': self.local_url,
            'cluster': self.cluster_url,
            'external': self.external_url,
        }
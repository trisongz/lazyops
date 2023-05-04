from __future__ import annotations

from pathlib import Path
from lazyops.types import BaseModel, lazyproperty, validator, Field
from lazyops.configs.base import DefaultSettings, BaseSettings
from typing import List, Dict, Union, Any, Optional

class KOpsSettings(DefaultSettings):
    kubeconfig: Optional[str] = None
    kubeconfig_context: Optional[str] = None
    kops_ctx_dir: Optional[str] = None
    kops_ctx: Optional[str] = None

    kops_watch_interval: int = 60
    kops_finalizer: str = 'kops.gex.ai/finalizer'
    kops_prefix: str = 'kops.gex.ai'
    kops_persistent_key: str = 'last-handled-configuration'
    kops_generate_event_name: str = 'kops-event-'

    kops_max_message_length: int = 1024
    kops_cut_message_infix: str = '...'

    kopf_enable_event_logging: bool = False
    kopf_event_logging_level: str = 'INFO'

    kopf_name: str = 'KOps'
    build_id: Optional[str] = None


    class Config:
        arbitrary_types_allowed = True
        case_sensitive = False
        env_prefix = ''

    @lazyproperty
    def kubeconfig_path(self):
        if not self.kubeconfig: return None
        path = Path(self.kubeconfig)
        return path if path.exists() else None

    @lazyproperty
    def kops_ctx_path(self):
        return Path(self.kops_ctx_dir) if self.kops_ctx_dir else None
    
    @lazyproperty
    def kops_kconfig_path(self):
        if self.kops_ctx and self.kops_ctx_path:
            for ext in {'.yaml', '.yml'}:
                if ext in self.kops_ctx: ext = ''
                path = self.kops_ctx_path.joinpath(f'{self.kops_ctx}{ext}')
                if path.exists():
                    return path
        return None
        
    @lazyproperty
    def kconfig_path(self) -> Path:
        return self.kops_kconfig_path or self.kubeconfig_path 
    
    def get_kconfig_path(self, ctx: str = None) -> Path:
        if ctx:
            for ext in {'.yaml', '.yml'}:
                if ext in ctx: ext = ''
                path = self.kops_ctx_path.joinpath(f'{ctx}{ext}')
                if path.exists():
                    return path

        return self.kconfig_path
import re
from typing import Optional, List, Union, Optional, Any, Dict
from dataclasses import dataclass
from lazyops import get_logger, PathIO
from lazyops.lazyclasses import lazyclass


@lazyclass
@dataclass
class TFSModelVersion:
    step: int
    label: str = 'latest'


@lazyclass
@dataclass
class TFSModelConfig:
    name: str
    base_path: str
    model_platform: str = 'tensorflow'
    model_versions: Optional[List[TFSModelVersion]] = None

    def set_only_latest(self):
        if self.model_versions:
            self.model_versions = [version for version in self.model_versions if version.label == 'latest']
    
    @property
    def default_label(self):
        if self.model_versions:
            for ver in self.model_versions:
                if ver.label is not None: return ver.label
        return None

    @property
    def default_version(self):
        if self.model_versions:
            for ver in self.model_versions:
                if ver.label is not None: return str(ver.step)
        return None
    
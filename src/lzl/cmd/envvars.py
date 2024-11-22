from __future__ import annotations

"""
Common Environment Variables
"""

import os
from pathlib import Path

GITHUB_TOKEN: str = os.environ.get('GH_TOKEN', os.getenv('GITHUB_TOKEN', ''))

# Paths
TEMP_PATH = os.getenv('TEMP_PATH', '/tmp')
BUILD_CONFIG_PATH = Path(os.getenv('BUILD_CONFIG_PATH', f'{TEMP_PATH}/build_config.yaml'))

LIB_PATH = Path(__file__).parent
ASSETS_PATH = LIB_PATH.joinpath('assets')

APP_HOME = os.getenv('APP_HOME', '/app')
APP_PATH = Path(APP_HOME)

REQUIREMENTS_PATH = Path(os.getenv('REQUIREMENTS_PATH', '/tmp/requirements'))

if pkgs_path := os.getenv('PKGS_PATH'):
    PKGS_PATH = Path(pkgs_path)
else:
    PKGS_PATH = REQUIREMENTS_PATH.joinpath('pkgs')

# DEFAULT_CONFIG_PATH = _HERE.joinpath('default_build_config.yaml')

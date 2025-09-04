import sys
from pathlib import Path
from setuptools import setup

root = Path(__file__).parent
version_text = root.joinpath('src', 'version.py').read_text()
version = version_text.split('VERSION = ', 1)[-1].strip().replace('-', '').replace("'", '')

if sys.version_info.minor < 8:
    pass  # Dependencies are handled in pyproject.toml with markers

setup(version=version)
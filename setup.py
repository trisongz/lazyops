import os
import sys
from pathlib import Path
from setuptools import setup, find_packages

if sys.version_info.major != 3:
    raise RuntimeError("This package requires Python 3+")

pkg_name = 'lazyops'
gitrepo = 'trisongz/lazyops'

root = Path(__file__).parent
version = root.joinpath('src/version.py').read_text().split('VERSION = ', 1)[-1].strip().replace('-', '').replace("'", '')

is_builder_ci = os.getenv('BUILDER_CI', 'false').lower() in {'true', '1', 't', 'y', 'yes'}
requirements = [
    'loguru',
    'pydantic',
    'pydantic-settings',
    'frozendict',
    'async_lru',
    'pyyaml',
    # 'setuptools '
] if not is_builder_ci else [
    'typer',
    'pydantic',
    'pydantic-settings',
    'pyyaml',
]

if sys.version_info.minor < 8:
    requirements.append('typing_extensions')
if sys.version_info.minor > 11:
    requirements.append('setuptools')

extras = {
    'kops': [
        'kubernetes',
        'kubernetes_asyncio',
        'kopf',
        'aiocache',
        'kr8s',
    ],
    'fastapi': [
        'fastapi',
        'uvicorn',
        'filelock==3.12.4',
        'pydantic-settings',
        'python-multipart',
    ],
    'builder': [
        'pyyaml',
        'typer',
    ],
    'authzero': [
        'niquests',
        'tldextract',
        'fastapi',
        'pycryptodomex',
        'pyjwt[crypto]',
        'python-jose',
    ],
    'openai': [
        'httpx',
        'backoff',
        'tiktoken',
        'jinja2',
        'pyyaml',
        'numpy',
        'scipy',
    ],
    'fileio': [
        "botocore == 1.29.76",
        "urllib3 < 2",
        "aiobotocore == 2.5.0",
        "s3fs == 2023.6.0",
        "boto3 == 1.26.76",
        "fsspec == 2023.6.0",
        "s3transfer == 0.6.1",
        "python-magic",
        "aiopath",
        "aiofiles",
        "aiofile",
    ],
}
args = {
    'package_dir': {'': 'src'},
    'py_modules': [pkg_name, 'lzl', 'lzo'],
    'packages': find_packages(
        "src",
    ),
    # 'packages': find_packages(include = [f'{pkg_name}', f'{pkg_name}.*',]),
    'install_requires': requirements,
    'include_package_data': True,
    'long_description': root.joinpath('README.md').read_text(encoding='utf-8'),
    'entry_points': {
        "console_scripts": [
            'lazyops-build = lazyops.libs.abc.builder:main',
            'lzl = lzl.cmd:main'
        ]
    },
    'extras_require': extras,
}

setup(
    name = pkg_name,
    version = version,
    url=f'https://github.com/{gitrepo}',
    license='MIT License',
    description='A collection of submodules/patterns that are commonly used within Internal Development',
    author='Tri Songz',
    author_email='ts@songzcorp.com',
    long_description_content_type="text/markdown",
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.9',
        'Topic :: Software Development :: Libraries',
    ],
    **args
)


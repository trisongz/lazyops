import sys
from pathlib import Path
from setuptools import setup, find_packages

if sys.version_info.major != 3:
    raise RuntimeError("This package requires Python 3+")

pkg_name = 'lazyops'
gitrepo = 'trisongz/lazyops'

root = Path(__file__).parent
version = root.joinpath(f'{pkg_name}/version.py').read_text().split('VERSION = ', 1)[-1].strip().replace('-', '').replace("'", '')

requirements = [
    'loguru',
    'pydantic',
    # 'pydantic-settings',
    'frozendict',
    'async_lru',
]

if sys.version_info.minor < 8:
    requirements.append('typing_extensions')

extras = {
    'kops': [
        'kubernetes',
        'kubernetes_asyncio',
        'kopf',
        'aiocache',
        # 'kr8s',
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
    ]
}
args = {
    'packages': find_packages(include = [f'{pkg_name}', f'{pkg_name}.*',]),
    'install_requires': requirements,
    'include_package_data': True,
    'long_description': root.joinpath('README.md').read_text(encoding='utf-8'),
    'entry_points': {
        "console_scripts": [
            'lazyops-build = lazyops.libs.abc.builder:main',
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
    author_email='ts@growthengineai.com',
    long_description_content_type="text/markdown",
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development :: Libraries',
    ],
    **args
)


import pytest
from pathlib import Path

try:
    from pydantic.networks import MultiHostUrl  # noqa: F401
except ImportError:  # pragma: no cover - environment without MultiHostUrl support
    pytest.skip(
        "pydantic.networks.MultiHostUrl not available; database config tests require it",
        allow_module_level=True,
    )

from lzl.db.backends import ADAPTER_TO_BACKENDS, ADAPTER_TO_MANAGER
from lzl.db.configs import ADAPTER_TO_CONFIG, ADAPTER_TO_SETTINGS
from lzl.db.sqlite.backend import SQLAlchemyBackend, SqliteBackendMap
from lzl.db.sqlite.config import SqliteConfig, SqliteSettings
from lzl.db.sqlite.manager import SqliteBackendManager


def test_adapter_config_registry_contains_sqlite() -> None:
    assert ADAPTER_TO_CONFIG['sqlite'] is SqliteConfig
    assert ADAPTER_TO_SETTINGS['sqlite'] is SqliteSettings


def test_adapter_backend_registry_contains_sqlalchemy() -> None:
    sqlite_backends = ADAPTER_TO_BACKENDS['sqlite']
    assert sqlite_backends['sqlalchemy'] is SQLAlchemyBackend
    assert ADAPTER_TO_MANAGER['sqlite'] is SqliteBackendManager


@pytest.mark.parametrize('adapter', ['sqlalchemy', 'sqlmodel'])
def test_sqlite_backend_map_matches_registry(adapter: str) -> None:
    assert SqliteBackendMap[adapter] is ADAPTER_TO_BACKENDS['sqlite'][adapter]


def test_sqlite_config_engine_kwargs(tmp_path: Path) -> None:
    database_path = tmp_path / 'example.sqlite'
    config = SqliteConfig(url=f'sqlite:///{database_path}')

    engine_kwargs = config.get_engine_kwargs()

    assert engine_kwargs['url'].startswith('sqlite')
    assert database_path.name in engine_kwargs['url']

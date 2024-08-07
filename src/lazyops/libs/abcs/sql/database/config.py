from __future__ import annotations


import os
import pathlib
from pydantic_settings import BaseSettings
from pydantic import model_validator, computed_field, PrivateAttr
from pydantic.networks import PostgresDsn
from lazyops.libs.abcs.configs.types import AppEnv
from lazyops.utils.logs import logger
from typing import List, Optional, Dict, Any, Union

def construct_pg_urls(
    config: Dict[str, Dict[str, Union[str, Dict[str, str]]]],
    env_name: Optional[str] = 'local',
    in_cluster: bool = False,
) -> Dict[str, str]:
    """
    Constructs the Postgres URLs
    
    Function to transform
    users:
        production: user:...
        development: user_development:...
        staging: user_staging:...
        local: user_local:...
        superuser: postgres:...
    database: app
    adapter: postgresql+asyncpg
    endpoints:
        public: appdb.com:5432
        cluster:
            rw: appdb-v1-cluster-rw.db.svc.cluster.local:5432
            ro: appdb-v1-cluster-ro.db.svc.cluster.local:5432
            prw: appdb-v1-cluster-pooler-rw.db.svc.cluster.local:5432
            pro: appdb-v1-cluster-pooler-ro.db.svc.cluster.local:5432

    to (Public)

    url: postgresql://user:...@appdb.com:5432/app
    superuser_url: postgresql://postgres:...@appdb.com:5432/app

    to (Cluster)

    url: postgresql://user:...@appdb-v1-cluster-pooler-rw.db.svc.cluster.local:5432/app
    readonly_url: postgresql://user:...@appdb-v1-cluster-pooler-ro.db.svc.cluster.local:5432/app
    superuser_url: postgresql://postgres:...@appdb-v1-cluster-rw.db.svc.cluster.local:5432/app
    """
    uri_base = f'{config.get("adapter", "postgresql+asyncpg")}://'
    db = config['database']
    results = {}
    if user := config['users'].get(env_name):
        user_uri_base = f'{uri_base}{user}'
        if in_cluster:
            cluster_eps = config['endpoints']['cluster']
            if cluster_eps.get('prw'):
                results['url'] = f'{user_uri_base}@{cluster_eps["prw"]}/{db}'
            elif cluster_eps.get('rw'):
                results['url'] = f'{user_uri_base}@{cluster_eps["rw"]}/{db}'
            
            if cluster_eps.get('pro'):
                results['readonly_url'] = f'{user_uri_base}@{cluster_eps["pro"]}/{db}'
            elif cluster_eps.get('ro'):
                results['readonly_url'] = f'{user_uri_base}@{cluster_eps["ro"]}/{db}'
        else:
            results['url'] = f'{user_uri_base}@{config["endpoints"]["public"]}/{db}'
    
    if superuser := config['users'].get('superuser'):
        superuser_uri_base = f'{uri_base}{superuser}'
        if in_cluster:
            cluster_eps = config['endpoints']['cluster']
            if cluster_eps.get('rw'):
                results['superuser_url'] = f'{superuser_uri_base}@{cluster_eps["rw"]}/{db}'
            elif cluster_eps.get('prw'):
                results['superuser_url'] = f'{superuser_uri_base}@{cluster_eps["prw"]}/{db}'
        else:
            results['superuser_url'] = f'{superuser_uri_base}@{config["endpoints"]["public"]}/{db}'
    return results




class PostgresSettings(BaseSettings):
    """
    The Postgres Settings
    """
    url: Optional[PostgresDsn] = None
    readonly_url: Optional[PostgresDsn] = None
    superuser_url: Optional[PostgresDsn] = None
    migration_env: Optional[Union[AppEnv, str]] = None
    target_env: Optional[Union[AppEnv, str]] = None

    _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)

    class Config:
        env_prefix = "POSTGRES_"

    @classmethod
    def get_pg_config_file_env_var(cls, **kwargs) -> str:
        """
        Returns the Postgres Config File Environment Variable
        """
        return None
    
    @classmethod
    def get_pg_app_name(cls, **kwargs) -> str:
        """
        Returns the Postgres App Name
        """
        return None

    @property
    def env_prefix_value(self) -> str:
        """
        Returns the env prefix value
        """
        if 'env_prefix_value' not in self._extra:
            self._extra['env_prefix_value'] = self.Config.env_prefix.lower().rstrip('_')
        return self._extra['env_prefix_value']
    
    @computed_field
    @property
    def url_username(self) -> Optional[str]:
        """
        The Username
        """
        return self.url.hosts()[0]['username']

    @computed_field
    @property
    def url_password(self) -> Optional[str]:
        """
        The Password
        """
        if ':' in str(self.url) and '@' in str(self.url):
            return str(self.url).split('@')[0].split(':')[-1]
        return None
    
    @computed_field
    @property
    def superuser_url_password(self) -> Optional[str]:
        """
        The Password
        """
        if not self.superuser_url: return None
        if ':' in str(self.superuser_url) and '@' in str(self.superuser_url):
            return str(self.superuser_url).split('@')[0].split(':')[-1]
        return None
    
    @computed_field
    @property
    def safe_url(self) -> Optional[str]:
        """
        The Password
        """
        if not self.url: return None
        return str(self.url).replace(self.url_password, '********')
    
    @computed_field
    @property
    def safe_superuser_url(self) -> Optional[str]:
        """
        The Password
        """
        if not self.superuser_url: return None
        return str(self.superuser_url).replace(self.superuser_url_password, '********')

    @computed_field
    @property
    def adapterless_url(self) -> str:
        """
        Returns the plain url with only postgres://
        """
        return 'postgres://' + str(self.url).split('://', 1)[-1].strip()
    

    @computed_field
    @property
    def adapterless_superuser_url(self) -> str:
        """
        Returns the plain url with only postgres://
        """
        return 'postgres://' + str(self.superuser_url).split('://', 1)[-1].strip()


    @computed_field
    @property
    def cli_connect_string(self) -> str:
        """
        Returns the cli connect string

        export PGPASSWORD=<password> psql -h <host> -p <port> -U <user> -d <database>
        """
        url = self.superuser_url or self.url
        url_data = url.hosts()[0]
        return f"export PGPASSWORD={url_data['password']} psql -h {url_data['host']} -p {url_data['port']} -U {url_data['username']} -d {url.path[1:]}"
    

    def has_logged_msg(self, msg: str) -> bool:
        """
        Checks if the message has been logged
        """
        return False

    def log_readonly_warning(self):
        """
        Logs the readonly warning
        """
        if not self.has_logged_msg(f'{self.env_prefix_value}_readonly_warning'):
            safe_url = str(self.url).replace(self.url_password, '********')  if self.url_password else str(self.url)
            logger.info(f'|y|Readonly URL not set|e|, using default URL: {safe_url}', colored = True, prefix = 'PostgresDB')

    def log_db_url(self):
        """
        Logs the Database URL
        """
        if not self.has_logged_msg(f'{self.env_prefix_value}_url'):
            safe_url = str(self.url).replace(self.url_password, '********')  if self.url_password else str(self.url)
            logger.info(f'Using URL: |g|{safe_url}|e|', colored = True, prefix = 'PostgresDB')

    
    # @model_validator(mode = 'after')
    # def post_init_validate(self):
    #     """
    #     Validate after
    #     """
    #     if not self.superuser_url:
    #         self.superuser_url = self.url
    #     if self.target_env and isinstance(self.target_env, str):
    #         self.target_env = AppEnv.from_env(self.target_env)
    #     if self.target_env: self.reconfigure(self.target_env)
    #     return self


    @classmethod
    def fetch_from_config_file(
        cls, 
        env_name: Optional[str] = None, 
        app_name: Optional[str] = None,
        config_file: Optional[Union[str, pathlib.Path]] = None,
        config_file_env_var: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the config from the config file
        """
        if not config_file:
            if not config_file_env_var: return
            config_file = os.getenv(config_file_env_var)
        config_file = pathlib.Path(config_file)
        if not config_file.exists(): return
        import yaml
        from lazyops.utils.system import is_in_kubernetes
        logger.info(f'Using Postgres Config File: {config_file}', colored = True, prefix = f'{app_name} - {env_name}')
        config_data: Dict[str, Dict[str, Dict[str, str]]] = yaml.safe_load(config_file.read_text())
        if app_name and not config_data.get(app_name): return
        return construct_pg_urls(
            config_data.get(app_name) if app_name else config_data,
            env_name = env_name,
            in_cluster = is_in_kubernetes(),
        )

from __future__ import annotations


import abc
import datetime
import typing as t

if t.TYPE_CHECKING:
    from lzl.types import AppEnv

def parse_db_config(
    config: t.Dict[str, t.Dict[str, t.Union[str, t.Dict[str, str]]]],
    env_name: t.Optional[t.Union[str, 'AppEnv']] = 'local',
    in_cluster: t.Optional[bool] = None,
    default_adapter: t.Optional[str] = 'postgresql+asyncpg',
    **kwargs,
) -> t.Dict[str, str]:
    """
    Constructs the Database URLs from a YAML Configuration
    
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
    if hasattr(env_name, 'name'): env_name = env_name.name
    if in_cluster is None:
        from lzo.utils.system import is_in_kubernetes
        in_cluster = is_in_kubernetes()
    
    uri_base = f'{config.get("adapter", default_adapter)}://'
    db = config['database']
    results = {}
    if user := config['users'].get(env_name):
        user_uri_base = f'{uri_base}{user}'
        if in_cluster:
            cluster_eps = config['endpoints']['cluster']
            if isinstance(cluster_eps, str): 
                results['url'] = f'{user_uri_base}@{cluster_eps}/{db}'
            
            else:
                if cluster_eps.get('prw'):
                    results['url'] = f'{user_uri_base}@{cluster_eps["prw"]}/{db}'
                elif cluster_eps.get('rw'):
                    results['url'] = f'{user_uri_base}@{cluster_eps["rw"]}/{db}'
                
                if cluster_eps.get('pro'):
                    results['readonly_url'] = f'{user_uri_base}@{cluster_eps["pro"]}/{db}'
                elif cluster_eps.get('ro'):
                    results['readonly_url'] = f'{user_uri_base}@{cluster_eps["ro"]}/{db}'
        
        elif isinstance(config['endpoints']['public'], dict):
            public_eps = config['endpoints']['public']
            if public_eps.get('prw'):
                results['url'] = f'{user_uri_base}@{public_eps["prw"]}/{db}'
            elif public_eps.get('rw'):
                results['url'] = f'{user_uri_base}@{public_eps["rw"]}/{db}'
            
            if public_eps.get('pro'):
                results['readonly_url'] = f'{user_uri_base}@{public_eps["pro"]}/{db}'
            elif public_eps.get('ro'):
                results['readonly_url'] = f'{user_uri_base}@{public_eps["ro"]}/{db}'
        
        else:
            results['url'] = f'{user_uri_base}@{config["endpoints"]["public"]}/{db}'
    
    if superuser := config['users'].get('superuser'):
        superuser_uri_base = f'{uri_base}{superuser}'
        if in_cluster:
            cluster_eps = config['endpoints']['cluster']
            if isinstance(cluster_eps, str):
                results['superuser_url'] = f'{superuser_uri_base}@{cluster_eps}/{db}'
            elif cluster_eps.get('rw'):
                results['superuser_url'] = f'{superuser_uri_base}@{cluster_eps["rw"]}/{db}'
            elif cluster_eps.get('prw'):
                results['superuser_url'] = f'{superuser_uri_base}@{cluster_eps["prw"]}/{db}'
        elif isinstance(config['endpoints']['public'], dict):
            public_eps = config['endpoints']['public']
            if public_eps.get('rw'):
                results['superuser_url'] = f'{superuser_uri_base}@{public_eps["rw"]}/{db}'
            elif public_eps.get('prw'):
                results['superuser_url'] = f'{superuser_uri_base}@{public_eps["prw"]}/{db}'
        else:
            results['superuser_url'] = f'{superuser_uri_base}@{config["endpoints"]["public"]}/{db}'
    return results



def build_sql_metadata_filter(
    table: str,
    conditional: t.Optional[str] = 'AND',
    metadata_key: t.Optional[str] = '_metadata',
    include_table_name: t.Optional[bool] = False,
    **filters: t.Dict[str, t.Union[int, float, datetime.datetime, t.Dict, t.List, t.Any]]
) -> str:
    """
    Constructs the WHERE clause for the `_metadata` property because it's a `jsonb` field
    """
    q = ""
    if include_table_name and table: metadata_key = f'{table}.{metadata_key}'
    for key, value in filters.items():
        if 'date' in key:
            # Handle dates
            if isinstance(value, list):
                # Handle date ranges
                if isinstance(value[0], datetime.datetime):
                    value[0] = value[0].strftime("%Y-%m-%d %H:%M:%S")
                    value[1] = value[1].strftime("%Y-%m-%d %H:%M:%S")
                q += f"jsonb_path_exists({metadata_key}, '$.{key} ? (@ BETWEEN {value[0]} AND {value[1]} || @ == null)' {conditional} "
            else:
                # Handle single dates
                op = '>' if key == "open_date" else '<='
                q += f"jsonb_path_exists({metadata_key}, '$.{key} ? (@ {op} {value} || @ == null)' {conditional} "
            continue

        # Handle Ints and Floats
        if isinstance(value, (int, float)):
            op = '>=' if 'min' in key else '<='
            q += f"jsonb_path_exists({metadata_key}, '$.{key} ? (@ {op} {value} || @ == null)' {conditional} "
            continue

        # Handle Strings
        if isinstance(value, str):
            q += f"jsonb_path_exists({metadata_key}, '$.{key} ? (@ ILIKE %'{value}'% || @ == null)' {conditional} "
            continue

        # Handle Lists
        if isinstance(value, list):
            q += f"jsonb_path_exists({metadata_key}, '$.{key} ? (@ && {value} || @ == null)' {conditional} "
            continue

        # Handle Dicts
        if isinstance(value, dict):
            q += f"jsonb_path_exists({metadata_key}, '$.{key} ? (@ ?& {value.keys()} || @ == null)' {conditional} "
            continue

    q = q[:-len(conditional)-1]
    return q


class SQLAlchemyUtilities(abc.ABC):
    """
    Abstract Base Class for SQLAlchemy Utilities
    """
    def __init__(self):
        """
        Initializes the SQLAlchemy Utilities
        """
        from sqlalchemy.orm import defer
        from sqlalchemy.sql.expression import (
            text, select, update, delete, 
            funcfilter, lambda_stmt, func, modifier, bindparam,
            exists, desc, asc, case, t.cast, literal, 
            collate, distinct, extract, false, null, nulls_first, nulls_last, true,
            over, between, lateral, try_cast, alias, type_coerce, within_group, 
            intersect, intersect_all, outerjoin, union, union_all, table, values,
            all_, and_, any_, not_, or_, tuple_, except_, except_all, 
        )
        from sqlalchemy.dialects.postgresql import insert, array_agg
        from sqlalchemy.orm import selectinload
        self.defer = defer
        self.text = text
        self.select = select
        self.update = update
        self.delete = delete
        self.funcfilter = funcfilter
        self.lambda_stmt = lambda_stmt
        self.func = func
        self.modifier = modifier
        self.bindparam = bindparam

        self.exists = exists
        self.desc = desc
        self.asc = asc
        self.case = case
        self.t.cast = t.cast
        self.literal = literal

        self.collate = collate
        self.distinct = distinct
        self.extract = extract
        self.false = false
        self.null = null
        self.nulls_first = nulls_first
        self.nulls_last = nulls_last
        self.true = true
        self.over = over
        self.between = between
        self.lateral = lateral
        self.try_cast = try_cast
        self.alias = alias
        self.type_coerce = type_coerce
        self.within_group = within_group

        self.intersect = intersect
        self.intersect_all = intersect_all
        self.outerjoin = outerjoin
        self.union = union
        self.union_all = union_all
        self.table = table
        self.values = values

        self.and_ = and_
        self.all_ = all_
        self.any_ = any_
        self.not_ = not_
        self.or_ = or_
        self.tuple_ = tuple_
        self.except_ = except_
        self.except_all = except_all

        self.select = select
        self.update = update
        self.delete = delete
        self.insert = insert
        self.selectinload = selectinload
        self.array_agg = array_agg
        self.postinit()

    def postinit(self):
        """
        Post Initialization
        """
        pass
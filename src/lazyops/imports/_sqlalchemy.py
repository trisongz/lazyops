
"""
Import Handler for sqlalchemy
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import sqlalchemy
    _sqlalchemy_available = True
except ImportError:
    sqlalchemy = object
    _sqlalchemy_available = False

try:
    import asyncpg
    _asyncpg_available = True
except ImportError:
    asyncpg = object
    _asyncpg_available = False

try:
    import psycopg2
    _psycopg2_available = True
except ImportError:
    psycopg2 = object
    _psycopg2_available = False

try:
    import sqlalchemy_json
    _sqlalchemy_json_available = True
except ImportError:
    sqlalchemy_json = object
    _sqlalchemy_json_available = False

def resolve_sqlalchemy(
    required: bool = False,
):
    """
    Ensures that `sqlalchemy` is available
    """
    global sqlalchemy, _sqlalchemy_available
    if not _sqlalchemy_available:
        resolve_missing('sqlalchemy', required = required)
        import sqlalchemy
        _sqlalchemy_available = True
        globals()['sqlalchemy'] = sqlalchemy

def resolve_asyncpg(
    required: bool = False,
):
    """
    Ensures that `asyncpg` is available
    """
    global asyncpg, _asyncpg_available
    if not _asyncpg_available:
        resolve_missing('asyncpg', required = required)
        import asyncpg
        _asyncpg_available = True
        globals()['asyncpg'] = asyncpg

def resolve_psycopg2(
    required: bool = False,
):
    """
    Ensures that `psycopg2` is available
    """
    global psycopg2, _psycopg2_available
    if not _psycopg2_available:
        resolve_missing('psycopg2', 'psycopg2-binary', required = required)
        import psycopg2
        _psycopg2_available = True
        globals()['psycopg2'] = psycopg2

def resolve_sqlalchemy_json(
    required: bool = False,
):
    """
    Ensures that `sqlalchemy_json` is available
    """
    global sqlalchemy_json, _sqlalchemy_json_available
    if not _sqlalchemy_json_available:
        resolve_missing('sqlalchemy_json', required = required)
        import sqlalchemy_json
        _sqlalchemy_json_available = True
        globals()['sqlalchemy_json'] = sqlalchemy_json

def require_sqlalchemy(
    required: bool = False,
):
    """
    Wrapper for `resolve_sqlalchemy` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_sqlalchemy, 
            func = func, 
            required = required
        )
    return decorator

def resolve_sql(
    required: bool = True,
    require_sqlalchemy: bool = True,
    require_psycopg2: bool = False,
    require_asyncpg: bool = False,
    require_sqlalchemy_json: bool = True,
):
    """
    Ensures that `sqlalchemy` is available
    """
    if require_sqlalchemy:
        resolve_sqlalchemy(required = required)
    if require_psycopg2:
        resolve_psycopg2(required = required)
    if require_asyncpg:
        resolve_asyncpg(required = required)
    if require_sqlalchemy_json:
        resolve_sqlalchemy_json(required = required)

def require_sql(
    required: bool = True,
    require_sqlalchemy: bool = True,
    require_psycopg2: bool = False,
    require_asyncpg: bool = False,
    require_sqlalchemy_json: bool = True,
):
    """
    Wrapper for `resolve_sqlalchemy` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_sql, 
            func = func, 
            required = required,
            require_sqlalchemy = require_sqlalchemy,
            require_psycopg2 = require_psycopg2,
            require_asyncpg = require_asyncpg,
            require_sqlalchemy_json = require_sqlalchemy_json,
        )
    return decorator
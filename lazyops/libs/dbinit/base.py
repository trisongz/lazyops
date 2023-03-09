from lazyops.imports._sqlalchemy import resolve_sqlalchemy

resolve_sqlalchemy(True)

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine.base import Engine
from sqlalchemy.engine.row import Row
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql.elements import TextClause
try:
    from sqlalchemy.orm.decl_api import DeclarativeBase
except ImportError:
    from sqlalchemy.orm.decl_api import DeclarativeMeta as DeclarativeBase
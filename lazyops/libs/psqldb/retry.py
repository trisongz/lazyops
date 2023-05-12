import time

from sqlalchemy import event
from sqlalchemy.engine.base import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from typing import Union, Optional

# https://docs.sqlalchemy.org/en/14/faq/connections.html#faq-execute-retry
# Retryable ReadOnly Event

def reconnecting_engine(
    engine: Union[Engine, AsyncEngine],
    num_retries: Optional[int] = 5, 
    retry_interval: Optional[float] = 10.0,
):
    def _run_with_retries(fn, context, cursor_obj, statement, *arg, **kw):
        for retry in range(num_retries + 1):
            try:
                fn(cursor_obj, statement, context=context, *arg)
            except engine.dialect.dbapi.Error as raw_dbapi_err:
                connection = context.root_connection
                if engine.dialect.is_disconnect(raw_dbapi_err, connection, cursor_obj):
                    if retry > num_retries:
                        raise
                    engine.logger.error(
                        "disconnection error, retrying operation",
                        exc_info=True,
                    )
                    connection.invalidate()

                    # use SQLAlchemy 2.0 API if available
                    if hasattr(connection, "rollback"):
                        connection.rollback()
                    else:
                        trans = connection.get_transaction()
                        if trans:
                            trans.rollback()

                    time.sleep(retry_interval)
                    context.cursor = cursor_obj = connection.connection.cursor()
                else:
                    raise
            else:
                return True
        
    
    e = engine.execution_options(isolation_level="AUTOCOMMIT")
    engine_obj = e if isinstance(engine, Engine) else e.sync_engine
    

    @event.listens_for(engine_obj, "do_execute_no_params")
    def do_execute_no_params(cursor_obj, statement, context):
        return _run_with_retries(
            context.dialect.do_execute_no_params, context, cursor_obj, statement
        )

    @event.listens_for(engine_obj, "do_execute")
    def do_execute(cursor_obj, statement, parameters, context):
        return _run_with_retries(
            context.dialect.do_execute, context, cursor_obj, statement, parameters
        )

    return e
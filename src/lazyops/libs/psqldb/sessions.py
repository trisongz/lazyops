from __future__ import annotations


# https://stackoverflow.com/questions/69483534/sqlalchemy-with-multiple-session-how-to-avoid-object-is-already-attached-to-se


import weakref
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext.asyncio import AsyncSession, async_object_session


class CarefulSession(orm.Session):

    def add(self, object_):
        # Get the session that contains the object, if there is one.
        object_session = orm.object_session(object_)
        if object_session and object_session is not self:
            # Remove the object from the other session, but keep
            # a reference so we can reinstate it.
            object_session.expunge(object_)
            object_._prev_session = weakref.ref(object_session)
        return super().add(object_)

class CarefulAsyncSession(AsyncSession):

    def add(self, object_):
        # Get the session that contains the object, if there is one.
        object_session = async_object_session(object_)
        if object_session and object_session is not self:
            # Remove the object from the other session, but keep
            # a reference so we can reinstate it.
            object_session.expunge(object_)
            object_._prev_session = weakref.ref(object_session)
        return super().add(object_)


# @sa.event.listens_for(CarefulAsyncSession.sync_session, 'after_commit')
def receive_after_commit(session):
    """Reinstate objects into their previous sessions."""
    objects = filter(lambda o: hasattr(o, '_prev_session'), session.identity_map.values())
    for object_ in objects:
        prev_session = object_._prev_session()
        if prev_session:
            session.expunge(object_)
            prev_session.add(object_)
            delattr(object_, '_prev_session')

def receive_after_commit_orm(session):
    """
    Reinstate objects into their previous sessions.

    - This assumes that the object has a `_prev_session` attribute
    """
    objects = filter(lambda o: o._prev_session, session.identity_map.values())
    for object_ in objects:
        prev_session = object_._prev_session()
        if prev_session:
            session.expunge(object_)
            prev_session.add(object_)
            object_._prev_session = None
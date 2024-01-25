from __future__ import annotations

"""
Extra Helper Types
"""

import threading

class Singleton(object):
    
    """
    This is a singleton that is not locked to a single thread
    """

    __instance = None

    def __new__(cls):
        """
        If the instance is not created, then create it
        """
        if cls.__instance is None:
            cls.__instance = super(Singleton, cls).__new__(cls)
        return cls.__instance


class LockedSingleton(object):

    """
    This is a singleton that is locked to a single thread
    """
    __instance = None
    __instance_lock = threading.RLock()

    def __new__(cls):
        """
        If the instance is not created, then create it
        """
        if cls.__instance is None:
            with cls.__instance_lock:
                cls.__instance = super(LockedSingleton, cls).__new__(cls)
        return cls.__instance


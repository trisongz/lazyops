from __future__ import annotations

"""Singleton helpers used by LazyOps proxy abstractions."""

import threading
import typing as t


class Singleton:
    """Basic singleton that is safe for single-threaded initialisation."""

    __instance: t.ClassVar["Singleton | None"] = None

    def __new__(cls) -> "Singleton":  # type: ignore[override]
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance


class LockedSingleton:
    """Singleton protected by a re-entrant lock for multi-thread scenarios."""

    __instance: t.ClassVar["LockedSingleton | None"] = None
    __instance_lock: t.ClassVar[threading.RLock] = threading.RLock()

    def __new__(cls) -> "LockedSingleton":  # type: ignore[override]
        if cls.__instance is None:
            with cls.__instance_lock:
                if cls.__instance is None:
                    cls.__instance = super().__new__(cls)
        return cls.__instance


__all__ = ["Singleton", "LockedSingleton"]

from __future__ import annotations

"""
Implements Dynamic Class Registration from this code snippet

https://dev.to/konstantinos_andreou_4dc1/tutorial-dynamic-class-discovery-and-loading-in-python-5dh8
"""

import os
import importlib
import typing as t
from lzl.logging import logger

T = t.TypeVar("T")

class BaseDynamicLoader:
    MODULE: str

    def __init__(self, class_to_find: T):
        self.module = importlib.import_module(self.MODULE)
        self.class_to_find = class_to_find
        self._found_classes = self.__dynamic_class_loader()

    def __dynamic_class_loader(self) -> t.Dict[str, T]:
        """
        Dynamically load all classes from the module.
        """
        found_classes: t.Dict[str, T] = {}
        logger.info(
            f"Loading {self.class_to_find.__name__} classes from <{self.MODULE}>",
            prefix = self.__class__.__name__
        )
        root_dir = self.module.__path__[0]
        for root, _, files in os.walk(root_dir):
            for file in files:
                # Check if the file is a Python file and not a special file
                if file.endswith(".py") and not file.startswith("__"):
                    mod_name = os.path.splitext(file)[0]
                    module = importlib.import_module(f"{self.MODULE}.{mod_name}")
                    for cls in dir(module):
                        # Check if the class is a subclass of class_to_find
                        if (
                            isinstance(getattr(module, cls), type)
                            and issubclass(getattr(module, cls), self.class_to_find)
                            and getattr(module, cls) is not self.class_to_find
                        ):
                            # Check if the class is a class_to_find
                            logger.info(
                                f"Found {self.class_to_find.__name__} class <{cls}> in <{file}>",
                                prefix = self.__class__.__name__
                            )
                            found_classes[cls] = getattr(module, cls)
        return found_classes
from __future__ import annotations

"""
Basic Ktrl Setup


import pathlib
from lazyops.libs.ktrl.base import *

class Settings(KtrlSettings):
    ...

    
class MyResource(
    Resource,
    kind = 'MyResource',
    group = 'my.group',
    version = 'v1',
    scope = 'Namespaced',
    status_subresource = True,
    plural = 'myresources',
):
    spec: Spec
    

here = pathlib.Path(__file__).parent
settings = Settings()
settings.set_jinja_templates(here.joinpath('templates'))

class Controller(BaseKtrl):
    APP_NAME = 'myapp'
    CRD_OBJECT = MyResource

engine = Controller()

"""

# This module is meant to provide a easy import-all to basic modules.

from pydantic import BaseModel, Field, model_validator
from lazyops.libs.kopf_resources import Resource, Spec, Status

from .config import KtrlSettings
from .patches import kopf
from .models import BaseKtrl


# `lzo.types`

This package re-exports a curated subset of LazyOps' pydantic wrappers so
applications can opt-in to the enhanced models without pulling in the full
`lzl` surface.  `BaseModel` mirrors `pydantic.BaseModel` but allows arbitrary
extra fields, while `BaseSettings` layers on helpers for environment detection
and logging conveniences.

```python
from lzo.types import BaseSettings, AppEnv

class ExampleSettings(BaseSettings):
    name: str
    debug_enabled: bool = True

settings = ExampleSettings(app_env='development', name='demo')
assert settings.app_env == AppEnv.DEVELOPMENT
```

Where possible the module re-exports typing utilities (`field_validator`,
`model_validator`, etc.) so consumers have a single import location for
annotating new models.

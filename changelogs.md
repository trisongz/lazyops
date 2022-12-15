## v0.2.2 - Last Updated: Dec 14, 2022
- Minor formatting tweaks to logging events
- Add new helper methods to `lazyops.types.models.BaseModel`
- add convenience default `BaseSettings` for cloud providers:
    - Boto: `lazyops.configs.cloud.BotoSettings`
    - AWS: `lazyops.configs.cloud.AwsSettings`
    - GCP: `lazyops.configs.cloud.GcpSettings`
- add a few import helpers to `lazyops.imports`
    - `aiohttpx` - `lazyops.imports._aiohttpx` 
    - `fileio` - `lazyops.imports._fileio`


## v0.2.1 - Last Updated: Dec 14, 2022
- Moved JSON serialization out of `lazyops.utils.helpers` -> `lazyops.utils.serialization`
 - reimported into `lazyops.utils.helpers` to maintain backwards compatibility


## v0.2.0 - Last Updated: Dec 12, 2022
- Refactor entire codebase to support new APIs
- `lazyops.LazyLib` - Lazy Dependency Import Helper
- `lazyops.imports` - Subclass of `LazyLib` for importing dependencies
- `lazyops.types` - Common pattern of Types that are used
- migrate to use `loguru` as default logger.
- drop all dependencies except for `pydantic` and `loguru`


## v0.1.0 - Last Updated: Aug 5, 2021
- Final release of LazyOps v0.1.0


## v0.0.9 - Aug 5, 2021
- Modifications to LazyRPC
- Lots of other fun stuff.

## v0.0.81 - July 28, 2021

- Add API for LazyHFModel
- Hotfix for importing LazyHFModel
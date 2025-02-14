## v0.3.0rc01 - Last Updated: Nov 22, 2024

This is a major release that includes a lot of new features.

`lazyops` is remains for compatability, but will no longer be maintained.

Going forward, the library is split into two parts:

- `lzl` - Seperate, independent modules that can be imported and used independently

- `lzo` - A collection of submodules/patterns that are commonly used within Internal Development

This is under beta development and is not yet ready for production use.

The minimum python version is now 3.9.

## v0.2.85 - Last Updated: Feb 23, 2023

- Added New Library: `hatchet`
  
  Builds on top of `hatchet_sdk` to make building workflows easier.

- Added New Library: `kinde`

  Builds on top of `kinde_sdk` to make integration with fastapi easier.


## v0.2.24 - Last Updated: Feb 23, 2023
- Resolve Async issues with `timed_cache` to resolve properly.
  - added `async_lru` as a dependency


## v0.2.15 - Last Updated: Feb 3, 2023
- Add additional utils
  - `lazyops.utils.helpers.import_function`
  - `lazyops.utils.helpers.create_timestamp`
  - `lazyops.utils.helpers.create_unique_id`
  - `lazyops.utils.helpers.create_secret`
  - `lazyops.utils.helpers.fetch_property`

- Add logger modification methods
  - `lazyops.utils.logs.change_logger_level`
  - `lazyops.utils.logs.add_api_log_filters`

- Add `lazyops.libs.asyncz` module

## v0.2.7-8 - Last Updated: Jan 4, 2023
- Add some validation checks to `lazyops.configs.base.DefaultSettings`

## v0.2.5-6 - Last Updated: Dec 21, 2022
- Minor hotfixes

## v0.2.4 - Last Updated: Dec 15, 2022
- Hotfix to resolve issues with logging
- Added additional config options
  - `lazyops.configs.k8s.K8sSettings`
  - `lazyops.configs.base.DefaultSettings`
- Added additional import helpers
  - `lazyops.imports._aiokeydb`
  - `lazyops.imports._psutil`
  - `lazyops.imports._torch`
  - `lazyops.imports._k8s`
  - `lazyops.imports._transformers`


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
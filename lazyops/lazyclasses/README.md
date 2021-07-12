# LazyClasses

Borrowed from [fastclasses-json](https://github.com/cakemanny/fastclasses-json), inspired by heavy usage of [dataclasses-json](https://github.com/lidatong/dataclasses-json).

Differences:
- Borrows fastclasses-json's JIT serialization method
- Utilizes pysimdjson's JIT parser for faster serialization/decoding to maximize performance.
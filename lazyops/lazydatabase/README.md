# LazyDB

A fast, async-ish, jsonrpc db, with persistance on disk with Dynamic Schema Creation.

Because I don't do well with ORM DBs.

## Quick Benchmarks

**LazyRPC + LazyDB**

- 50k GET Requests: 30.9 secs from single thread async aiohttp session

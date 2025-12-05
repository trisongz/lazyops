---
hide:
  - navigation
---

# LazyOps

<div align="center">
  <img src="https://raw.githubusercontent.com/trisongz/lazyops/main/docs/assets/logo.png" alt="LazyOps Logo" width="200" style="display: none;">
  
  <p class="description" style="font-size: 1.2rem; max-width: 800px; margin: 0 auto;">
    <b>High-performance, async-native tooling for modern Python applications.</b><br>
    Split into zero-dependency core utilities (<code>lzl</code>) and powerful registry patterns (<code>lzo</code>).
  </p>

  <p align="center" style="margin-top: 20px;">
    <a href="https://pypi.org/project/lazyops/" target="_blank">
        <img src="https://img.shields.io/pypi/v/lazyops?color=%2334D058&label=pypi%20package" alt="Package version">
    </a>
    <a href="https://pypi.org/project/lazyops/" target="_blank">
        <img src="https://img.shields.io/pypi/pyversions/lazyops.svg?color=%2334D058" alt="Supported Python versions">
    </a>
  </p>
</div>

---

## **Installation**

<div class="termy">

```console
$ pip install lazyops
```

</div>

## **At a Glance**

LazyOps is designed to make Python development faster and cleaner by providing robust utilities that handle the "boring stuff" efficiently. It is divided into two primary namespaces:

<div class="grid cards" markdown>

-   :material-feather:{ .lg .middle } __lzl__

    ---

    **Lazy Libraries & Utilities**
    
    A zero-dependency collection of core components. Think of it as `itertools` + `functools` + `asyncio` helpers on steroids.
    
    [:octicons-arrow-right-24: Explore lzl](api/lzl/index.md)

-   :material-layers-triple:{ .lg .middle } __lzo__

    ---

    **Lazy Objects & Registries**
    
    Advanced patterns for state management, object registries, and configuration. Built for scalable application architecture.
    
    [:octicons-arrow-right-24: Explore lzo](api/lzo/index.md)

</div>

---

## **Flash Examples**

See how **LazyOps** simplifies common patterns.

=== "Lazy Loading"

    Drastically reduce import times by loading heavy modules only when accessed.

    ```python
    from lzl.load import LazyLoad
    
    # pandas is not imported yet!
    pd = LazyLoad("pandas")
    
    def analyze_data(data):
        # pandas is imported here, on first access
        df = pd.DataFrame(data)
        return df.describe()
    ```

=== "Async IO"

    Unified, high-performance file operations that work across local and cloud storage.

    ```python
    from lzl.io import File
    
    async def process_logs():
        # Works with local paths, S3, MinIO, etc.
        logs = await File("s3://my-bucket/app.log").read_text()
        
        # Non-blocking write
        await File("local/processed.log").write_text(logs)
        
    # Check sizes easily
    size = File("s3://my-bucket/large-dataset.parquet").size
    ```

=== "Robust Logging"

    Zero-config, high-performance structured logging based on `loguru`.

    ```python
    from lzl.logging import logger
    
    # Automatically formatted, colored, and timestamped
    logger.info("Application starting up...", env="production")
    
    try:
        1 / 0
    except Exception:
        # localized tracebacks
        logger.trace("Something went wrong", error_code=500)
    ```

=== "Smart Registry"

    Build plugin systems or manage global components with `MRegistry`.

    ```python
    from lzo.registry import MRegistry
    
    # Create a registry for your AI Models
    Models = MRegistry("models")
    
    @Models.register("gpt-4")
    class GPT4:
        def generate(self): ...
            
    # Lazy instantiation
    model = Models.get("gpt-4")
    ```

=== "API Clients"

    Pre-configured clients for popular services like OpenAI, Slack, and Kubernetes.

    ```python
    from lzl.api import aiohttpx
    
    async def fetch_data():
        # A robust, async HTTP client with retries and timeout logic built-in
        async with aiohttpx.Client() as client:
            resp = await client.get("https://api.example.com/data")
            return resp.json()
    ```

---

## **Why LazyOps?**

<div class="grid cards" markdown>

-   __Async Native__
    
    Built from the ground up for `asyncio`. Almost every I/O operation has a non-blocking `await` equivalent, ensuring your event loop never stalls.

-   __Zero Overhead__
    
    The `lzl` core is designed to be lightweight. You import only what you use, and lazy loading ensures you don't pay for dependencies you don't need.

-   __Developer Experience__
    
    Fully typed with `mypy` support, comprehensive docstrings, and intuitive APIs. We prioritize readability and ease of use.

-   __Production Ready__
    
    Used in production environments handling high-throughput data processing and microservices orchestration.

</div>

## **Next Steps**

* [Get Started with lzl Utilities](api/lzl/index.md)
* [Learn about lzo Registries](api/lzo/index.md)
* [View Extension Modules](api/lzl/ext.md)
from __future__ import annotations

"""
Extra Helpers
"""
import functools
import typing as t
import urllib.request
import shutil
from lzl import load
from concurrent.futures import ThreadPoolExecutor, as_completed

if load.TYPE_CHECKING:
    import browserforge.download
    from lzl.api import aiohttpx
else:
    browserforge = load.LazyLoad("browserforge", install_missing=True)
    aiohttpx = load.lazy_load('lzl.api.aiohttpx', install_missing = False)


def download_file(url: str, path: str) -> None:
    """
    Download a file from the specified URL and save it to the given path.
    """
    with urllib.request.urlopen(url) as resp:  # nosec
        if resp.status != 200:
            raise ValueError(f"Download failed with status code: {resp.status}")
        with open(path, "wb") as f:
            shutil.copyfileobj(resp, f)

@functools.lru_cache()
def browserforge_download(
    headers: t.Optional[bool] = True,
    fingerprints: t.Optional[bool] = True,
):
    """
    Returns the browser forge downloader
    """
    browserforge.__load__()
    from lzl.logging import logger
    try:
        from browserforge.download import is_downloaded
        if is_downloaded(headers = headers, fingerprints = fingerprints):
            return True
    except ImportError:
        from browserforge.download import IsDownloaded
        try:
            if IsDownloaded(): return True
        except Exception as e:
            logger.error(f'Error checking if downloaded: {e}')
            try:
                from browserforge.download import get_all_paths
            except ImportError:
                from browserforge.download import _get_all_paths as get_all_paths
            def _IsDownloaded() -> bool:
                """
                Check if the required data files are already downloaded.
                Returns True if all the requested data files are present, False otherwise.
                """
                for path in get_all_paths():
                    if not path.exists():
                        return False
                return True
            
            if _IsDownloaded(): return True


    from browserforge.download import (
        ROOT_DIR,
        DATA_DIRS,
        DATA_FILES,
        REMOTE_PATHS,
    )
    futures = {}
    options = {'headers': headers, 'fingerprints': fingerprints}
    options = {k: v for k, v in options.items() if v}
    with ThreadPoolExecutor(10) as executor:
        for data_type in options:
            for local_name, remote_name in DATA_FILES[data_type].items():
                url = f"{REMOTE_PATHS[data_type]}/{remote_name}"
                path = str(DATA_DIRS[data_type] / local_name)
                future = executor.submit(download_file, url, path)
                futures[future] = local_name
        for f in as_completed(futures):
            try:
                future.result()
                logger.info(f"{futures[f]:<30}OK!")
            except Exception as e:
                logger.warning(f"Error downloading {local_name}: {e}")




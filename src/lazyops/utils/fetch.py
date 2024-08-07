"""
Retrieval Utilities
"""

import os
import re
import base64
import requests
import json
import functools
import contextlib
from pathlib import Path
from typing import Optional, Union, Tuple, List, Dict, Any, TYPE_CHECKING
from lazyops.utils.logs import logger
from lazyops.types import BaseModel, lazyproperty, Literal
from pydantic.types import ByteSize


with contextlib.suppress(ImportError):
    from tqdm.auto import tqdm as base_tqdm

user_home = Path(os.path.expanduser("~"))



"""
HuggingFace Utilities
"""


def get_huggingface_token(
    raise_error: Optional[bool] = False,
) -> Optional[str]:
    """
    Gets the HuggingFace API token
    """
    # check env first
    for key in {'HF_TOKEN', 'HUGGINGFACE_TOKEN', 'HUGGINGFACE_API_TOKEN'}:
        if key in os.environ:
            return os.environ[key]
    
    token_path = user_home.joinpath(".huggingface/token")
    if token_path.exists():
        with open(token_path, 'r') as f:
            return f.read().strip()
    
    if raise_error:
        raise ValueError("HuggingFace API token not found. Please run `huggingface-cli login` to login.")
    return None


def sanitize_branch_name(branch_name: str):
    pattern = re.compile(r"^[a-zA-Z0-9._-]+$")
    if pattern.match(branch_name):
        return branch_name
    raise ValueError("Invalid branch name. Only alphanumeric characters, period, underscore and dash are allowed.")

re_patterns = {
    'adapter': re.compile(r"adapter.*\.bin"),
    'pytorch': re.compile(r".*\.pt"),
    'pytorch_model': re.compile(r"(pytorch|adapter)_model.*\.bin"),
    'safetensors': re.compile(r"model.*\.safetensors"),
    'ggml': re.compile(r".*\.ggml.*\.bin"),
    'tensorflow': re.compile(r".*\.(tf|h5)"),
    'tokenizer': re.compile(r"(tokenizer|special_tokens_map|spiece).*\.(json|model)"),
    'text': re.compile(r".*\.(txt|json|py|md)"),
    'config': re.compile(r".*\.json"),
    'flax': re.compile(r"flax*"),
}
reg_patterns = {
    'adapter': ["adapter*.bin"],
    'pytorch': ["*.pt", 'pytorch*.bin'],
    'safetensors': ["*.safetensors"],
    'ggml': ["*ggml*.bin"],
    'tensorflow': ["*.h5", "*.tf"],
    'tokenizer': ["tokenizer*.json", "special_tokens_map*.json", "spiece*.model"],
    'text': ["*.txt", "*.json", "*.py", "*.md"],
    'config': ["*.json"],
    'flax': ["flax*."],
}

# re_compile_patterns = {
#     key: re.compile(value) for key, value in re_patterns.items()
# }

class HFLink(BaseModel):
    url: str
    filename: str
    size: ByteSize

    @lazyproperty
    def is_pytorch_model(self):
        return bool(re_patterns['pytorch_model'].match(self.filename))
    
    @lazyproperty
    def is_safetensors(self):
        return bool(re_patterns['safetensors'].match(self.filename))
    
    @lazyproperty
    def is_pytorch(self):
        return bool(re_patterns['pytorch'].match(self.filename))
    
    @lazyproperty
    def is_tensorflow(self):
        return bool(re_patterns['tensorflow'].match(self.filename))
    
    @lazyproperty
    def is_tokenizer(self):
        return bool(re_patterns['tokenizer'].match(self.filename))
    
    @lazyproperty
    def is_text(self):
        return bool(re_patterns['text'].match(self.filename))
    
    @lazyproperty
    def is_lora(self):
        return self.filename.endswith(('adapter_config.json', 'adapter_model.bin'))
    
    @lazyproperty
    def is_config(self):
        return bool(re_patterns['config'].match(self.filename))

class HFLinks(BaseModel):
    repo_id: str
    repo_type: str
    revision: str

    links: List[HFLink] = []

    @lazyproperty
    def is_lora(self):
        return any(link.is_lora for link in self.links)

    @lazyproperty
    def lora_links(self):
        return [link for link in self.links if link.is_lora]

    @lazyproperty
    def pytorch_links(self):
        return [link for link in self.links if link.is_pytorch]
    
    @lazyproperty
    def pytorch_model_links(self):
        return [link for link in self.links if link.is_pytorch_model]
    
    @lazyproperty
    def safetensors_links(self):
        return [link for link in self.links if link.is_safetensors]
    
    @lazyproperty
    def tensorflow_links(self):
        return [link for link in self.links if link.is_tensorflow]
    
    @lazyproperty
    def config_links(self):
        return [link for link in self.links if link.is_config and not link.is_tokenizer]

    @lazyproperty
    def tokenizer_links(self):
        return [link for link in self.links if link.is_tokenizer]
    
    @lazyproperty
    def text_links(self):
        return [link for link in self.links if link.is_text and not link.is_tokenizer and not link.is_config]
    
    @lazyproperty
    def classifications(self) -> List[str]:
        res = []
        if self.lora_links:
            res.append('lora')
        if self.pytorch_model_links or self.pytorch_links:
            res.append('pytorch')
        if self.tensorflow_links:
            res.append('tensorflow')
        if self.safetensors_links:
            res.append('safetensors')
        return res


    def __len__(self):
        return len(self.links)
    
    def __getitem__(self, idx: Union[str, int]) -> Union[List[HFLink], HFLink]:
        """
        Returns the link at the given index or by the type
        """
        if isinstance(idx, int):
            return self.links[idx]
        if hasattr(self, f"{idx}_links"):
            return getattr(self, f"{idx}_links")
        # assume its a filename
        for link in self.links:
            if link.filename == idx:
                return link
        raise KeyError(f"Link with filename `{idx}` not found.")

@functools.lru_cache(maxsize=128)
def get_download_links_from_huggingface(
    repo_id: str,
    revision: Optional[str] = None,
    repo_type: Optional[str] = None,
    auth_token: Optional[Union[str, bool]] = True,
) -> HFLinks:
    """
    Retrieves the download links for a given `repo_id`.

    Args:
        repo_id (`str`):
            The ID of the repo on huggingface.co.
        revision (`str`, *optional*):
            The specific model version to use. Will default to `"main"` if it's not provided and no `commit_hash` is
            provided either.
        repo_type (`str`, *optional*):
            The type of the repository. Will default to `"models"`.
        auth_token (Union[`str`, `bool`, *optional*):
            The HuggingFace API token to use. 
            If `False`, will not use any token. If `None`, will try to get the token.
            If `True`, will try to get the token if found.
            If a string, will use that as the token.
    
    """
    if revision is None: revision = "main"
    if repo_type is None: repo_type = "models"

    repo_links = HFLinks(repo_id=repo_id, repo_type=repo_type, revision=revision)
    base = "https://huggingface.co"
    page = f"/api/{repo_type}/{repo_id}/tree/{revision}"
    cursor = b""

    headers = {}
    if auth_token:
        if isinstance(auth_token, str):
            headers['authorization'] = f'Bearer {auth_token}'
        elif auth_token is True:
            headers['authorization'] = f'Bearer {get_huggingface_token(False)}'

    while True:
        content = requests.get(
            f"{base}{page}",
            headers = headers,
            params = {'cursor': cursor.decode()} if cursor else None
        ).content
        data = json.loads(content)
        if len(data) == 0: break
        for i in range(len(data)):
            filename = data[i]['path']
            repo_links.links.append(
                HFLink(
                    url = f"https://huggingface.co/{repo_id}/resolve/{revision}/{filename}",
                    filename = filename,
                    size = data[i]['size'],
                )
            )
        
        cursor = base64.b64encode(f'{{"file_name":"{data[-1]["path"]}"}}'.encode()) + b':50'
        cursor = base64.b64encode(cursor)
        cursor = cursor.replace(b'=', b'%3D')

    return repo_links

"""
Forked from huggingface hub to ensure multithreading
"""

def snapshot_download(
    repo_id: str,
    *,
    revision: Optional[str] = None,
    repo_type: Optional[str] = None,
    cache_dir: Union[str, Path, None] = None,
    local_dir: Union[str, Path, None] = None,
    local_dir_use_symlinks: Union[bool, Literal["auto"]] = "auto",
    library_name: Optional[str] = None,
    library_version: Optional[str] = None,
    user_agent: Optional[Union[Dict, str]] = None,
    proxies: Optional[Dict] = None,
    etag_timeout: float = 10,
    resume_download: bool = False,
    force_download: bool = False,
    token: Optional[Union[bool, str]] = None,
    local_files_only: bool = False,
    allow_patterns: Optional[Union[List[str], str]] = None,
    ignore_patterns: Optional[Union[List[str], str]] = None,
    max_workers: int = 8,
    tqdm_class: Optional['base_tqdm'] = None,
) -> str:
    """Download repo files.

    Download a whole snapshot of a repo's files at the specified revision. This is useful when you want all files from
    a repo, because you don't know which ones you will need a priori. All files are nested inside a folder in order
    to keep their actual filename relative to that folder. You can also filter which files to download using
    `allow_patterns` and `ignore_patterns`.

    If `local_dir` is provided, the file structure from the repo will be replicated in this location. You can configure
    how you want to move those files:
      - If `local_dir_use_symlinks="auto"` (default), files are downloaded and stored in the cache directory as blob
        files. Small files (<5MB) are duplicated in `local_dir` while a symlink is created for bigger files. The goal
        is to be able to manually edit and save small files without corrupting the cache while saving disk space for
        binary files. The 5MB threshold can be configured with the `HF_HUB_LOCAL_DIR_AUTO_SYMLINK_THRESHOLD`
        environment variable.
      - If `local_dir_use_symlinks=True`, files are downloaded, stored in the cache directory and symlinked in `local_dir`.
        This is optimal in term of disk usage but files must not be manually edited.
      - If `local_dir_use_symlinks=False` and the blob files exist in the cache directory, they are duplicated in the
        local dir. This means disk usage is not optimized.
      - Finally, if `local_dir_use_symlinks=False` and the blob files do not exist in the cache directory, then the
        files are downloaded and directly placed under `local_dir`. This means if you need to download them again later,
        they will be re-downloaded entirely.

    An alternative would be to clone the repo but this requires git and git-lfs to be installed and properly
    configured. It is also not possible to filter which files to download when cloning a repository using git.

    Args:
        repo_id (`str`):
            A user or an organization name and a repo name separated by a `/`.
        revision (`str`, *optional*):
            An optional Git revision id which can be a branch name, a tag, or a
            commit hash.
        repo_type (`str`, *optional*):
            Set to `"dataset"` or `"space"` if downloading from a dataset or space,
            `None` or `"model"` if downloading from a model. Default is `None`.
        cache_dir (`str`, `Path`, *optional*):
            Path to the folder where cached files are stored.
        local_dir (`str` or `Path`, *optional*:
            If provided, the downloaded files will be placed under this directory, either as symlinks (default) or
            regular files (see description for more details).
        local_dir_use_symlinks (`"auto"` or `bool`, defaults to `"auto"`):
            To be used with `local_dir`. If set to "auto", the cache directory will be used and the file will be either
            duplicated or symlinked to the local directory depending on its size. It set to `True`, a symlink will be
            created, no matter the file size. If set to `False`, the file will either be duplicated from cache (if
            already exists) or downloaded from the Hub and not cached. See description for more details.
        library_name (`str`, *optional*):
            The name of the library to which the object corresponds.
        library_version (`str`, *optional*):
            The version of the library.
        user_agent (`str`, `dict`, *optional*):
            The user-agent info in the form of a dictionary or a string.
        proxies (`dict`, *optional*):
            Dictionary mapping protocol to the URL of the proxy passed to
            `requests.request`.
        etag_timeout (`float`, *optional*, defaults to `10`):
            When fetching ETag, how many seconds to wait for the server to send
            data before giving up which is passed to `requests.request`.
        resume_download (`bool`, *optional*, defaults to `False):
            If `True`, resume a previously interrupted download.
        force_download (`bool`, *optional*, defaults to `False`):
            Whether the file should be downloaded even if it already exists in the local cache.
        token (`str`, `bool`, *optional*):
            A token to be used for the download.
                - If `True`, the token is read from the HuggingFace config
                  folder.
                - If a string, it's used as the authentication token.
        local_files_only (`bool`, *optional*, defaults to `False`):
            If `True`, avoid downloading the file and return the path to the
            local cached file if it exists.
        allow_patterns (`List[str]` or `str`, *optional*):
            If provided, only files matching at least one pattern are downloaded.
        ignore_patterns (`List[str]` or `str`, *optional*):
            If provided, files matching any of the patterns are not downloaded.
        max_workers (`int`, *optional*):
            Number of concurrent threads to download files (1 thread = 1 file download).
            Defaults to 8.
        tqdm_class (`tqdm`, *optional*):
            If provided, overwrites the default behavior for the progress bar. Passed
            argument must inherit from `tqdm.auto.tqdm` or at least mimic its behavior.
            Note that the `tqdm_class` is not passed to each individual download.
            Defaults to the custom HF progress bar that can be disabled by setting
            `HF_HUB_DISABLE_PROGRESS_BARS` environment variable.

    Returns:
        Local folder path (string) of repo snapshot

    <Tip>

    Raises the following errors:

    - [`EnvironmentError`](https://docs.python.org/3/library/exceptions.html#EnvironmentError)
      if `token=True` and the token cannot be found.
    - [`OSError`](https://docs.python.org/3/library/exceptions.html#OSError) if
      ETag cannot be determined.
    - [`ValueError`](https://docs.python.org/3/library/exceptions.html#ValueError)
      if some parameter value is invalid

    </Tip>
    """
    from tqdm.contrib.concurrent import thread_map
    
    from huggingface_hub.constants import (
        DEFAULT_REVISION,
        HF_HUB_ENABLE_HF_TRANSFER,
        HUGGINGFACE_HUB_CACHE,
        REPO_TYPES,
        hf_cache_home,
    )
    from huggingface_hub.file_download import (
        REGEX_COMMIT_HASH, 
        hf_hub_download, 
        repo_folder_name
    )
    from huggingface_hub.hf_api import HfApi
    from huggingface_hub.utils import filter_repo_objects
    from huggingface_hub.utils import tqdm as hf_tqdm
    # from transformers.file_utils

    if repo_type is None: repo_type = "model"
    if repo_type not in REPO_TYPES:
        raise ValueError(f"Invalid repo type: {repo_type}. Accepted repo types are: {str(REPO_TYPES)}")

    if cache_dir is None: cache_dir = os.path.join(hf_cache_home, f"{repo_type}s")
        # cache_dir = HUGGINGFACE_HUB_CACHE
    if revision is None: revision = DEFAULT_REVISION
    if isinstance(cache_dir, Path): cache_dir = str(cache_dir)
    storage_folder = os.path.join(cache_dir, repo_folder_name(repo_id=repo_id, repo_type=repo_type))
    # if we have no internet connection we will look for an
    # appropriate folder in the cache
    # If the specified revision is a commit hash, look inside "snapshots".
    # If the specified revision is a branch or tag, look inside "refs".
    if local_files_only:
        if REGEX_COMMIT_HASH.match(revision):
            commit_hash = revision
        else:
            # retrieve commit_hash from file
            ref_path = os.path.join(storage_folder, "refs", revision)
            commit_hash = Path(ref_path).read_text()
        snapshot_folder = os.path.join(storage_folder, "snapshots", commit_hash)

        if os.path.exists(snapshot_folder):
            return snapshot_folder

        raise ValueError(
            "Cannot find an appropriate cached snapshot folder for the specified"
            " revision on the local disk and outgoing traffic has been disabled. To"
            " enable repo look-ups and downloads online, set 'local_files_only' to"
            " False."
        )

    # if we have internet connection we retrieve the correct folder name from the huggingface api
    _api = HfApi()
    repo_info = _api.repo_info(
        repo_id=repo_id,
        repo_type=repo_type,
        revision=revision,
        token=token,
    )
    assert repo_info.sha is not None, "Repo info returned from server must have a revision sha."
    filtered_repo_files = list(
        filter_repo_objects(
            items=[f.rfilename for f in repo_info.siblings],
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
        )
    )
    commit_hash = repo_info.sha
    snapshot_folder = os.path.join(storage_folder, "snapshots", commit_hash)
    # if passed revision is not identical to commit_hash
    # then revision has to be a branch name or tag name.
    # In that case store a ref.
    if revision != commit_hash:
        ref_path = os.path.join(storage_folder, "refs", revision)
        os.makedirs(os.path.dirname(ref_path), exist_ok=True)
        with open(ref_path, "w") as f:
            f.write(commit_hash)

    # we pass the commit_hash to hf_hub_download
    # so no network call happens if we already
    # have the file locally.
    def _inner_hf_hub_download(repo_file: str):
        return hf_hub_download(
            repo_id,
            filename=repo_file,
            repo_type=repo_type,
            revision=commit_hash,
            cache_dir=cache_dir,
            local_dir=local_dir,
            local_dir_use_symlinks=local_dir_use_symlinks,
            library_name=library_name,
            library_version=library_version,
            user_agent=user_agent,
            proxies=proxies,
            etag_timeout=etag_timeout,
            resume_download=resume_download,
            force_download=force_download,
            token=token,
        )

    if HF_HUB_ENABLE_HF_TRANSFER:
        # when using hf_transfer we don't want extra parallelism
        # from the one hf_transfer provides
        for file in filtered_repo_files:
            _inner_hf_hub_download(file)
    else:
        thread_map(
            _inner_hf_hub_download,
            filtered_repo_files,
            desc=f"Fetching {len(filtered_repo_files)} files",
            max_workers=max_workers,
            # User can use its own tqdm class or the default one from `huggingface_hub.utils`
            tqdm_class=tqdm_class or hf_tqdm,
        )

    if local_dir is not None:
        return str(os.path.realpath(local_dir))
    return snapshot_folder

def download_pretrained(
    repo_id: str,
    revision: Optional[str] = None,
    repo_type: Optional[str] = None,
    auth_token: Optional[Union[str, bool]] = True,
    classifications: Optional[List[str]] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    allow_patterns: Optional[Union[List[str], str]] = None,
    **kwargs,
):
    """
    Handles the downloading of pretrained models from HuggingFace.
    """
    if classifications is None: 
        classifications = ['pytorch', 'tokenizer', 'config']
    if allow_patterns is None:
        allow_patterns = []
    if isinstance(allow_patterns, str):
        allow_patterns = [allow_patterns]
    for classification in classifications:
        allow_patterns.extend(reg_patterns[classification])
    if auth_token and auth_token is True:
        auth_token = get_huggingface_token(False)
    return snapshot_download(
        repo_id=repo_id,
        revision=revision,
        repo_type=repo_type,
        cache_dir=cache_dir,
        allow_patterns=allow_patterns,
        token=auth_token,
        **kwargs,
    )







# def get_file_from_url(
#     url: str,
#     idx: int,
#     total: int,
#     filename: Optional[str] = None,
#     output_folder: Optional[Path] = None,
#     overwrite: Optional[bool] = False,

#     # idx: int,
#     # tot: int,
#     # overwrite: bool = False,
# ):
#     output_path = output_folder / Path(url.split('/')[-1])
#     if output_path.exists() and not overwrite:
#         logger.info(f"Skipping {output_path} because it already exists.")
#         return
    
#     logger.info(f"Downloading file {idx} of {tot}...")
#     r = requests.get(
#         url, 
#         stream = True,
#         headers = {
#             'authorization': f'Bearer {huggingface_api_token}'
#         }
#     )
#     with open(output_folder / Path(url.split('/')[-1]), 'wb') as f:
#         total_size = int(r.headers.get('content-length', 0))
#         block_size = 1024
#         t = tqdm.tqdm(total=total_size, unit='iB', unit_scale=True)
#         for data in r.iter_content(block_size):
#             t.update(len(data))
#             f.write(data)
#         t.close()

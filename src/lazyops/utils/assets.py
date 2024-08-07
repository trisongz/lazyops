"""
Module Import Handler
"""
import typing
import functools
import pathlib
import importlib.util
from lazyops.utils.lazy import lazy_import

from typing import Optional, Dict, List, Union, Any, Callable, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from lazyops.types import BaseModel


@functools.lru_cache()
def get_module_path(
    module_name: str, 
    **kwargs
) -> pathlib.Path:
    """
    Get the path to the module.

    args:
        module_name: name of the module to import from (e.g. 'lazyops')
    
    Use it like this:

    >>> get_module_path('lazyops')
    """
    module_spec = importlib.util.find_spec(module_name)
    if not module_spec:
        raise ValueError(f"Module {module_name} not found")
    
    for path in module_spec.submodule_search_locations:
        module_path = pathlib.Path(path)
        if module_path.exists(): return module_path
    
    raise ValueError(f"Module {module_name} cant be found in the path")


@functools.lru_cache()
def get_module_assets_path(
    module_name: str, 
    assets_dir: typing.Optional[str] = 'assets',
    **kwargs
) -> pathlib.Path:
    """
    Get the path to the module's assets.

    args:
        module_name: name of the module to import from (e.g. 'lazyops')
        assets_dir: name of the assets directory (default: 'assets')
    
    Use it like this:

    >>> get_module_assets_path('lazyops', assets_dir = 'assets')
    """
    module_spec = importlib.util.find_spec(module_name)
    if not module_spec:
        raise ValueError(f"Module {module_name} not found")
    
    for path in module_spec.submodule_search_locations:
        asset_path = pathlib.Path(path).joinpath(assets_dir)
        if asset_path.exists(): return asset_path
    
    raise ValueError(f"Module {module_name} does not have an assets directory")


_allowed_extensions = [
    '.yaml', '.yml', '.json', '.jsonl', '.jsonlines', '.txt',
    '.csv', '.tsv', '.xls', '.xlsx', '.xlsm', '.xlsb', '.odf', '.ods', '.odt',
    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.rtf', '.txt', '.md', '.html', '.htm',
    '.pkl', '.pickle',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.svg', '.webp',
]

_binary_extensions = [
    '.pkl',
    '.pickle',
    '.pdf',
    '.doc',
    '.docx',
    '.jpg',
    '.jpeg',
    '.png',
    '.gif',
    '.bmp',
    '.tiff',
    '.tif',
    '.svg',
    '.webp',
]


@functools.lru_cache()
def search_for_assets(
    path: pathlib.Path,
    allowed_extensions: typing.Optional[typing.List[str]] = None,
    recursive: typing.Optional[bool] = False,
    **kwargs
) -> typing.List[pathlib.Path]:
    """
    Search for assets in a path.

    args:
        path: path to search
        allowed_extensions: list of allowed extensions (default: None)
        recursive: search recursively (default: False)
    
    Use it like this:

    >>> search_for_assets(pathlib.Path('lazyops/assets'), allowed_extensions = ['.yaml', '.yml'])
    """
    if allowed_extensions is None: allowed_extensions = _allowed_extensions
    result = []
    for file in path.iterdir():
        if file.is_dir() and recursive:
            result.extend(search_for_assets(file, allowed_extensions = allowed_extensions))
        elif file.suffix in allowed_extensions:
            result.append(file)
    return result

_file_loader_extensions = {
    'fileio.io.Yaml.loads': ['.yaml', '.yml'],
    'lazyops.utils.serialization.Json.loads': ['.json', '.jsonl', '.jsonlines'],
    'fileio.io.Csv': ['.csv'],
    'fileio.io.Tsv': ['.tsv'],
    'fileio.io.Dill': ['.pkl', '.pickle'],
}

def get_file_loader(
    path: pathlib.Path,
):
    """
    Get the file loader for the path.
    """
    return next(
        (
            lazy_import(loader)
            for loader, extensions in _file_loader_extensions.items()
            if path.suffix in extensions
        ),
        None,
    )


@functools.lru_cache()
def get_module_assets(
    module_name: str, 
    *path_parts,
    assets_dir: Optional[str] = 'assets',
    allowed_extensions: Optional[List[str]] = None,
    recursive: Optional[bool] = False,
    **kwargs
) -> Union[pathlib.Path, List[pathlib.Path]]:
    """
    Get the path to an assets from a module.

    args:
        module_name: name of the module to import from (e.g. 'configz')
        path_parts: path parts to the assets directory (default: [])
        assets_dir: name of the assets directory (default: 'assets')
        allowed_extensions: list of allowed extensions (default: None)
    
    Use it like this:

    >>> get_module_assets_path('lazyops', 'authz', 'file.json', assets_dir = 'assets')
    >>> get_module_assets_path('lazyops', 'authz') 
    """
    module_assets_path = get_module_assets_path(module_name, assets_dir = assets_dir)
    module_assets = module_assets_path.joinpath(*path_parts)
    # if its a file, return the file
    if module_assets.is_file(): return module_assets
    # if it's a directory, return a list of files
    return search_for_assets(module_assets, allowed_extensions = allowed_extensions, recursive = recursive)


@functools.lru_cache()
def load_file_content(
    path: pathlib.Path,
    model: Optional[Type['BaseModel']] = None,
    loader: Optional[Callable] = None,
    binary_load: Optional[bool] = None,
    **kwargs
) -> Any:
    """
    Load file content.

    args:
        path: path to the file
        model: model to parse the file with (default: None)
        loader: loader to use (default: None)
        binary_load: load the file as binary (default: None)
    """
    assert path.exists(), f"File {path} does not exist"
    binary_load = path.suffix in _binary_extensions if binary_load is None else binary_load
    if loader is None:
        loader = get_file_loader(path)
    data = path.read_bytes() if binary_load else path.read_text()
    if loader is None and model is None: return data
    if loader is not None:
        if path.suffix in {'jsonl', 'jsonlines'}:
            data = [loader(d) for d in data.splitlines()]
        else:
            data = loader(data)
    # load model
    if model is not None: 
        from lazyops.types.models import pyd_parse_obj
        data = pyd_parse_obj(model, data)
    return data


@functools.lru_cache()
def import_module_assets(
    module_name: str, 
    *path_parts,
    model: Optional[Type['BaseModel']] = None,
    load_file: Optional[bool] = False,
    loader: Optional[Callable] = None,
    assets_dir: Optional[str] = 'assets',
    allowed_extensions: Optional[List[str]] = None,
    recursive: Optional[bool] = False,
    as_dict: Optional[bool] = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Import assets from a module.

    args:
        module_name: name of the module to import from (e.g. 'configz')
        path_parts: path parts to the assets directory (default: [])
        model: model to parse the assets with (default: None)
        load_file: load the file (default: False)
        loader: loader to use (default: None)
        assets_dir: name of the assets directory (default: 'assets')
        allowed_extensions: list of allowed extensions (default: None)
        as_dict: return a dict instead of a list (default: False)
    """

    module_assets = get_module_assets(
        module_name,
        *path_parts,
        assets_dir = assets_dir,
        allowed_extensions = allowed_extensions,
        recursive = recursive,
        **kwargs
    )
    if not isinstance(module_assets, list): module_assets = [module_assets]
    return {
        asset.name: load_file_content(asset, model=model, loader=loader, **kwargs)
        if load_file or model is not None
        else asset
        for asset in module_assets
    } if as_dict else [
        load_file_content(asset, model=model, loader=loader, **kwargs)
        if load_file or model is not None
        else asset
        for asset in module_assets
    ]





"""
Wrapper Functions
"""

def create_import_assets_wrapper(
    module_name: str,
    assets_dir: Optional[str] = 'assets',
    allowed_extensions: Optional[List[str]] = None,
    recursive: Optional[bool] = False,
    as_dict: Optional[bool] = False,
) -> Callable[..., Union[Dict[str, Any], List[Any]]]:
    """
    Create a wrapper around import_module_assets.

    args:
        module_name: name of the module to import from (e.g. 'lazyops')
        assets_dir: name of the assets directory (default: 'assets')
        allowed_extensions: list of allowed extensions (default: None)
        as_dict: return a dict instead of a list (default: False)

    """
    def import_assets_wrapper(
        *path_parts,
        model: Optional[Type['BaseModel']] = None,
        load_file: Optional[bool] = False,
        **kwargs
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        Import assets from a module.

        args:
            path_parts: path parts to the assets directory (default: [])
            model: model to parse the assets with (default: None)
            load_file: load the file (default: False)
            **kwargs: additional arguments to pass to import_module_assets
        
        """
        return import_module_assets(
            module_name,
            *path_parts,
            assets_dir = assets_dir,
            model = model,
            load_file = load_file,
            allowed_extensions = allowed_extensions,
            recursive = recursive,
            as_dict = as_dict,
            **kwargs,
        )

    return import_assets_wrapper


def create_get_assets_wrapper(
    module_name: str,
    assets_dir: Optional[str] = 'assets',
    allowed_extensions: Optional[List[str]] = None,
    recursive: Optional[bool] = False,
    as_dict: Optional[bool] = False,
) -> Callable[..., Union[pathlib.Path, Any, List[pathlib.Path], List[Any], Dict[str, pathlib.Path], Dict[str, Any]]]:
    """
    Create a wrapper around `get_module_assets`.

    args:
        module_name: name of the module to import from (e.g. 'lazyops')
        assets_dir: name of the assets directory (default: 'assets')
        allowed_extensions: list of allowed extensions (default: None)
        as_dict: return a dict instead of a list (default: False)

    """
    def get_assets_wrapper(
        *path_parts,
        load_file: Optional[bool] = False,
        loader: Optional[Callable] = None,
        **kwargs
    ) -> Union[pathlib.Path, Any, List[pathlib.Path], List[Any], Dict[str, pathlib.Path], Dict[str, Any]]:
        """
        Import assets from a module.

        args:
            path_parts: path parts to the assets directory (default: [])
            load_file: load the file (default: False)
            loader: loader function to use (default: None)
            **kwargs: additional arguments to pass to `get_module_assets`
        
        """
        assets = get_module_assets(
            module_name,
            *path_parts,
            assets_dir = assets_dir,
            allowed_extensions = allowed_extensions,
            recursive = recursive,
            **kwargs,
        )
        if as_dict:
            if not isinstance(assets, list): assets = [assets]
            return {
                asset.name: load_file_content(asset, loader = loader, **kwargs) if load_file else asset
                for asset in assets
            }
        
        if isinstance(assets, list):
            return [load_file_content(asset, loader = loader, **kwargs) if load_file else asset for asset in assets]
        return load_file_content(assets, loader = loader, **kwargs) if load_file else assets

    return get_assets_wrapper


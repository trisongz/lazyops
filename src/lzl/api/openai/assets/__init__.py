from __future__ import annotations

import json
import pathlib
from typing import Optional, Dict, Any, List, Union

assets_path = pathlib.Path(__file__).parent
pricing_path = assets_path.joinpath('pricing')
presets_path = assets_path.joinpath('presets')

_provider_prices: Dict[str, List[Dict[str, Union[str, List, Dict, float]]]] = {}


def load_provider_prices(
    provider: Optional[str] = None,
    filepath: Optional[Union[str, pathlib.Path]] = None,
    overwrite: Optional[bool] = None,
    **kwargs,
) -> List[Dict[str, Union[str, List, Dict, float]]]:
    """
    Returns the provider prices
    """
    global _provider_prices
    if provider is None: provider = 'openai'
    elif filepath: provider = pathlib.Path(filepath).stem
    if provider not in _provider_prices or overwrite is True:
        if filepath is None: filepath = pricing_path.joinpath(f'{provider}.yaml')
        else: filepath = pathlib.Path(filepath)
        if not filepath.exists(): raise ValueError(f'{provider} Provider Pricing File does not exist: {filepath}')
        assert filepath.suffix in {
            ".yaml", ".yml", ".json"
        }, f"The {provider} Provider Pricing file must be a YAML or JSON file: {filepath}"
        if filepath.suffix == ".json":
            _provider_prices[provider] = json.loads(filepath.read_text())
        else:
            import yaml
            _provider_prices[provider] = yaml.safe_load(filepath.read_text())
    return _provider_prices[provider]


def load_preset_config(
    name: Optional[str] = None,
    filepath: Optional[Union[str, pathlib.Path]] = None,
    **overrides,
) -> Dict[str, Any]:
    """
    Returns the preset config
    """
    assert name or filepath, "You must provide either a name or a path to the preset"
    if filepath is None: filepath = presets_path.joinpath(f'{name}.yaml')
    else: filepath = pathlib.Path(filepath)
    if name is None: name = filepath.stem
    if not filepath.exists(): raise ValueError(f'{name} Preset Config File does not exist: {filepath}')
    assert filepath.suffix in {
        ".yaml", ".yml", ".json"
    }, f"The {name} preset file must be a YAML or JSON file: {filepath}"

    from lzo.utils import parse_envvars_from_text
    text = filepath.read_text()
    text, _ = parse_envvars_from_text(text)
    if filepath.suffix == ".json":
        data = json.loads(text)
    else:
        import yaml
        data = yaml.safe_load(text)
    if overrides: 
        from lzo.utils import update_dict
        data = update_dict(data, overrides)
    if data.get('models') and not isinstance(data['models'], list):
        if isinstance(data['models'], str):
            kws = {
                'filepath' if '/' in data['models'] else 'provider': data['models'],
            }
        elif isinstance(data['models'], dict):
            kws = data['models']
        else:
            raise ValueError(f'Invalid models: {data["models"]}')
        data['models'] = load_provider_prices(**kws)
    return data




from __future__ import annotations

from enum import Enum
from pathlib import Path
from lzo.types import BaseModel, Field, eproperty, model_validator
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from lzl.ext.jinja import Environment

lib_path = Path(__file__).parent

class Layout(Enum):
    MODERN = "modern"
    CLASSIC = "classic"

class SearchHotKey(Enum):
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"
    F = "f"
    G = "g"
    H = "h"
    I = "i"
    J = "j"
    K = "k"
    L = "l"
    M = "m"
    N = "n"
    O = "o"
    P = "p"
    Q = "q"
    R = "r"
    S = "s"
    T = "t"
    U = "u"
    V = "v"
    W = "w"
    X = "x"
    Y = "y"
    Z = "z"


class ScalarOpenAPI(BaseModel):
    """
    Scalar OpenAPI
    """
    openapi_url: Optional[str] = Field(None, description = "The OpenAPI URL that Scalar should load and use. This is normally done automatically by FastAPI using the default URL `/openapi.json`.")
    title: Optional[str] = Field(None, description = "The HTML `<title>` content, normally shown in the browser tab.")
    scalar_js_url: Optional[str] = Field("https://cdn.jsdelivr.net/npm/@scalar/api-reference", description = "The URL to use to load the Scalar JavaScript. It is normally set to a CDN URL.")
    scalar_proxy_url: Optional[str] = Field("", description = "The URL to use to set the Scalar Proxy. It is normally set to a Scalar API URL (https://proxy.scalar.com), but default is empty")
    scalar_favicon_url: Optional[str] = Field("https://fastapi.tiangolo.com/img/favicon.png", description = "The URL of the favicon to use. It is normally shown in the browser tab.")
    scalar_theme: Optional[Union[str, Path]] = Field(None, description = "Custom CSS theme for Scalar. A Path can be provided to load the theme from a file, or a string can be provided to use the string as the theme.")
    layout: Optional[Layout] = Field(Layout.MODERN, description = "The layout to use for Scalar. Default is \"modern\".")
    show_sidebar: Optional[bool] = Field(True, description = "A boolean to show the sidebar. Default is True which means the sidebar is shown.")
    hide_download_button: Optional[bool] = Field(False, description = "A boolean to hide the download button. Default is False which means the download button is shown.")
    hide_models: Optional[bool] = Field(False, description = "A boolean to hide all models. Default is False which means all models are shown.")
    dark_mode: Optional[bool] = Field(True, description = "Whether dark mode is on or off initially (light mode). Default is True which means dark mode is used.")
    search_hot_key: Optional[SearchHotKey] = Field(SearchHotKey.K, description = "The hotkey to use for search. Default is \"k\" (e.g. CMD+k).")
    hidden_clients: Optional[Union[bool, Dict[str, Union[bool, List[str]]], List[str]]] = Field(default_factory= list, description = "A dictionary with the keys being the target names and the values being a boolean to hide all clients of the target or a list clients. If a boolean is provided, it will hide all the clients with that name. Backwards compatibility: If a list of strings is provided, it will hide the clients with the name and the list of strings. Default is [] which means no clients are hidden.")
    servers: Optional[List[Dict[str, str]]] = Field(default_factory= list, description = "A list of dictionaries with the keys being the server name and the value being the server URL. Default is [] which means no servers are provided.")
    default_open_all_tags: Optional[bool] = Field(False, description = "A boolean to open all tags by default. Default is False which means tags are closed by default.")

    @model_validator(mode = 'before')
    def prevalidate_openapi(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pre-Validates the OpenAPI
        """
        if 'app' in values:
            values['_extra'] = {'app': values.pop('app')}
            if not values.get('openapi_url'): values['openapi_url'] = values['_extra']['app'].openapi_url
            if not values.get('title'): values['title'] = values['_extra']['app'].title
        return values
    

    @model_validator(mode = 'after')
    def validate_openapi(self):
        """
        Validates the OpenAPI
        """
        if self.scalar_theme:
            # Check if it's a potential path or a string
            if isinstance(self.scalar_theme, str) and 'var(-' not in self.scalar_theme:
                self.scalar_theme = Path(self.scalar_theme)
            if isinstance(self.scalar_theme, Path):
                self.scalar_theme = self.scalar_theme.read_text()
        return self

    @eproperty
    def app(self) -> Optional['FastAPI']:
        """
        Returns the app
        """
        return self._extra.get('app')

    @app.setter
    def app(self, value: 'FastAPI'):
        """
        Sets the app
        """
        self._extra['app'] = value
        if not self.openapi_url: self.openapi_url = value.openapi_url
        if not self.title and value.title: self.title = value.title

    @eproperty
    def j2(self) -> 'Environment':
        """
        Returns the j2 environment
        """
        from jinja2 import FileSystemLoader
        from lzl.ext.jinja import Environment
        return Environment(
            include_autofilters = True,
            default_mode = 'sync',
            variable_end_string = '|}',
            variable_start_string = '{|',
            loader = FileSystemLoader(lib_path.joinpath('static')),
        )

    def render(self, **kwargs) -> str:
        """
        Returns the HTML Response
        """
        return self.j2.get_template('template.html').render(src = self, **kwargs)

    # def __call__(self, **kwargs) -> 'HTMLResponse':
    #     """
    #     Returns the HTML Response
    #     """

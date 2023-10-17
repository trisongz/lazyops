from __future__ import annotations

"""
Stoplight OpenAPI Docs Params
"""

from lazyops.types import BaseModel, lazyproperty
from fastapi.responses import HTMLResponse
from typing import Optional, Dict, Any


class OpenAPIStoplight(BaseModel):
    app_title: Optional[str] = ''
    version: Optional[str] = 'latest'
    style: Optional[str] = ''
    favicon_url: Optional[str] = ''
    logo_url: Optional[str] = ''
    openapi_url: Optional[str] = '/openapi.json'
    google_analytics_tag_id: Optional[str] = None


    @lazyproperty
    def css_url(self):
        """
        Return the CSS URL for the Stoplight Elements.
        """
        return f"https://unpkg.com/@stoplight/elements@{self.version}/styles.min.css" \
            if (self.version and self.version != "latest") else "https://unpkg.com/@stoplight/elements/styles.min.css"
    
    @lazyproperty
    def js_url(self):
        """
        Return the JS URL for the Stoplight Elements.
        """
        return f"https://unpkg.com/@stoplight/elements@{self.version}/web-components.min.js" \
            if (self.version and self.version != "latest") else "https://unpkg.com/@stoplight/elements/web-components.min.js"
    

    @property
    def favicon(self) -> str:
        """Return favicon `<link>` tag, if applicable.
        Returns:
            A `<link>` tag if self.favicon_url is not empty, otherwise returns a placeholder meta tag.
        """
        return f"<link rel='icon' type='image/x-icon' href='{self.favicon_url}'>" if self.favicon_url else "<meta/>"


    @property
    def logo_data(self) -> str:
        """
        Return logo data
        """
        return f'logo="{self.logo_url}"' if self.logo_url else ''
    
    @lazyproperty
    def html_body(self):
        """
        Return the HTML body
        """
        head = f"""
            <head>
            <title>{self.app_title} - Documentation</title>
            {self.favicon}
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
            <link rel="stylesheet" href="{self.css_url}">
            <script src="{self.js_url}" crossorigin></script>
            <style>{self.style}</style>
            </head>
        """
        if self.google_analytics_tag_id:
            head += """
        <!-- Google tag (gtag.js) -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=<GOOGLE_TAG_ID>"></script>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());

            gtag('config', '<GOOGLE_TAG_ID>');
        </script>    
        """.replace('<GOOGLE_TAG_ID>', self.google_analytics_tag_id)

        _set_header_script = """
            <script>
            // Check whether `x-api-key` is present in the headers
            // and set `TryIt_securitySchemeValues` value in localStorage accordingly
            // const apiKey = localStorage.getItem('x-api-key');
            function parseHttpHeaders(httpHeaders) {
                return httpHeaders.split("\\n")
                .map(x=>x.split(/: */,2))
                .filter(x=>x[0])
                .reduce((ac, x)=>{ac[x[0]] = x[1];return ac;}, {});
            }

            var req = new XMLHttpRequest();
            req.open('GET', document.location, false);
            req.send(null);
            var headers = parseHttpHeaders(req.getAllResponseHeaders());

            // const apiKey = Headers().get('x-api-key');
            const apiKey = headers['x-api-key'];
            const authHeader = headers['authorization'];
            if (apiKey) {
                localStorage.setItem('TryIt_securitySchemeValues', JSON.stringify({
                    'API Key': apiKey.trim(),
                    'Auth0 Authorization': authHeader ? authHeader.trim() : ''
                }));
            }
            // else if (authHeader) {
            //     localStorage.setItem('TryIt_securitySchemeValues', JSON.stringify({       
            // }
            // if (authHeader) {
            
            </script>
        """

        body = f"""
            <body>
            {_set_header_script}
            <elements-api
                apiDescriptionUrl="{self.openapi_url}"
                router="hash"
                layout="sidebar"
                tryItCredentialsPolicy="include"
                {self.logo_data}
            />
            </body>
        """

        return f"""
        <!DOCTYPE html>
            <html>
                {head}
                {body}
            </html>
        """.strip()

    def get_response(self, headers: Optional[Dict[str, Any]] = None, **kwargs) -> HTMLResponse:
        """
        Return the HTML response
        """
        return HTMLResponse(content=self.html_body, headers=headers, **kwargs)
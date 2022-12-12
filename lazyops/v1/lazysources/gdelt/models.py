from ._base import *
from datetime import datetime
from typing import Optional, List, Union
from dataclasses import dataclass
from lazyops.lazyclasses.api import lazyclass
from lazyops.utils import timed_cache

_NP = None

# We lazily init news-please because it's a fat and heavy repo. Need to pick something else in the future.
@timed_cache(600)
def _init_newsplease():
    global _NP
    if _NP is not None:
        return
    nplease = lazy_init('news-please', 'newsplease')
    _NP = nplease.NewsPlease


@lazyclass
@dataclass
class Article:
    url: str
    title: str = None
    description: str = None
    image_url: str = None
    language: str = None
    domain: str = None
    text: str = None
    authors: List[str] = None
    date_publish: Union[str, datetime] = None
    date_modify: Union[str, datetime] = None
    extracted: Optional[bool] = False

    def _run(self):
        if self.extracted:
            return
        _init_newsplease()
        try:
            data = _NP.from_url(self.url)
            self.title = data.title
            self.description = data.description
            self.image_url = data.image_url
            self.language = data.language
            self.domain = data.source_domain
            self.text = data.maintext
            self.authors = data.authors
            self.date_publish = data.date_publish
            self.date_modify = data.date_modify
            self.extracted = True
        except Exception as e:
            logger.error(f'Error Parsing URL: {self.url}.\n{str(e)}')



@lazyclass
@dataclass
class GDELTArticle:
    url: str
    url_mobile: str = ''
    title: str = ''
    seendate: str = ''
    socialimage: str = ''
    domain: str = ''
    language: str = ''
    sourcecountry: str = ''
    text: Optional[str] = None
    extraction: Optional[Article] = None

    def parse(self):
        if self.extraction is not None:
            return
        self.extraction = Article(url=self.url)
        self.extraction._run()
        if self.extraction.extracted:
            self.text = self.extraction.text
    
    async def async_parse(self):
        if self.extraction is not None:
            return
        self.extraction = Article(url=self.url)
        self.extraction._run()
        if self.extraction.extracted:
            self.text = self.extraction.text
